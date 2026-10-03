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

from nicegui.testing import User

from hazel_tracking.config import DISPLAY_NAME, VERSION
from hazel_tracking.ui import theme
from tests import page_scenarios as scenarios
from tests.page_fixtures import Plan, content_of, open_page, until


async def test_the_chrome_names_the_service_and_its_version(user: User, page_plan: Plan) -> None:
    await open_page(user, page_plan)
    label = content_of(user, "chrome-name")
    assert DISPLAY_NAME in label
    assert f"v{VERSION}" in label
    assert "Michroma" in label


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
    assert sizes
    assert min(sizes) >= theme.MINIMUM_TYPE_PX


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
