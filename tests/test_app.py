# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""The app: its two ops endpoints, the token in neither, the page's `response_timeout`,
and the seam through which `install()` binds the gathering to the page.
What the page shows is the page's own tests' to check."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from nicegui import ui

from hazel_tracking import app as app_module
from hazel_tracking import gather as gather_module
from hazel_tracking import page as page_module
from hazel_tracking.app import default_http_client, install
from hazel_tracking.config import VERSION, Config
from hazel_tracking.model import Gather, Snapshot


def test_health_reports_the_version(app_client: TestClient) -> None:
    resp = app_client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"ok", "version", "uptime_seconds"}
    assert body["ok"] is True
    assert body["version"] == VERSION
    assert body["uptime_seconds"] >= 0


def test_admin_version_reports_the_name_the_version_and_every_setting_but_the_token(
    app_client: TestClient,
) -> None:
    resp = app_client.get("/admin/version")
    assert resp.status_code == 200
    assert resp.json() == {
        "name": "hazel-tracking",
        "version": VERSION,
        "host": "0.0.0.0",
        "port": 35999,
        "github_org": "ExampleOrg",
        "github_api_url": "http://github.invalid",
        "wait_seconds": 7.0,
        "time_zone": "Europe/London",
    }


@pytest.mark.parametrize("path", ["/health", "/admin/version"])
def test_the_token_is_in_neither_endpoint(app_client: TestClient, sentinel_token: str, path: str) -> None:
    resp = app_client.get(path)
    assert sentinel_token not in resp.text
    assert all(sentinel_token not in value for value in resp.headers.values())


def _registered_pages(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """Every `ui.page` registered from now on, whichever way it is called."""
    registered: list[Any] = []
    register = ui.page.__call__

    def record(self: Any, func: Callable[..., Any]) -> Callable[..., Any]:
        registered.append(self)
        return register(self, func)

    monkeypatch.setattr(ui.page, "__call__", record)
    return registered


@pytest.mark.parametrize(("wait", "timeout"), [(15.0, 20.0), (7.5, 12.5)])
def test_the_page_may_take_the_wait_and_five_seconds_to_build(
    monkeypatch: pytest.MonkeyPatch, sentinel_token: str, wait: float, timeout: float
) -> None:
    """NiceGUI's default `response_timeout` is 3 s; a gather may take the whole wait."""
    registered = _registered_pages(monkeypatch)
    install(Config(github_token=sentinel_token, wait_seconds=wait))
    [dashboard] = [p for p in registered if p.path == "/"]
    assert dashboard.response_timeout == timeout


async def test_the_default_client_carries_the_token_in_the_authorization_header_alone(
    sentinel_token: str,
) -> None:
    cfg = Config(github_token=sentinel_token, github_api_url="http://github.invalid", wait_seconds=4.0)
    sent: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200, json={})

    async with default_http_client(cfg, transport=httpx.MockTransport(answer)) as client:
        assert client.timeout == httpx.Timeout(4.0)
        await client.get("/rate_limit")
    [request] = sent
    assert str(request.url) == "http://github.invalid/rate_limit"
    assert request.headers["Authorization"] == f"Bearer {sentinel_token}"
    assert [name for name, value in request.headers.items() if sentinel_token in value] == ["authorization"]


def test_the_default_client_sends_no_authorization_without_a_token() -> None:
    request = default_http_client(Config()).build_request("GET", "/rate_limit")
    assert "Authorization" not in request.headers


async def test_install_binds_the_gathering_to_the_page_through_the_client_factory(
    monkeypatch: pytest.MonkeyPatch, sentinel_token: str
) -> None:
    """The page receives a zero-argument gather; it opens a client from the factory, gives it to
    `hazel_tracking.gather.gather` with the configuration, and closes it afterwards."""
    cfg = Config(github_token=sentinel_token)
    snapshot = Snapshot(
        began_at=datetime(2026, 9, 18, tzinfo=UTC),
        duration_seconds=0.0,
        completed=True,
        sources=("GitHub",),
        repositories=(),
        problems=(),
    )
    bound: list[Gather] = []
    calls: list[tuple[Config, httpx.AsyncClient]] = []
    clients: list[httpx.AsyncClient] = []

    async def fake_gather(given: Config, client: httpx.AsyncClient) -> Snapshot:
        calls.append((given, client))
        assert not client.is_closed
        return snapshot

    def factory() -> httpx.AsyncClient:
        client = default_http_client(cfg, transport=httpx.MockTransport(lambda _: httpx.Response(200)))
        clients.append(client)
        return client

    monkeypatch.setattr(gather_module, "gather", fake_gather)
    monkeypatch.setattr(page_module, "register", lambda _cfg, gather: bound.append(gather))
    install(cfg, http_client_factory=factory)

    [page_gather] = bound
    assert await page_gather() is snapshot
    assert await page_gather() is snapshot
    assert [given for given, _ in calls] == [cfg, cfg]
    assert [client for _, client in calls] == clients
    assert all(client.is_closed for client in clients)


def test_a_gather_given_to_install_is_the_one_the_page_receives(monkeypatch: pytest.MonkeyPatch) -> None:
    bound: list[Gather] = []

    async def stub() -> Snapshot:
        raise AssertionError("not called here")

    monkeypatch.setattr(page_module, "register", lambda _cfg, gather: bound.append(gather))
    install(Config(), gather=stub)
    assert bound == [stub]


def test_the_gathering_s_entry_point_has_the_contract_s_signature() -> None:
    assert inspect.iscoroutinefunction(gather_module.gather)
    assert list(inspect.signature(gather_module.gather).parameters) == ["cfg", "client"]
    assert app_module.install.__kwdefaults__ == {"gather": None, "http_client_factory": None}
