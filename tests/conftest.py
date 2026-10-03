# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Shared fixtures.

The gathering's fixtures live in `tests/gh_fixtures.py` and the page's in
`tests/page_fixtures.py`, loaded below as plugins beside NiceGUI's user plugin
(`user_plugin`, not `plugin`, which imports selenium), so that neither adds to
this file; their names carry the prefixes `gh_` and `page_`.

`sentinel_token` stands for the GitHub token wherever a test needs one, so that a
test can prove the token is shown nowhere by looking for it.
"""

from __future__ import annotations

from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from nicegui import app

from hazel_tracking.app import install
from hazel_tracking.config import Config


@pytest.fixture
def sentinel_token() -> str:
    return "sentinel-github-token-3f9d0c"


@pytest.fixture
def app_config(sentinel_token: str) -> Config:
    """A configuration whose every setting differs from its default, the token a sentinel."""
    return Config(
        host="0.0.0.0",
        port=35999,
        github_token=sentinel_token,
        github_org="ExampleOrg",
        github_api_url="http://github.invalid",
        wait_seconds=7.0,
        time_zone=ZoneInfo("Europe/London"),
    )


@pytest.fixture
def app_client(app_config: Config) -> TestClient:
    """NiceGUI's app with hazel-tracking installed under `app_config`, without its lifespan:
    NiceGUI's startup wants a running `ui.run()`, and the ops endpoints need none of it."""
    install(app_config)
    return TestClient(app, base_url="http://localhost")


pytest_plugins = ["nicegui.testing.user_plugin", "tests.gh_fixtures", "tests.page_fixtures"]
