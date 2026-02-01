"""Tests for jarvis-config-client."""

import pytest
from unittest.mock import patch, MagicMock

from jarvis_config_client import (
    init,
    shutdown,
    get_service_url,
    get_all_services,
    ConfigClient,
    ServiceConfig,
)


@pytest.fixture
def mock_services_response():
    """Mock response from config service."""
    return {
        "services": [
            {
                "name": "jarvis-auth",
                "host": "localhost",
                "port": 8007,
                "url": "http://localhost:8007",
                "health_path": "/health",
                "description": "Authentication service",
            },
            {
                "name": "jarvis-logs",
                "host": "localhost",
                "port": 8006,
                "url": "http://localhost:8006",
                "health_path": "/health",
                "description": "Logging service",
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
        client = ConfigClient(config_url="http://localhost:8013")
        services = client.fetch_services()

        assert len(services) == 2
        assert "jarvis-auth" in services
        assert "jarvis-logs" in services
        assert services["jarvis-auth"].url == "http://localhost:8007"
        assert services["jarvis-logs"].port == 8006

    def test_refresh_updates_cache(self, mock_httpx_client):
        """Test that refresh updates the internal cache."""
        client = ConfigClient(config_url="http://localhost:8013")

        assert len(client.get_all()) == 0

        success = client.refresh()

        assert success is True
        assert len(client.get_all()) == 2

    def test_get_url(self, mock_httpx_client):
        """Test getting URL for a specific service."""
        client = ConfigClient(config_url="http://localhost:8013")
        client.refresh()

        url = client.get_url("jarvis-auth")
        assert url == "http://localhost:8007"

        url = client.get_url("nonexistent")
        assert url is None

    def test_get_service(self, mock_httpx_client):
        """Test getting service config."""
        client = ConfigClient(config_url="http://localhost:8013")
        client.refresh()

        svc = client.get_service("jarvis-logs")
        assert isinstance(svc, ServiceConfig)
        assert svc.name == "jarvis-logs"
        assert svc.host == "localhost"
        assert svc.port == 8006


class TestGlobalFunctions:
    """Tests for module-level functions."""

    def teardown_method(self):
        """Clean up after each test."""
        shutdown()

    def test_init_with_url(self, mock_httpx_client):
        """Test init with explicit URL."""
        success = init(config_url="http://localhost:8013")
        assert success is True

    def test_init_without_url_raises(self):
        """Test init without URL raises ValueError."""
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="JARVIS_CONFIG_URL"):
                init()

    def test_get_service_url_before_init_raises(self):
        """Test get_service_url before init raises RuntimeError."""
        with pytest.raises(RuntimeError, match="not initialized"):
            get_service_url("jarvis-auth")

    def test_get_service_url_after_init(self, mock_httpx_client):
        """Test get_service_url after init works."""
        init(config_url="http://localhost:8013")

        url = get_service_url("jarvis-auth")
        assert url == "http://localhost:8007"

    def test_get_all_services_after_init(self, mock_httpx_client):
        """Test get_all_services after init works."""
        init(config_url="http://localhost:8013")

        services = get_all_services()
        assert len(services) == 2
        assert "jarvis-auth" in services
        assert "jarvis-logs" in services
