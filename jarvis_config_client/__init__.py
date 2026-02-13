"""
Jarvis Config Client - Service discovery for jarvis microservices.

Usage:
    from jarvis_config_client import init, get_service_url, shutdown

    # Initialize once at startup (auto-discovers config-service)
    init()

    # Get service URLs throughout your app
    auth_url = get_service_url("auth")
    logs_url = get_service_url("logs")

    # Or use named helpers
    from jarvis_config_client import get_auth_url, get_logs_url
    auth_url = get_auth_url()

    # Shutdown (stops background refresh)
    shutdown()
"""

from jarvis_config_client.client import (
    ConfigClient,
    ConfigServiceNotFoundError,
    ServiceConfig,
    ServiceNotFoundError,
    get_all_services,
    get_auth_url,
    get_command_center_url,
    get_llm_proxy_url,
    get_logs_url,
    get_mcp_url,
    get_mqtt_broker_url,
    get_ocr_url,
    get_recipes_url,
    get_service_url,
    get_tts_url,
    get_whisper_url,
    init,
    refresh_services,
    require_service_url,
    shutdown,
)
from jarvis_config_client.discovery import discover_config_service

__all__ = [
    "init",
    "shutdown",
    "get_service_url",
    "require_service_url",
    "get_all_services",
    "refresh_services",
    "discover_config_service",
    "ConfigClient",
    "ConfigServiceNotFoundError",
    "ServiceConfig",
    "ServiceNotFoundError",
    # Named helpers
    "get_auth_url",
    "get_command_center_url",
    "get_llm_proxy_url",
    "get_whisper_url",
    "get_tts_url",
    "get_logs_url",
    "get_ocr_url",
    "get_recipes_url",
    "get_mcp_url",
    "get_mqtt_broker_url",
]

__version__ = "0.2.0"
