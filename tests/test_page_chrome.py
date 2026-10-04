# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""The chrome and the three tabs: what every view shares.

The rule is docs/what-it-shows.md, "The page": the ParkviewLab logo, the display
name with the service's version, the age of the data, and Refresh, above three
tabs. Opening the page and Refresh run both gathers; switching tabs gathers
nothing. The page is drawn first and filled in place when the gathers return.
"""

from __future__ import annotations

import asyncio
import re
from datetime import UTC, datetime

from nicegui import ui
from nicegui.testing import User

from hazel_tracking.config import DISPLAY_NAME, VERSION
from hazel_tracking.ui import theme
from tests import page_scenarios as scenarios
from tests.page_fixtures import Plan, content_of, dashboard_of, open_page, until


async def test_the_chrome_names_the_service_and_its_version(user: User, page_plan: Plan) -> None:
    await open_page(user, page_plan)
    name = content_of(user, "chrome-name")
    version = content_of(user, "chrome-version")
    assert DISPLAY_NAME in name
    assert f"v{VERSION}" in version
    assert f"v{VERSION}" not in name
    assert "Michroma" in name and "Michroma" in version


async def test_the_face_and_the_mark_are_embedded_and_never_fetched(user: User, page_plan: Plan) -> None:
    await open_page(user, page_plan)
    served = (await user.http_client.get("/")).text
    assert "data:font/woff2;base64," in served
    assert "fonts.googleapis.com" not in served
    assert "fonts.gstatic.com" not in served
    assert "<svg" in content_of(user, "brand-logo")


async def test_the_stylesheet_keeps_no_type_under_twelve_pixels(user: User, page_plan: Plan) -> None:
    await open_page(user, page_plan)
    sizes = [int(size) for size in re.findall(r"font-size:(\d+)px", theme.stylesheet())]
    sizes += [int(size) for size in re.findall(r"font-size:(\d+)px", content_of(user, "chrome-name"))]
    assert sizes
    assert min(sizes) >= theme.MINIMUM_TYPE_PX
    assert theme.MINIMUM_TYPE_PX == 12


async def test_the_age_advances_each_second(user: User, page_plan: Plan) -> None:
    moment = datetime.now(UTC)
    await open_page(user, page_plan, scenarios.live_like(moment))
    await user.should_see(content="gathered 0 s ago")
    await asyncio.sleep(1.2)
    await user.should_see(content="gathered 1 s ago")


async def test_the_page_is_drawn_before_a_gather_returns(user: User, page_plan: Plan) -> None:
    hold = page_plan.block()
    page_plan.load(scenarios.live_like(), scenarios.open_pull_requests())
    await user.open("/")
    await user.should_see(DISPLAY_NAME)
    await user.should_see(marker="spinner")
    assert content_of(user, "overview") == ""
    hold.set()
    await until(lambda: content_of(user, "overview") != "")
    await user.should_not_see(marker="spinner")


async def test_opening_the_page_runs_both_gathers(user: User, page_plan: Plan) -> None:
    await open_page(user, page_plan)
    assert page_plan.full_gathers == 1
    assert page_plan.pull_request_gathers == 1


async def test_refresh_runs_both_gathers_again(user: User, page_plan: Plan) -> None:
    await open_page(user, page_plan)
    user.find(marker="refresh").click()
    await until(lambda: page_plan.full_gathers == 2 and page_plan.pull_request_gathers == 2)


async def test_the_three_tabs_are_there_and_switching_gathers_nothing(user: User, page_plan: Plan) -> None:
    await open_page(user, page_plan)
    for name in ("Overview", "Detail", "Pull requests"):
        await user.should_see(name)
    user.find("Detail").click()
    user.find("Pull requests").click()
    user.find("Overview").click()
    await asyncio.sleep(0.1)
    assert page_plan.full_gathers == 1
    assert page_plan.pull_request_gathers == 1


async def test_refresh_covers_the_page_with_the_busy_spinner(user: User, page_plan: Plan) -> None:
    await open_page(user, page_plan)
    await user.should_not_see(marker="spinner")
    hold = page_plan.block()
    user.find(marker="refresh").click()
    await until(lambda: page_plan.full_gathers == 2)
    await user.should_see(marker="spinner")
    hold.set()
    await user.should_not_see(marker="spinner")


async def test_refresh_is_disabled_while_a_gather_runs(user: User, page_plan: Plan) -> None:
    await open_page(user, page_plan)
    hold = page_plan.block()
    user.find(marker="refresh").click()
    await until(lambda: page_plan.full_gathers == 2)
    (button,) = user.find(marker="refresh").elements
    assert not button.enabled
    hold.set()
    await until(lambda: button.enabled)


async def test_the_interactive_elements_are_only_those_the_page_names(user: User, page_plan: Plan) -> None:
    """The chrome's Refresh, the three tabs, the tab's Refresh and Watch, a Watch on each listed
    pull request, the information icon and the dialog's Close; the links are markup, not elements."""
    await open_page(user, page_plan, scenarios.failures())
    buttons = [element for element in user.client.layout.descendants() if isinstance(element, ui.button)]
    marks = sorted(mark for button in buttons for mark in button._markers)
    assert marks == sorted(
        [
            "refresh",
            "pull-requests-refresh",
            "watch",
            "status-icon",
            *[
                f"watch-{open_pull_request.repository}-{open_pull_request.pull_request.number}"
                for open_pull_request in scenarios.OPEN
            ],
        ]
    )
    assert len(buttons) == len(marks) + 1, "the dialog's Close is the one button without a mark"
    tabs = [element for element in user.client.layout.descendants() if isinstance(element, ui.tab)]
    assert len(tabs) == 3


async def test_a_page_closed_while_a_gather_runs_leaves_nothing_behind(user: User, page_plan: Plan) -> None:
    """The browser goes while a Refresh's gather is still out; what returns is dropped, and
    nothing is drawn for a client that is no longer there."""
    await open_page(user, page_plan)
    hold = page_plan.block()
    user.find(marker="refresh").click()
    await until(lambda: page_plan.full_gathers == 2)
    user.client.delete()
    hold.set()
    await asyncio.sleep(0.2)
    assert page_plan.full_gathers == 2


async def test_an_overtaken_gather_does_not_overwrite_a_newer_one(user: User, page_plan: Plan) -> None:
    """Two full gathers in flight at once: the older one's result is dropped when it returns, so
    the page keeps the newer, and the retries do not advance a step for a result nobody saw."""
    await open_page(user, page_plan)
    dashboard = dashboard_of(user)
    page_plan.load([scenarios.timed_out(), scenarios.live_like()])
    hold = page_plan.block()
    older = asyncio.create_task(dashboard._full_gather())
    await until(lambda: page_plan.full_gathers == 2)
    newer = asyncio.create_task(dashboard._full_gather())
    await until(lambda: page_plan.full_gathers == 3)
    hold.set()
    await asyncio.gather(older, newer)
    assert "Gathered from GitHub" in content_of(user, "status-sentence")
    assert "did not answer" not in content_of(user, "status-sentence")
