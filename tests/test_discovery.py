"""Tests for network discovery of jarvis-config-service."""

import pytest
from unittest.mock import patch, MagicMock

from jarvis_config_client.discovery import (
    discover_config_service,
    _probe_config_service,
    _get_local_ip,
)


class TestProbeConfigService:
    """Tests for _probe_config_service."""

    def test_returns_url_on_valid_response(self):
        with patch("jarvis_config_client.discovery.httpx.Client") as mock:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"service": "jarvis-config-service"}

            mock_instance = MagicMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__enter__ = MagicMock(return_value=mock_instance)
            mock_instance.__exit__ = MagicMock(return_value=False)
            mock.return_value = mock_instance

            result = _probe_config_service("http://localhost:8013", timeout=2.0)
            assert result == "http://localhost:8013"

    def test_returns_none_on_wrong_service(self):
        with patch("jarvis_config_client.discovery.httpx.Client") as mock:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"service": "some-other-service"}

            mock_instance = MagicMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__enter__ = MagicMock(return_value=mock_instance)
            mock_instance.__exit__ = MagicMock(return_value=False)
            mock.return_value = mock_instance

            result = _probe_config_service("http://localhost:8013", timeout=2.0)
            assert result is None

    def test_returns_none_on_connection_error(self):
        import httpx
        with patch("jarvis_config_client.discovery.httpx.Client") as mock:
            mock_instance = MagicMock()
            mock_instance.get.side_effect = httpx.ConnectError("refused")
            mock_instance.__enter__ = MagicMock(return_value=mock_instance)
            mock_instance.__exit__ = MagicMock(return_value=False)
            mock.return_value = mock_instance

            result = _probe_config_service("http://localhost:8013", timeout=2.0)
            assert result is None


class TestDiscoverConfigService:
    """Tests for discover_config_service."""

    def test_returns_env_var_first(self):
        with patch.dict("os.environ", {"JARVIS_CONFIG_URL": "http://10.0.0.1:8013"}):
            result = discover_config_service()
            assert result == "http://10.0.0.1:8013"

    @patch("jarvis_config_client.discovery._probe_config_service")
    def test_probes_localhost_second(self, mock_probe):
        mock_probe.return_value = "http://localhost:8013"
        with patch.dict("os.environ", {}, clear=True):
            result = discover_config_service()
            assert result == "http://localhost:8013"
            mock_probe.assert_called_once_with("http://localhost:8013", 2.0)

    @patch("jarvis_config_client.discovery._scan_subnet")
    @patch("jarvis_config_client.discovery._get_local_ip")
    @patch("jarvis_config_client.discovery._probe_config_service")
    def test_scans_subnet_when_localhost_fails(self, mock_probe, mock_ip, mock_scan):
        mock_probe.return_value = None
        mock_ip.return_value = "192.168.1.100"
        mock_scan.return_value = "http://192.168.1.50:8013"

        with patch.dict("os.environ", {}, clear=True):
            result = discover_config_service()
            assert result == "http://192.168.1.50:8013"
            mock_scan.assert_called_once_with("192.168.1.100", 8013, 2.0)

    @patch("jarvis_config_client.discovery._get_local_ip")
    @patch("jarvis_config_client.discovery._probe_config_service")
    def test_returns_none_when_nothing_found(self, mock_probe, mock_ip):
        mock_probe.return_value = None
        mock_ip.return_value = None

        with patch.dict("os.environ", {}, clear=True):
            result = discover_config_service()
            assert result is None

    def test_respects_config_port_env(self):
        with patch.dict("os.environ", {"JARVIS_CONFIG_PORT": "9999"}, clear=True):
            with patch("jarvis_config_client.discovery._probe_config_service") as mock_probe:
                mock_probe.return_value = "http://localhost:9999"
                result = discover_config_service()
                assert result == "http://localhost:9999"
                mock_probe.assert_called_once_with("http://localhost:9999", 2.0)
