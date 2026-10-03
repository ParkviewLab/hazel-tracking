# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""No secret on the page, anywhere (axiom 6).

The page is installed under a configuration whose token is a sentinel, so that a
test can look for that exact value in everything a browser is sent: the served
document, every element's words, the status bar's sentence and the dialog behind
its icon. The credential may be named in general terms, and these tests hold the
page to that: the words "token" and "GitHub token" are expected where the status
bar reports the expiry, and the value never is.
"""

from __future__ import annotations

from nicegui.testing import User

from hazel_tracking.config import TOKEN_VARIABLE
from tests import page_scenarios as scenarios
from tests.page_fixtures import (
    PAGE_CONFIG,
    SENTINEL_TOKEN,
    Plan,
    content_of,
    everything_shown,
    open_page,
    until,
)


def test_the_sentinel_is_the_one_conftest_gives(sentinel_token: str) -> None:
    assert sentinel_token == SENTINEL_TOKEN


def test_the_page_runs_under_a_configuration_that_holds_the_token() -> None:
    assert PAGE_CONFIG.github_token == SENTINEL_TOKEN, "the test proves nothing without it"


async def test_the_token_is_nowhere_on_the_page(user: User, page_plan: Plan) -> None:
    await open_page(user, page_plan)
    served = (await user.http_client.get("/")).text
    assert SENTINEL_TOKEN not in served
    assert SENTINEL_TOKEN not in everything_shown(user)


async def test_the_token_is_not_in_the_status_bar_or_its_dialog(user: User, page_plan: Plan) -> None:
    await open_page(user, page_plan, scenarios.failures())
    user.find(marker="status-icon").click()
    assert SENTINEL_TOKEN not in content_of(user, "status-sentence")
    assert SENTINEL_TOKEN not in content_of(user, "status-dialog")
    assert SENTINEL_TOKEN not in everything_shown(user)


async def test_a_gather_that_raised_with_the_token_in_its_message_shows_neither(
    user: User, page_plan: Plan
) -> None:
    page_plan.load(scenarios.live_like(), scenarios.open_pull_requests())
    page_plan.full_raises = RuntimeError(f"Bearer {SENTINEL_TOKEN} was refused")
    await user.open("/")
    await until(lambda: "The gather failed" in content_of(user, "status-sentence"))
    user.find(marker="status-icon").click()
    assert SENTINEL_TOKEN not in everything_shown(user)
    assert SENTINEL_TOKEN not in (await user.http_client.get("/")).text


async def test_the_credential_is_named_in_general_terms_alone(user: User, page_plan: Plan) -> None:
    await open_page(user, page_plan)
    sentence = content_of(user, "status-sentence")
    assert "the GitHub token expires in" in sentence
    assert TOKEN_VARIABLE not in everything_shown(user)


async def test_a_pull_request_gather_that_raised_with_the_token_shows_neither(
    user: User, page_plan: Plan
) -> None:
    page_plan.load(scenarios.live_like(), scenarios.open_pull_requests())
    page_plan.pull_requests_raise = RuntimeError(f"Bearer {SENTINEL_TOKEN} was refused")
    await user.open("/")
    await until(lambda: "could not be gathered" in content_of(user, "status-sentence"))
    user.find(marker="status-icon").click()
    assert SENTINEL_TOKEN not in everything_shown(user)
    assert SENTINEL_TOKEN not in (await user.http_client.get("/")).text
