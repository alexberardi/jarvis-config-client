"""init() must never leave more than one background refresh thread alive.

Regression for a slow thread leak on a jarvis node whose config-service was
down: several threads (voice loop, MQTT connect loop, service resolvers) each
retry ``init()``. Two concurrent calls both read the same old ``_client``,
both stopped it, and each built and started a new one, so the client that lost
the race kept its ``jarvis-config-refresh`` thread forever. py-spy on a Pi 4
showed 9 live refresh threads after 50 minutes.
"""

import atexit
import threading
from unittest.mock import patch

import httpx
import pytest

import jarvis_config_client.client as client_mod


def _refresh_threads() -> list[threading.Thread]:
    return [
        t for t in threading.enumerate()
        if t.name == "jarvis-config-refresh" and t.is_alive()
    ]


def _refused(*_a, **_kw):
    raise httpx.ConnectError("[Errno 111] Connection refused")


@pytest.fixture(autouse=True)
def _clean_global():
    client_mod.shutdown()
    yield
    client_mod.shutdown()


class TestInitConcurrency:
    def test_concurrent_init_leaves_one_refresh_thread(self):
        """Many threads retrying init() at once against a dead server."""
        start = threading.Barrier(8)

        def worker() -> None:
            start.wait()
            for _ in range(20):
                client_mod.init(config_url="http://localhost:1")

        with patch.object(client_mod.ConfigClient, "fetch_services", side_effect=_refused):
            threads = [threading.Thread(target=worker) for _ in range(8)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=30)

        assert len(_refresh_threads()) <= 1

    def test_repeated_init_leaves_one_refresh_thread(self):
        with patch.object(client_mod.ConfigClient, "fetch_services", side_effect=_refused):
            for _ in range(50):
                client_mod.init(config_url="http://localhost:1")

        assert len(_refresh_threads()) == 1
        client_mod.shutdown()
        assert _refresh_threads() == []

    def test_repeated_init_registers_atexit_once(self):
        with patch.object(client_mod.ConfigClient, "fetch_services", side_effect=_refused), \
                patch.object(atexit, "register") as register:
            for _ in range(50):
                client_mod.init(config_url="http://localhost:1")

        assert register.call_count <= 1
