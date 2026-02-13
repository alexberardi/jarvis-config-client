"""
Network discovery for jarvis-config-service.

Discovery chain:
1. JARVIS_CONFIG_URL env var → return immediately
2. Probe localhost:{port}/info → validate response
3. Find local IP → scan /24 subnet on {port} concurrently
4. Return discovered URL or None
"""

import logging
import os
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_PORT = 8013


def _probe_config_service(url: str, timeout: float) -> str | None:
    """Probe a URL for jarvis-config-service /info endpoint."""
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.get(f"{url}/info")
            if response.status_code == 200:
                data = response.json()
                if data.get("service") == "jarvis-config-service":
                    return url
    except (httpx.HTTPError, OSError, ValueError):
        pass
    return None


def _get_local_ip() -> str | None:
    """Get the local IP address by connecting to an external address."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return None


def _scan_subnet(local_ip: str, port: int, timeout: float) -> str | None:
    """Scan the /24 subnet for jarvis-config-service."""
    prefix = ".".join(local_ip.split(".")[:3])

    def probe_host(host_num: int) -> str | None:
        ip = f"{prefix}.{host_num}"
        if ip == local_ip:
            return None
        url = f"http://{ip}:{port}"
        return _probe_config_service(url, timeout)

    with ThreadPoolExecutor(max_workers=50) as executor:
        futures = {executor.submit(probe_host, i): i for i in range(1, 255)}
        for future in as_completed(futures):
            result = future.result()
            if result is not None:
                # Cancel remaining futures
                for f in futures:
                    f.cancel()
                return result

    return None


def discover_config_service(port: int | None = None, timeout: float = 2.0) -> str | None:
    """
    Discover jarvis-config-service on the network.

    Discovery chain:
    1. JARVIS_CONFIG_URL env var → return immediately
    2. Probe localhost:{port}/info
    3. Find local IP → scan /24 subnet concurrently
    4. Return discovered URL or None

    Args:
        port: Port to scan (default: JARVIS_CONFIG_PORT env var or 8013)
        timeout: Timeout per probe in seconds

    Returns:
        Config service URL or None if not found
    """
    # 1. Check env var
    env_url = os.getenv("JARVIS_CONFIG_URL")
    if env_url:
        logger.debug(f"Using JARVIS_CONFIG_URL: {env_url}")
        return env_url

    # Resolve port
    if port is None:
        port_str = os.getenv("JARVIS_CONFIG_PORT")
        port = int(port_str) if port_str else _DEFAULT_PORT

    # 2. Probe localhost
    localhost_url = f"http://localhost:{port}"
    logger.debug(f"Probing localhost: {localhost_url}")
    result = _probe_config_service(localhost_url, timeout)
    if result:
        logger.info(f"Found config service at {result}")
        return result

    # 3. Subnet scan
    local_ip = _get_local_ip()
    if local_ip:
        logger.debug(f"Scanning subnet from {local_ip}")
        result = _scan_subnet(local_ip, port, timeout)
        if result:
            logger.info(f"Found config service at {result}")
            return result

    logger.warning("Could not discover jarvis-config-service")
    return None
