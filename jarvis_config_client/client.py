"""
Jarvis Config Client - Core client implementation.

Fetches service URLs from jarvis-config-service, caches them locally,
and provides background refresh functionality.
"""

import atexit
import logging
import os
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

import httpx

# SQLAlchemy is optional - only needed for database persistence
try:
    from sqlalchemy import text
    from sqlalchemy.exc import SQLAlchemyError
except ImportError:
    text = None  # type: ignore[assignment]
    SQLAlchemyError = Exception  # type: ignore[misc,assignment]

logger = logging.getLogger(__name__)


@dataclass
class ServiceConfig:
    """Configuration for a single service."""
    name: str
    host: str
    port: int
    url: str
    health_path: str
    scheme: str = "http"
    description: Optional[str] = None


class ConfigClient:
    """
    Client for fetching and caching service configurations.

    Supports:
    - Fetching all services from config service
    - In-memory caching with optional database persistence
    - Background refresh at configurable interval
    - Fallback to cached values on failure
    """

    def __init__(
        self,
        config_url: str,
        refresh_interval_seconds: int = 300,  # 5 minutes
        db_engine: Optional[Any] = None,
        on_refresh: Optional[Callable[[Dict[str, ServiceConfig]], None]] = None,
    ):
        """
        Initialize the config client.

        Args:
            config_url: URL of jarvis-config-service (e.g., http://localhost:8013)
            refresh_interval_seconds: How often to refresh service URLs (default: 300s / 5 min)
            db_engine: Optional SQLAlchemy engine for persistent caching
            on_refresh: Optional callback when services are refreshed
        """
        self.config_url = config_url.rstrip("/")
        self.refresh_interval = refresh_interval_seconds
        self.db_engine = db_engine
        self.on_refresh = on_refresh

        self._services: Dict[str, ServiceConfig] = {}
        self._lock = threading.RLock()
        self._refresh_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._initialized = False
        self._last_refresh: Optional[float] = None

        # Initialize database table if engine provided
        if self.db_engine:
            self._init_db()

    def _init_db(self) -> None:
        """Create the service_configs table if it doesn't exist."""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS service_configs (
            name VARCHAR(64) PRIMARY KEY,
            host VARCHAR(255) NOT NULL,
            port INTEGER NOT NULL,
            url VARCHAR(512) NOT NULL,
            health_path VARCHAR(255) NOT NULL,
            scheme VARCHAR(10) NOT NULL DEFAULT 'http',
            description VARCHAR(500),
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """

        with self.db_engine.connect() as conn:
            conn.execute(text(create_table_sql))
            conn.commit()

        logger.debug("Initialized service_configs table")

    def _save_to_db(self, services: Dict[str, ServiceConfig]) -> None:
        """Persist services to database."""
        if not self.db_engine:
            return

        upsert_sql = """
        INSERT INTO service_configs (name, host, port, url, health_path, scheme, description, updated_at)
        VALUES (:name, :host, :port, :url, :health_path, :scheme, :description, CURRENT_TIMESTAMP)
        ON CONFLICT (name) DO UPDATE SET
            host = EXCLUDED.host,
            port = EXCLUDED.port,
            url = EXCLUDED.url,
            health_path = EXCLUDED.health_path,
            scheme = EXCLUDED.scheme,
            description = EXCLUDED.description,
            updated_at = CURRENT_TIMESTAMP
        """

        try:
            with self.db_engine.connect() as conn:
                for svc in services.values():
                    conn.execute(text(upsert_sql), {
                        "name": svc.name,
                        "host": svc.host,
                        "port": svc.port,
                        "url": svc.url,
                        "health_path": svc.health_path,
                        "scheme": svc.scheme,
                        "description": svc.description,
                    })
                conn.commit()
            logger.debug(f"Saved {len(services)} services to database")
        except SQLAlchemyError as e:
            logger.warning(f"Failed to save services to database: {type(e).__name__}: {e}")

    def _load_from_db(self) -> Dict[str, ServiceConfig]:
        """Load services from database."""
        if not self.db_engine:
            return {}

        try:
            with self.db_engine.connect() as conn:
                result = conn.execute(text("SELECT name, host, port, url, health_path, scheme, description FROM service_configs"))
                services = {}
                for row in result:
                    services[row.name] = ServiceConfig(
                        name=row.name,
                        host=row.host,
                        port=row.port,
                        url=row.url,
                        health_path=row.health_path,
                        scheme=getattr(row, "scheme", "http"),
                        description=row.description,
                    )
                logger.debug(f"Loaded {len(services)} services from database")
                return services
        except SQLAlchemyError as e:
            logger.warning(f"Failed to load services from database: {type(e).__name__}: {e}")
            return {}

    def fetch_services(self) -> Dict[str, ServiceConfig]:
        """
        Fetch all services from the config service.

        Uses JARVIS_CONFIG_URL_STYLE env var to determine URL style.
        Set to 'dockerized' for containers needing host.docker.internal.

        Returns:
            Dict mapping service names to ServiceConfig objects

        Raises:
            httpx.HTTPError: If the request fails
        """
        url = f"{self.config_url}/services"

        # Check for URL style preference (for Docker containers)
        url_style = os.getenv("JARVIS_CONFIG_URL_STYLE", "").lower()
        params = {}
        if url_style == "dockerized":
            params["style"] = "dockerized"

        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

            services = {}
            for svc in data.get("services", []):
                config = ServiceConfig(
                    name=svc["name"],
                    host=svc["host"],
                    port=svc["port"],
                    url=svc["url"],
                    health_path=svc.get("health_path", "/health"),
                    scheme=svc.get("scheme", "http"),
                    description=svc.get("description"),
                )
                services[config.name] = config

            logger.info(f"Fetched {len(services)} services from config service")
            return services

        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch services from {url}: {e}")
            raise

    def refresh(self) -> bool:
        """
        Refresh the service cache from the config service.

        Returns:
            True if refresh succeeded, False otherwise
        """
        try:
            services = self.fetch_services()

            with self._lock:
                self._services = services
                self._last_refresh = time.time()

            # Persist to database
            self._save_to_db(services)

            # Call refresh callback
            if self.on_refresh:
                try:
                    self.on_refresh(services)
                except Exception as e:
                    logger.warning(f"Refresh callback failed: {e}")

            return True

        except httpx.HTTPError as e:
            logger.warning(f"Failed to refresh services: {type(e).__name__}: {e}")

            # Try to load from database as fallback
            if self.db_engine and not self._services:
                cached = self._load_from_db()
                if cached:
                    with self._lock:
                        self._services = cached
                    logger.info(f"Using {len(cached)} cached services from database")

            return False

    def _refresh_loop(self) -> None:
        """Background thread that refreshes services periodically."""
        while not self._stop_event.is_set():
            # Wait for the refresh interval or until stop is signaled
            if self._stop_event.wait(timeout=self.refresh_interval):
                break

            logger.debug("Background refresh triggered")
            self.refresh()

    def start(self) -> bool:
        """
        Start the config client.

        Fetches initial services and starts background refresh thread.

        Returns:
            True if initial fetch succeeded, False if using cached data
        """
        if self._initialized:
            return True

        # Try to load from database first (for fast startup)
        if self.db_engine:
            cached = self._load_from_db()
            if cached:
                with self._lock:
                    self._services = cached
                logger.info(f"Loaded {len(cached)} cached services from database")

        # Fetch fresh data
        success = self.refresh()

        # Start background refresh thread
        self._stop_event.clear()
        self._refresh_thread = threading.Thread(
            target=self._refresh_loop,
            name="jarvis-config-refresh",
            daemon=True,
        )
        self._refresh_thread.start()

        self._initialized = True
        logger.info(f"Config client started (refresh every {self.refresh_interval}s)")

        return success

    def stop(self) -> None:
        """Stop the background refresh thread."""
        if self._refresh_thread and self._refresh_thread.is_alive():
            self._stop_event.set()
            self._refresh_thread.join(timeout=5.0)
            logger.info("Config client stopped")

        self._initialized = False

    def get_service(self, name: str) -> Optional[ServiceConfig]:
        """
        Get configuration for a specific service.

        Args:
            name: Service name (e.g., "jarvis-auth")

        Returns:
            ServiceConfig or None if not found
        """
        with self._lock:
            return self._services.get(name)

    def get_url(self, name: str) -> Optional[str]:
        """
        Get URL for a specific service.

        Args:
            name: Service name (e.g., "jarvis-auth")

        Returns:
            Service URL or None if not found
        """
        svc = self.get_service(name)
        return svc.url if svc else None

    def get_all(self) -> Dict[str, ServiceConfig]:
        """Get all cached services."""
        with self._lock:
            return dict(self._services)


# Global singleton instance
_client: Optional[ConfigClient] = None


def init(
    config_url: Optional[str] = None,
    refresh_interval_seconds: int = 300,
    db_engine: Optional[Any] = None,
    on_refresh: Optional[Callable[[Dict[str, ServiceConfig]], None]] = None,
) -> bool:
    """
    Initialize the global config client.

    Args:
        config_url: URL of jarvis-config-service. Defaults to JARVIS_CONFIG_URL env var.
        refresh_interval_seconds: How often to refresh (default: 300s / 5 min)
        db_engine: Optional SQLAlchemy engine for persistent caching
        on_refresh: Optional callback when services are refreshed

    Returns:
        True if initial fetch succeeded, False if using cached data

    Raises:
        ValueError: If no config_url provided and JARVIS_CONFIG_URL not set
    """
    global _client

    if _client is not None:
        logger.warning("Config client already initialized, reinitializing...")
        _client.stop()

    url = config_url or os.getenv("JARVIS_CONFIG_URL")
    if not url:
        raise ValueError(
            "config_url not provided and JARVIS_CONFIG_URL environment variable not set"
        )

    _client = ConfigClient(
        config_url=url,
        refresh_interval_seconds=refresh_interval_seconds,
        db_engine=db_engine,
        on_refresh=on_refresh,
    )

    # Register shutdown handler
    atexit.register(shutdown)

    return _client.start()


def shutdown() -> None:
    """Shutdown the global config client."""
    global _client

    if _client is not None:
        _client.stop()
        _client = None


def get_service_url(name: str) -> Optional[str]:
    """
    Get URL for a specific service.

    Args:
        name: Service name (e.g., "jarvis-auth")

    Returns:
        Service URL or None if not found

    Raises:
        RuntimeError: If init() hasn't been called
    """
    if _client is None:
        raise RuntimeError("Config client not initialized. Call init() first.")

    return _client.get_url(name)


def get_all_services() -> Dict[str, ServiceConfig]:
    """
    Get all cached services.

    Returns:
        Dict mapping service names to ServiceConfig objects

    Raises:
        RuntimeError: If init() hasn't been called
    """
    if _client is None:
        raise RuntimeError("Config client not initialized. Call init() first.")

    return _client.get_all()


def refresh_services() -> bool:
    """
    Manually refresh services from config service.

    Returns:
        True if refresh succeeded, False otherwise

    Raises:
        RuntimeError: If init() hasn't been called
    """
    if _client is None:
        raise RuntimeError("Config client not initialized. Call init() first.")

    return _client.refresh()
