# jarvis-config-client

Python library for service discovery in the jarvis ecosystem. Fetches service URLs from `jarvis-config-service`, caches them locally, and provides background refresh.

## Installation

```bash
# Basic installation
pip install -e .

# With PostgreSQL support
pip install -e ".[postgres]"
```

## Quick Start

```python
from jarvis_config_client import init, get_service_url, shutdown

# Initialize once at startup
init(config_url="http://localhost:8013")

# Get service URLs anywhere in your app
auth_url = get_service_url("jarvis-auth")
logs_url = get_service_url("jarvis-logs")
llm_url = get_service_url("jarvis-llm-proxy")

# Shutdown when done (stops background refresh)
shutdown()
```

## With Database Persistence

For services with a database, you can persist cached URLs for faster startup and fallback when the config service is unavailable:

```python
from sqlalchemy import create_engine
from jarvis_config_client import init, get_service_url

# Create your database engine
engine = create_engine("postgresql://user:pass@localhost:5432/mydb")

# Initialize with database persistence
init(
    config_url="http://localhost:8013",
    db_engine=engine,
    refresh_interval_seconds=300,  # Refresh every 5 minutes
)

# Use normally
auth_url = get_service_url("jarvis-auth")
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `JARVIS_CONFIG_URL` | - | URL of jarvis-config-service |

## Features

- **Automatic caching**: Service URLs cached in memory
- **Database persistence**: Optional SQLAlchemy integration for persistent cache
- **Background refresh**: URLs refreshed every 5 minutes (configurable)
- **Fallback**: Uses cached values if config service is unavailable
- **Thread-safe**: Safe for multi-threaded applications
- **Graceful shutdown**: Automatically stops background thread on exit

## API Reference

### `init(config_url=None, refresh_interval_seconds=300, db_engine=None, on_refresh=None)`

Initialize the config client. Must be called before other functions.

- `config_url`: Config service URL (defaults to `JARVIS_CONFIG_URL` env var)
- `refresh_interval_seconds`: Background refresh interval (default: 300)
- `db_engine`: SQLAlchemy engine for persistent caching
- `on_refresh`: Callback function when services are refreshed

### `get_service_url(name)`

Get URL for a specific service by name.

```python
url = get_service_url("jarvis-auth")  # Returns "http://localhost:8007"
```

### `get_all_services()`

Get all cached services as a dict.

```python
services = get_all_services()
for name, config in services.items():
    print(f"{name}: {config.url}")
```

### `refresh_services()`

Manually trigger a refresh from the config service.

### `shutdown()`

Stop the background refresh thread. Called automatically on exit.

## Service Names

Use the `jarvis-` prefix for all service names:

- `jarvis-auth`
- `jarvis-command-center`
- `jarvis-llm-proxy`
- `jarvis-logs`
- `jarvis-whisper`
- `jarvis-recipes`
- `jarvis-ocr`
- `jarvis-tts`
- `jarvis-config`
