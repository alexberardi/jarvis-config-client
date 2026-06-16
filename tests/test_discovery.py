"""Tests for network discovery of jarvis-config-service."""

import pytest
from unittest.mock import patch, MagicMock

from jarvis_config_client.discovery import (
    discover_config_service,
    _probe_config_service,
    _get_local_ip,
    _scan_subnet,
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
        mock_probe.return_value = "http://localhost:7700"
        with patch.dict("os.environ", {}, clear=True):
            result = discover_config_service()
            assert result == "http://localhost:7700"
            mock_probe.assert_called_once_with("http://localhost:7700", 2.0)

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
            mock_scan.assert_called_once_with("192.168.1.100", 7700, 2.0)

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


class TestGetLocalIp:
    """Tests for _get_local_ip."""

    def test_returns_ip_address(self):
        """Test _get_local_ip returns an IP when socket succeeds."""
        mock_socket = MagicMock()
        mock_socket.getsockname.return_value = ("192.168.1.100", 0)
        with patch("jarvis_config_client.discovery.socket.socket") as mock_sock_cls:
            mock_sock_cls.return_value.__enter__ = MagicMock(return_value=mock_socket)
            mock_sock_cls.return_value.__exit__ = MagicMock(return_value=False)
            result = _get_local_ip()
        assert result == "192.168.1.100"

    def test_returns_none_on_error(self):
        """Test _get_local_ip returns None on OSError."""
        with patch("jarvis_config_client.discovery.socket.socket") as mock_sock_cls:
            mock_sock_cls.return_value.__enter__ = MagicMock(
                side_effect=OSError("no network")
            )
            mock_sock_cls.return_value.__exit__ = MagicMock(return_value=False)
            result = _get_local_ip()
        assert result is None


class TestScanSubnet:
    """Tests for _scan_subnet."""

    @patch("jarvis_config_client.discovery._probe_config_service")
    def test_finds_service_on_subnet(self, mock_probe):
        """Test _scan_subnet finds a service."""
        def probe_side_effect(url, timeout):
            if "192.168.1.50" in url:
                return url
            return None

        mock_probe.side_effect = probe_side_effect
        result = _scan_subnet("192.168.1.100", 8013, 2.0)
        assert result is not None
        assert "192.168.1.50" in result

    @patch("jarvis_config_client.discovery._probe_config_service")
    def test_returns_none_when_no_service(self, mock_probe):
        """Test _scan_subnet returns None when nothing found."""
        mock_probe.return_value = None
        result = _scan_subnet("192.168.1.100", 8013, 0.01)
        assert result is None

    @patch("jarvis_config_client.discovery._probe_config_service")
    def test_skips_local_ip(self, mock_probe):
        """Test _scan_subnet skips the local IP address."""
        calls = []
        def probe_side_effect(url, timeout):
            calls.append(url)
            return None

        mock_probe.side_effect = probe_side_effect
        _scan_subnet("192.168.1.100", 8013, 0.01)
        # The local IP should not be probed
        assert "http://192.168.1.100:8013" not in calls
