# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""The pull-requests tab: the list, its own gather time and its own Refresh.

The rule is docs/what-it-shows.md, "The pull requests": every open pull request
into a repository's integration trunk across the organisation, each with its
repository, its number and title linked to it, and its status; the tab carries
the time of its own gather, and its Refresh gathers the open pull requests alone.
"""

from __future__ import annotations

import asyncio

from nicegui import ui
from nicegui.testing import User

from hazel_tracking.ui import theme
from hazel_tracking.ui.pull_requests_view import COLUMNS, key_of
from tests import page_scenarios as scenarios
from tests.page_fixtures import Plan, content_of, open_page, until


async def open_tab(user: User, page_plan: Plan, **loaded: object) -> None:
    await open_page(user, page_plan, **loaded)  # type: ignore[arg-type]
    user.find("Pull requests").click()
    await asyncio.sleep(0.05)


async def test_every_open_pull_request_is_listed_with_its_repository_and_status(
    user: User, page_plan: Plan
) -> None:
    await open_tab(user, page_plan)
    await user.should_see(content="#61 feat: the atlas generator")
    await user.should_see(content="conception-space")
    await user.should_see(content="ready to merge")
    await user.should_see(content="https://github.com/ParkviewLab/deco-assaying/pull/24")


async def test_the_tab_carries_the_time_of_its_own_gather(user: User, page_plan: Plan) -> None:
    await open_tab(user, page_plan)
    await user.should_see(content="gathered at 14:03:12 in 0.7 s")


async def test_its_refresh_gathers_the_open_pull_requests_alone(user: User, page_plan: Plan) -> None:
    await open_tab(user, page_plan)
    user.find(marker="pull-requests-refresh").click()
    await until(lambda: page_plan.pull_request_gathers == 2)
    assert page_plan.full_gathers == 1


async def test_a_search_that_did_not_answer_is_greyed(user: User, page_plan: Plan) -> None:
    await open_tab(user, page_plan, pull_requests=scenarios.pull_requests_not_gathered())
    await user.should_see(content="The open pull requests could not be gathered")
    await user.should_see(content="ungathered")


async def test_no_open_pull_request_reads_plainly(user: User, page_plan: Plan) -> None:
    await open_tab(user, page_plan, pull_requests=scenarios.pull_requests_snapshot([]))
    await user.should_see("No pull request is open.")


async def test_every_line_carries_a_watch_of_its_own(user: User, page_plan: Plan) -> None:
    await open_tab(user, page_plan)
    user.find(marker="watch-ParkviewLab/hazel-tracking-2")


async def test_its_refresh_fills_the_tabs_frame_with_a_spinner_and_leaves_the_chrome(
    user: User, page_plan: Plan
) -> None:
    await open_tab(user, page_plan)
    hold = page_plan.block_pull_requests()
    user.find(marker="pull-requests-refresh").click()
    await until(lambda: page_plan.pull_request_gathers == 2)
    await user.should_see(marker="tab-spinner")
    await user.should_not_see(marker="spinner")
    (refresh,) = user.find(marker="refresh").elements
    assert refresh.enabled, "the chrome stays usable while the open pull requests are gathered"
    user.find("Overview").click()
    assert user.find(marker="overview")
    hold.set()
    await user.should_not_see(marker="tab-spinner")


async def test_closing_the_page_stops_the_watch(user: User, page_plan: Plan) -> None:
    await open_tab(user, page_plan, pull_requests=scenarios.watch_times_out())
    user.find(marker="watch").click()
    await until(lambda: page_plan.pull_request_gathers >= 2)
    user.client.delete()
    gathered = page_plan.pull_request_gathers
    await asyncio.sleep(0.2)
    assert page_plan.pull_request_gathers <= gathered + 1


async def test_a_gather_that_raised_at_the_page_s_opening_is_shown_as_not_gathered(
    user: User, page_plan: Plan
) -> None:
    page_plan.load(scenarios.live_like(), scenarios.open_pull_requests())
    page_plan.pull_requests_raise = RuntimeError("the search was refused")
    await user.open("/")
    await until(lambda: page_plan.pull_request_gathers >= 1)
    user.find("Pull requests").click()
    await user.should_see(content="The open pull requests could not be gathered")
    await user.should_see(marker="status-icon")


async def test_a_gather_that_raised_at_its_refresh_is_shown_as_not_gathered(
    user: User, page_plan: Plan
) -> None:
    await open_tab(user, page_plan)
    page_plan.pull_requests_raise = RuntimeError("the search was refused")
    user.find(marker="pull-requests-refresh").click()
    await until(lambda: page_plan.pull_request_gathers == 2)
    await user.should_see(content="The open pull requests could not be gathered")
    user.find(marker="status-icon").click()
    assert "the error was a RuntimeError" in content_of(user, "status-dialog")


async def test_a_line_s_own_watch_carries_no_type_under_twelve_pixels(user: User, page_plan: Plan) -> None:
    """Its size is set in the stylesheet, not by the button's own `size`, which would be 10 px."""
    await open_tab(user, page_plan)
    (button,) = user.find(marker="watch-ParkviewLab/hazel-tracking-2").elements
    assert "size" not in button.props
    assert ".prcol-watch .q-btn { font-size:12px;" in theme.stylesheet()


async def test_the_links_are_not_sanitised_so_that_they_open_beside_the_dashboard(
    user: User, page_plan: Plan
) -> None:
    """The sanitiser drops a link's target, and a pull request opened in place of the Dashboard
    would end the watch the reader started; every value in the markup is escaped in `cells`."""
    await open_tab(user, page_plan)
    listed = [
        element
        for element in user.client.layout.descendants()
        if isinstance(element, ui.html) and _in_column(element, "title")
    ]
    assert listed
    for element in listed:
        assert element.props["sanitize"] is False
    assert [element for element in listed if 'target="_blank"' in element.content]


def _in_column(element: ui.element, column: str) -> bool:
    """Whether the element stands in the list's named column."""
    return any(f"prcol-{column}" in ancestor.classes for ancestor in element.ancestors())


async def test_the_list_is_one_table_as_wide_as_the_tab_with_the_watch_in_its_own_column(
    user: User, page_plan: Plan
) -> None:
    """Every line's Watch stands in the same fixed column at the right, as the detail's columns
    align: a table of fixed layout, every row four cells, the button always in the last."""
    await open_tab(user, page_plan, pull_requests=scenarios.open_pull_requests())
    (table,) = user.find(marker="pull-requests-table").elements
    assert table.tag == "table"
    assert "sheet" in table.classes and "prlist" in table.classes
    rows = [element for element in table.descendants() if element.tag == "tr"]
    assert len(rows) == len(scenarios.OPEN) + 1, "one header row and one row per pull request"
    for row in rows:
        columns = [child for child in row.descendants() if child.tag in ("td", "th")]
        assert [name for _, name in COLUMNS] == [
            class_name.removeprefix("prcol-")
            for cell in columns
            for class_name in cell.classes
            if class_name.startswith("prcol-")
        ]
    for open_pull_request in scenarios.OPEN:
        key = key_of(open_pull_request)
        (button,) = user.find(marker=f"watch-{key[0]}-{key[1]}").elements
        assert _in_column(button, "watch")
    css = theme.stylesheet()
    assert "table.sheet.prlist { table-layout:fixed; }" in css
    assert "table.sheet.prlist .prcol-watch { width:110px; text-align:right; }" in css
    assert "table.sheet.prlist .prcol-title { width:auto; white-space:normal;" in css
    assert "table.sheet th" in css and "width:100%" in css
