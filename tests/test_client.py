"""Tests for jarvis-config-client."""

import pytest
from unittest.mock import patch, MagicMock

import httpx

from jarvis_config_client import (
    init,
    shutdown,
    get_service_url,
    get_all_services,
    refresh_services,
    require_service_url,
    get_auth_url,
    get_command_center_url,
    get_logs_url,
    get_llm_proxy_url,
    get_tts_url,
    get_ocr_url,
    get_recipes_url,
    get_mcp_url,
    get_mqtt_broker_url,
    get_whisper_url,
    ConfigClient,
    ConfigServiceNotFoundError,
    ServiceConfig,
    ServiceNotFoundError,
)


@pytest.fixture
def mock_services_response():
    """Mock response from config service."""
    return {
        "services": [
            {
                "name": "auth",
                "host": "localhost",
                "port": 7701,
                "url": "http://localhost:7701",
                "health_path": "/health",
                "description": "Authentication service",
            },
            {
                "name": "logs",
                "host": "localhost",
                "port": 7702,
                "url": "http://localhost:7702",
                "health_path": "/health",
                "description": "Logging service",
            },
            {
                "name": "llm-proxy",
                "host": "localhost",
                "port": 8000,
                "url": "http://localhost:8000",
                "health_path": "/health",
                "description": "LLM proxy",
            },
            {
                "name": "command-center",
                "host": "localhost",
                "port": 7703,
                "url": "http://localhost:7703",
                "health_path": "/health",
            },
            {
                "name": "tts",
                "host": "localhost",
                "port": 7704,
                "url": "http://localhost:7704",
                "health_path": "/health",
            },
            {
                "name": "ocr",
                "host": "localhost",
                "port": 7705,
                "url": "http://localhost:7705",
                "health_path": "/health",
            },
            {
                "name": "recipes",
                "host": "localhost",
                "port": 7706,
                "url": "http://localhost:7706",
                "health_path": "/health",
            },
            {
                "name": "mcp",
                "host": "localhost",
                "port": 7707,
                "url": "http://localhost:7707",
                "health_path": "/health",
            },
            {
                "name": "mqtt-broker",
                "host": "localhost",
                "port": 7708,
                "url": "http://localhost:7708",
                "health_path": "/health",
            },
        ]
    }


@pytest.fixture
def mock_httpx_client(mock_services_response):
    """Mock httpx client for testing."""
    with patch("jarvis_config_client.client.httpx.Client") as mock:
        mock_response = MagicMock()
        mock_response.json.return_value = mock_services_response
        mock_response.raise_for_status = MagicMock()

        mock_client_instance = MagicMock()
        mock_client_instance.get.return_value = mock_response
        mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = MagicMock(return_value=False)

        mock.return_value = mock_client_instance
        yield mock


class TestConfigClient:
    """Tests for ConfigClient class."""

    def test_fetch_services(self, mock_httpx_client, mock_services_response):
        """Test fetching services from config service."""
        client = ConfigClient(config_url="http://localhost:7700")
        services = client.fetch_services()

        assert len(services) == 9
        assert "auth" in services
        assert "logs" in services
        assert services["auth"].url == "http://localhost:7701"
        assert services["logs"].port == 7702

    def test_refresh_updates_cache(self, mock_httpx_client):
        """Test that refresh updates the internal cache."""
        client = ConfigClient(config_url="http://localhost:7700")

        assert len(client.get_all()) == 0

        success = client.refresh()

        assert success is True
        assert len(client.get_all()) == 9

    def test_get_url(self, mock_httpx_client):
        """Test getting URL for a specific service."""
        client = ConfigClient(config_url="http://localhost:7700")
        client.refresh()

        url = client.get_url("auth")
        assert url == "http://localhost:7701"

        url = client.get_url("nonexistent")
        assert url is None

    def test_get_service(self, mock_httpx_client):
        """Test getting service config."""
        client = ConfigClient(config_url="http://localhost:7700")
        client.refresh()

        svc = client.get_service("logs")
        assert isinstance(svc, ServiceConfig)
        assert svc.name == "logs"
        assert svc.host == "localhost"
        assert svc.port == 7702


class TestRemoteUrlStyle:
    """Tests for remote URL style detection in fetch_services."""

    def test_remote_style_sends_params(self, mock_httpx_client):
        """Test that JARVIS_CONFIG_URL_STYLE=remote sends style=remote param."""
        with patch.dict("os.environ", {"JARVIS_CONFIG_URL_STYLE": "remote"}):
            client = ConfigClient(config_url="http://10.0.0.5:7700")
            client.fetch_services()

            # Verify the GET call included style=remote and remote_host
            mock_instance = mock_httpx_client.return_value.__enter__.return_value
            call_args = mock_instance.get.call_args
            assert call_args.kwargs["params"]["style"] == "remote"
            assert call_args.kwargs["params"]["remote_host"] == "10.0.0.5"

    def test_remote_style_infers_host_from_config_url(self, mock_httpx_client):
        """Test host is auto-inferred from non-localhost config URL."""
        with patch.dict("os.environ", {"JARVIS_CONFIG_URL_STYLE": "remote"}):
            client = ConfigClient(config_url="http://192.168.1.100:7700")
            client.fetch_services()

            mock_instance = mock_httpx_client.return_value.__enter__.return_value
            call_args = mock_instance.get.call_args
            assert call_args.kwargs["params"]["remote_host"] == "192.168.1.100"

    def test_remote_style_skips_localhost_host(self, mock_httpx_client):
        """Test remote style does not send remote_host when config URL is localhost."""
        with patch.dict("os.environ", {"JARVIS_CONFIG_URL_STYLE": "remote"}):
            client = ConfigClient(config_url="http://localhost:7700")
            client.fetch_services()

            mock_instance = mock_httpx_client.return_value.__enter__.return_value
            call_args = mock_instance.get.call_args
            assert call_args.kwargs["params"]["style"] == "remote"
            assert "remote_host" not in call_args.kwargs["params"]

    def test_no_style_env_sends_no_params(self, mock_httpx_client):
        """Test that without JARVIS_CONFIG_URL_STYLE, no style param is sent."""
        with patch.dict("os.environ", {}, clear=False):
            # Ensure the env var is not set
            import os
            os.environ.pop("JARVIS_CONFIG_URL_STYLE", None)

            client = ConfigClient(config_url="http://10.0.0.5:7700")
            client.fetch_services()

            mock_instance = mock_httpx_client.return_value.__enter__.return_value
            call_args = mock_instance.get.call_args
            assert call_args.kwargs["params"] == {}


class TestGlobalFunctions:
    """Tests for module-level functions."""

    def teardown_method(self):
        """Clean up after each test."""
        shutdown()

    def test_init_with_url(self, mock_httpx_client):
        """Test init with explicit URL."""
        success = init(config_url="http://localhost:7700")
        assert success is True

    @patch("jarvis_config_client.client.discover_config_service", return_value=None)
    def test_init_without_url_raises_config_not_found(self, mock_discover):
        """Test init without URL raises ConfigServiceNotFoundError."""
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ConfigServiceNotFoundError, match="Could not find"):
                init()

    @patch("jarvis_config_client.client.discover_config_service", return_value="http://192.168.1.50:7700")
    def test_init_auto_discovery(self, mock_discover, mock_httpx_client):
        """Test init with auto-discovery."""
        with patch.dict("os.environ", {}, clear=True):
            success = init()
            assert success is True
            mock_discover.assert_called_once()

    def test_get_service_url_before_init_raises(self):
        """Test get_service_url before init raises RuntimeError."""
        with pytest.raises(RuntimeError, match="not initialized"):
            get_service_url("auth")

    def test_get_service_url_after_init(self, mock_httpx_client):
        """Test get_service_url after init works."""
        init(config_url="http://localhost:7700")

        url = get_service_url("auth")
        assert url == "http://localhost:7701"

    def test_get_all_services_after_init(self, mock_httpx_client):
        """Test get_all_services after init works."""
        init(config_url="http://localhost:7700")

        services = get_all_services()
        assert len(services) == 9
        assert "auth" in services
        assert "logs" in services


class TestRequireServiceUrl:
    """Tests for require_service_url."""

    def teardown_method(self):
        shutdown()

    def test_returns_url_when_found(self, mock_httpx_client):
        """Test require_service_url returns URL for existing service."""
        init(config_url="http://localhost:7700")
        url = require_service_url("auth")
        assert url == "http://localhost:7701"

    def test_raises_when_not_found(self, mock_httpx_client):
        """Test require_service_url raises ServiceNotFoundError for missing service."""
        init(config_url="http://localhost:7700")
        with pytest.raises(ServiceNotFoundError, match="nonexistent"):
            require_service_url("nonexistent")

    def test_raises_before_init(self):
        """Test require_service_url raises RuntimeError before init."""
        with pytest.raises(RuntimeError, match="not initialized"):
            require_service_url("auth")


class TestNamedHelpers:
    """Tests for named helper functions (get_auth_url, get_logs_url, etc)."""

    def teardown_method(self):
        shutdown()

    def test_get_auth_url(self, mock_httpx_client):
        init(config_url="http://localhost:7700")
        assert get_auth_url() == "http://localhost:7701"

    def test_get_logs_url(self, mock_httpx_client):
        init(config_url="http://localhost:7700")
        assert get_logs_url() == "http://localhost:7702"

    def test_get_llm_proxy_url(self, mock_httpx_client):
        init(config_url="http://localhost:7700")
        assert get_llm_proxy_url() == "http://localhost:8000"

    def test_get_command_center_url(self, mock_httpx_client):
        init(config_url="http://localhost:7700")
        assert get_command_center_url() == "http://localhost:7703"

    def test_get_tts_url(self, mock_httpx_client):
        init(config_url="http://localhost:7700")
        assert get_tts_url() == "http://localhost:7704"

    def test_get_ocr_url(self, mock_httpx_client):
        init(config_url="http://localhost:7700")
        assert get_ocr_url() == "http://localhost:7705"

    def test_get_recipes_url(self, mock_httpx_client):
        init(config_url="http://localhost:7700")
        assert get_recipes_url() == "http://localhost:7706"

    def test_get_mcp_url(self, mock_httpx_client):
        init(config_url="http://localhost:7700")
        assert get_mcp_url() == "http://localhost:7707"

    def test_get_mqtt_broker_url(self, mock_httpx_client):
        init(config_url="http://localhost:7700")
        assert get_mqtt_broker_url() == "http://localhost:7708"

    def test_helper_raises_when_service_missing(self, mock_httpx_client):
        """Named helpers raise ServiceNotFoundError when service not in registry."""
        init(config_url="http://localhost:7700")
        # whisper is not in our mock response
        with pytest.raises(ServiceNotFoundError, match="whisper"):
            get_whisper_url()


class TestDockerUrlStyle:
    """Tests for Docker URL style detection."""

    def test_dockerized_env_var(self, mock_httpx_client):
        """Test that JARVIS_CONFIG_URL_STYLE=dockerized sends style param."""
        client = ConfigClient(config_url="http://localhost:7700")
        with patch.dict("os.environ", {"JARVIS_CONFIG_URL_STYLE": "dockerized"}):
            client.fetch_services()
        call_args = mock_httpx_client.return_value.get.call_args
        assert call_args[1]["params"] == {"style": "dockerized"}

    def test_docker_internal_url(self, mock_httpx_client):
        """Test that host.docker.internal in URL triggers dockerized style."""
        client = ConfigClient(config_url="http://host.docker.internal:7700")
        client.fetch_services()
        call_args = mock_httpx_client.return_value.get.call_args
        assert call_args[1]["params"] == {"style": "dockerized"}


class TestFetchErrors:
    """Tests for HTTP error handling in fetch_services."""

    def test_fetch_services_http_error(self):
        """Test fetch_services raises on HTTP error."""
        with patch("jarvis_config_client.client.httpx.Client") as mock:
            mock_instance = MagicMock()
            mock_instance.get.side_effect = httpx.ConnectError("refused")
            mock_instance.__enter__ = MagicMock(return_value=mock_instance)
            mock_instance.__exit__ = MagicMock(return_value=False)
            mock.return_value = mock_instance

            client = ConfigClient(config_url="http://localhost:7700")
            with pytest.raises(httpx.HTTPError):
                client.fetch_services()


class TestRefreshAdvanced:
    """Tests for advanced refresh scenarios."""

    def test_refresh_calls_on_refresh_callback(self, mock_httpx_client):
        """Test that refresh calls the on_refresh callback."""
        callback = MagicMock()
        client = ConfigClient(config_url="http://localhost:7700", on_refresh=callback)
        client.refresh()
        callback.assert_called_once()
        assert len(callback.call_args[0][0]) == 9

    def test_refresh_callback_error_does_not_break_refresh(self, mock_httpx_client):
        """Test that a failing callback doesn't break refresh."""
        callback = MagicMock(side_effect=ValueError("boom"))
        client = ConfigClient(config_url="http://localhost:7700", on_refresh=callback)
        result = client.refresh()
        assert result is True
        assert len(client.get_all()) == 9

    def test_refresh_failure_falls_back_to_db(self):
        """Test refresh failure loads from DB as fallback."""
        with patch("jarvis_config_client.client.httpx.Client") as mock_http:
            mock_instance = MagicMock()
            mock_instance.get.side_effect = httpx.ConnectError("refused")
            mock_instance.__enter__ = MagicMock(return_value=mock_instance)
            mock_instance.__exit__ = MagicMock(return_value=False)
            mock_http.return_value = mock_instance

            mock_engine = MagicMock()
            client = ConfigClient(config_url="http://localhost:7700", db_engine=mock_engine)

            # Simulate _load_from_db returning cached services
            cached = {"auth": ServiceConfig(name="auth", host="localhost", port=7701,
                                            url="http://localhost:7701", health_path="/health")}
            with patch.object(client, "_load_from_db", return_value=cached):
                result = client.refresh()

            assert result is False
            assert client.get_url("auth") == "http://localhost:7701"


class TestStartStop:
    """Tests for start/stop lifecycle."""

    def test_start_already_initialized(self, mock_httpx_client):
        """Test start returns True immediately when already initialized."""
        client = ConfigClient(config_url="http://localhost:7700")
        client.start()
        result = client.start()
        assert result is True
        client.stop()

    def test_start_loads_from_db_first(self, mock_httpx_client):
        """Test start loads from DB before fetching."""
        mock_engine = MagicMock()
        client = ConfigClient(config_url="http://localhost:7700", db_engine=mock_engine)

        cached = {"auth": ServiceConfig(name="auth", host="localhost", port=7701,
                                        url="http://localhost:7701", health_path="/health")}
        with patch.object(client, "_load_from_db", return_value=cached):
            with patch.object(client, "_init_db"):
                client.start()

        client.stop()

    def test_stop_when_not_started(self):
        """Test stop is safe when not started."""
        client = ConfigClient(config_url="http://localhost:7700")
        client.stop()  # Should not raise


class TestDbPersistence:
    """Tests for database persistence."""

    def test_init_db_creates_table(self):
        """Test _init_db creates the service_configs table."""
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

        client = ConfigClient(config_url="http://localhost:7700", db_engine=mock_engine)
        # _init_db was called in __init__
        mock_conn.execute.assert_called_once()
        mock_conn.commit.assert_called_once()

    def test_save_to_db(self):
        """Test _save_to_db persists services."""
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

        with patch.object(ConfigClient, "_init_db"):
            client = ConfigClient(config_url="http://localhost:7700", db_engine=mock_engine)

        services = {
            "auth": ServiceConfig(name="auth", host="localhost", port=7701,
                                  url="http://localhost:7701", health_path="/health"),
        }
        client._save_to_db(services)
        mock_conn.execute.assert_called()
        mock_conn.commit.assert_called()

    def test_save_to_db_without_engine(self):
        """Test _save_to_db is a no-op without db_engine."""
        client = ConfigClient(config_url="http://localhost:7700")
        client._save_to_db({})  # Should not raise

    def test_load_from_db(self):
        """Test _load_from_db retrieves services."""
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_row = MagicMock()
        mock_row.name = "auth"
        mock_row.host = "localhost"
        mock_row.port = 7701
        mock_row.url = "http://localhost:7701"
        mock_row.health_path = "/health"
        mock_row.scheme = "http"
        mock_row.description = "Auth service"
        mock_conn.execute.return_value = [mock_row]
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

        with patch.object(ConfigClient, "_init_db"):
            client = ConfigClient(config_url="http://localhost:7700", db_engine=mock_engine)

        services = client._load_from_db()
        assert "auth" in services
        assert services["auth"].url == "http://localhost:7701"

    def test_load_from_db_without_engine(self):
        """Test _load_from_db returns empty dict without db_engine."""
        client = ConfigClient(config_url="http://localhost:7700")
        assert client._load_from_db() == {}

    def test_save_to_db_handles_error(self):
        """Test _save_to_db handles SQLAlchemy errors gracefully."""
        from sqlalchemy.exc import SQLAlchemyError

        mock_engine = MagicMock()
        mock_engine.connect.side_effect = SQLAlchemyError("connection failed")

        with patch.object(ConfigClient, "_init_db"):
            client = ConfigClient(config_url="http://localhost:7700", db_engine=mock_engine)

        services = {
            "auth": ServiceConfig(name="auth", host="localhost", port=7701,
                                  url="http://localhost:7701", health_path="/health"),
        }
        # Should not raise
        client._save_to_db(services)

    def test_load_from_db_handles_error(self):
        """Test _load_from_db handles SQLAlchemy errors gracefully."""
        from sqlalchemy.exc import SQLAlchemyError

        mock_engine = MagicMock()
        mock_engine.connect.side_effect = SQLAlchemyError("connection failed")

        with patch.object(ConfigClient, "_init_db"):
            client = ConfigClient(config_url="http://localhost:7700", db_engine=mock_engine)

        result = client._load_from_db()
        assert result == {}


class TestGlobalFunctionsExtra:
    """Additional tests for module-level functions."""

    def teardown_method(self):
        shutdown()

    def test_get_all_services_before_init_raises(self):
        """Test get_all_services before init raises RuntimeError."""
        with pytest.raises(RuntimeError, match="not initialized"):
            get_all_services()

    def test_refresh_services_before_init_raises(self):
        """Test refresh_services before init raises RuntimeError."""
        with pytest.raises(RuntimeError, match="not initialized"):
            refresh_services()

    def test_refresh_services_after_init(self, mock_httpx_client):
        """Test refresh_services after init works."""
        init(config_url="http://localhost:7700")
        result = refresh_services()
        assert result is True

    def test_init_reinitializes(self, mock_httpx_client):
        """Test calling init twice reinitializes."""
        init(config_url="http://localhost:7700")
        # Second init should work without error
        result = init(config_url="http://localhost:7700")
        assert result is True
