# jarvis-config-client

Python library for service discovery in jarvis microservices. Fetches service URLs from jarvis-config-service.

## Quick Reference

```bash
# Install
pip install -e .

# Test
pytest
```

## Usage

```python
from jarvis_config_client import init, get_service_url

# Initialize once at startup
init(config_url="http://localhost:8013")

# Get service URLs
auth_url = get_service_url("jarvis-auth")
logs_url = get_service_url("jarvis-logs")
```

## With Database Persistence

```python
from sqlalchemy import create_engine
from jarvis_config_client import init

engine = create_engine("postgresql://...")
init(config_url="http://localhost:8013", db_engine=engine)
```

## Architecture

```
jarvis_config_client/
├── __init__.py    # Public API
└── client.py      # Core client with caching and refresh
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `JARVIS_CONFIG_URL` | Config service URL (default for init()) |

## Features

- In-memory caching of service URLs
- Optional PostgreSQL/SQLite persistence
- Background refresh every 5 minutes
- Fallback to cached values on failure
- Thread-safe

## Version

0.1.0
