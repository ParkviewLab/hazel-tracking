# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""The NiceGUI application: the handbook's two ops endpoints, the page, `install()` and `run()`.

`install()` registers everything on NiceGUI's app and is what `__main__` calls
before `run()`; the tests call it too. It binds the gathering to the page: the
page awaits a zero-argument `Gather`, which here opens one `httpx.AsyncClient`
from `http_client_factory`, runs `hazel_tracking.gather.gather` with it and
closes it. A test passes a stub `gather` for the page, or a factory whose
client talks to a fake GitHub through an `httpx` transport.

The token travels only in the client's `Authorization` header; neither endpoint
reports it, and nothing here logs it.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypedDict

import httpx
from nicegui import app, ui

from hazel_tracking import gather as gathering
from hazel_tracking import page
from hazel_tracking.config import DISPLAY_NAME, NAME, VERSION, Config
from hazel_tracking.model import Gather, Snapshot

_started_at = time.monotonic()


class Health(TypedDict):
    ok: bool
    version: str
    uptime_seconds: float


class Identity(TypedDict):
    """The name, the version and every setting but the token."""

    name: str
    version: str
    host: str
    port: int
    github_org: str
    github_api_url: str
    wait_seconds: float
    time_zone: str


def default_http_client(cfg: Config, transport: httpx.AsyncBaseTransport | None = None) -> httpx.AsyncClient:
    """The client the gathering reads through: `cfg.github_api_url`, the token in the
    `Authorization` header alone, and no call allowed longer than the wait.

    `transport` replaces the network, for a test.
    """
    headers = {"User-Agent": f"{NAME}/{VERSION}"}
    if cfg.github_token:
        headers["Authorization"] = f"Bearer {cfg.github_token}"
    return httpx.AsyncClient(
        base_url=cfg.github_api_url,
        headers=headers,
        timeout=httpx.Timeout(cfg.wait_seconds),
        transport=transport,
    )


def _register_routes(cfg: Config) -> None:
    """The ops endpoints; idempotent, so a second install after a test's reset is clean."""
    for path in ("/health", "/admin/version"):
        app.remove_route(path)

    @app.get("/health", tags=["health"])
    async def health() -> Health:
        return Health(ok=True, version=VERSION, uptime_seconds=time.monotonic() - _started_at)

    @app.get("/admin/version", tags=["admin"])
    async def admin_version() -> Identity:
        return Identity(
            name=NAME,
            version=VERSION,
            host=cfg.host,
            port=cfg.port,
            github_org=cfg.github_org,
            github_api_url=cfg.github_api_url,
            wait_seconds=cfg.wait_seconds,
            time_zone=cfg.time_zone.key,
        )


def install(
    cfg: Config,
    *,
    gather: Gather | None = None,
    http_client_factory: Callable[[], httpx.AsyncClient] | None = None,
) -> None:
    """Register the app on NiceGUI's app: the two ops endpoints and the page.

    `gather` is what the page awaits for a snapshot; by default it is the gathering,
    reading through a client from `http_client_factory`, whose default is
    `default_http_client(cfg)`. A `gather` given here makes the factory unused.
    """
    if gather is None:
        factory = http_client_factory or (lambda: default_http_client(cfg))

        async def gather_snapshot() -> Snapshot:
            async with factory() as client:
                return await gathering.gather(cfg, client)

        gather = gather_snapshot

    _register_routes(cfg)
    page.register(cfg, gather)


def run(cfg: Config) -> None:
    """Start the server. `reload=False`: the image runs one process, and reloading needs a file watcher."""
    ui.run(
        host=cfg.host,
        port=cfg.port,
        title=DISPLAY_NAME,
        reload=False,
        show=False,
        show_welcome_message=False,
    )
