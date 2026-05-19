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
init(config_url="http://localhost:7700")

# Get service URLs
auth_url = get_service_url("jarvis-auth")
logs_url = get_service_url("jarvis-logs")
```

## With Database Persistence

```python
from sqlalchemy import create_engine
from jarvis_config_client import init

engine = create_engine("postgresql://...")
init(config_url="http://localhost:7700", db_engine=engine)
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

## Invariants & gotchas

1. **Call `init()` exactly once at service startup.** Subsequent calls are a no-op; changing the config URL at runtime requires restart.
2. **`get_service_url()` is in-process cached.** First call populates the cache; subsequent calls hit memory. Cache is refreshed in the background every 5 minutes — that's the lag on stale data.
3. **DB persistence is optional but recommended in prod.** Pass `db_engine` so the cache survives restarts. Without it, every cold start refetches from config-service. If config-service is also cold-starting at the same time (e.g. compose-up), the consumer may get a stale fallback or fail outright.
4. **No URL fallbacks beyond what's cached.** If you want `localhost:7702` to work when config-service is unreachable, you need an env-var fallback in *your* code — this library won't fabricate URLs.
5. **Returned URLs may be dockerized or remote-style** depending on how config-service was queried (via `?style=dockerized`/`?style=remote`). This library doesn't rewrite — what you get is what config-service returned. If you need a different style, query config-service directly with the right query param.

## Used by

Every Python service in the stack. Mounting pattern lives in each service's `service_config.py`:
```python
from jarvis_config_client import init, get_service_url
# In FastAPI startup:
init(config_url=os.getenv("JARVIS_CONFIG_URL"), db_engine=db_engine)
```

## Stability

`0.1.0`. Public API (`init`, `shutdown`, `get_service_url`) is stable; breaking changes will bump to `1.0.0`. Internal implementation may change between minor versions.
