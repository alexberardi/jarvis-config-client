"""
Jarvis Config Client - Service discovery for jarvis microservices.

Usage:
    from jarvis_config_client import init, get_service_url, shutdown

    # Initialize once at startup
    init(config_url="http://localhost:8013")

    # Get service URLs throughout your app
    auth_url = get_service_url("jarvis-auth")
    logs_url = get_service_url("jarvis-logs")

    # Shutdown (stops background refresh)
    shutdown()
"""

from jarvis_config_client.client import (
    init,
    shutdown,
    get_service_url,
    get_all_services,
    refresh_services,
    ConfigClient,
    ServiceConfig,
)

__all__ = [
    "init",
    "shutdown",
    "get_service_url",
    "get_all_services",
    "refresh_services",
    "ConfigClient",
    "ServiceConfig",
]

__version__ = "0.1.0"
