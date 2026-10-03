# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""The Watch, and every rule by which it stops.

The rule is docs/what-it-shows.md, "The pull requests": the watch gathers the
open pull requests every `watch_interval_seconds` and stops when the set of open
pull requests changes, after `watch_limit_seconds`, when the reader leaves the
tab, and when the page is closed; started from one pull request's row it also
stops when that pull request's status changes. It marks the browser tab's title
when it stops on a change, and it shows no spinner, its button saying instead
that it is watching.

The comparison itself is read directly, since it is a pure function of two
snapshots; the page's tests then prove that the watch is wired to it.
"""

from __future__ import annotations

import asyncio

from nicegui.testing import User

from hazel_tracking.config import DISPLAY_NAME
from hazel_tracking.ui import watch as watching
from tests import page_scenarios as scenarios
from tests.page_fixtures import Plan, content_of, open_page, until

HAZEL = (scenarios.full("hazel-tracking"), 2)


async def open_tab(user: User, page_plan: Plan, **loaded: object) -> None:
    await open_page(user, page_plan, **loaded)  # type: ignore[arg-type]
    user.find("Pull requests").click()
    await asyncio.sleep(0.05)


# The comparison.


def test_an_arriving_pull_request_is_a_change_and_names_itself() -> None:
    before, after = scenarios.watch_sees_a_change()
    stop = watching.set_change(before, after)
    assert stop is not None
    assert stop.reason is watching.StopReason.SET_CHANGED
    assert stop.title_mark == "1 new pull request"
    assert stop.detail == "handbook #12 arrived"


def test_a_departing_pull_request_is_a_change() -> None:
    before = scenarios.pull_requests_snapshot(scenarios.OPEN)
    after = scenarios.pull_requests_snapshot(scenarios.OPEN[:-1])
    stop = watching.set_change(before, after)
    assert stop is not None
    assert stop.title_mark == "1 pull request closed"
    assert stop.detail == "hazel-tracking #3 is no longer open"


def test_an_unchanged_set_is_no_change() -> None:
    before, after = scenarios.watch_times_out()[:2]
    assert watching.set_change(before, after) is None


def test_a_search_that_did_not_answer_is_no_change() -> None:
    before = scenarios.pull_requests_snapshot(scenarios.OPEN)
    assert watching.set_change(before, scenarios.pull_requests_not_gathered()) is None


def test_a_chosen_pull_requests_status_change_is_a_stop() -> None:
    before, after = scenarios.watch_sees_a_status_change()
    assert watching.set_change(before, after) is None
    stop = watching.status_change(before, after, HAZEL)
    assert stop is not None
    assert stop.reason is watching.StopReason.STATUS_CHANGED
    assert stop.title_mark == "#2 ready to merge"
    assert stop.detail == "hazel-tracking #2 is now ready to merge"


def test_another_pull_requests_status_change_is_not_the_chosen_ones() -> None:
    before, after = scenarios.watch_sees_a_status_change()
    other = (scenarios.full("deco-assaying"), 24)
    assert watching.status_change(before, after, other) is None


# The page.


async def test_the_button_says_that_it_is_watching_and_shows_no_spinner(user: User, page_plan: Plan) -> None:
    await open_tab(user, page_plan, pull_requests=scenarios.watch_times_out())
    user.find(marker="watch").click()
    await until(lambda: page_plan.pull_request_gathers >= 3)
    await user.should_see("Watching")
    await user.should_not_see(marker="spinner")


async def test_pressing_it_again_cancels_the_watch(user: User, page_plan: Plan) -> None:
    await open_tab(user, page_plan, pull_requests=scenarios.watch_times_out())
    user.find(marker="watch").click()
    await until(lambda: page_plan.pull_request_gathers >= 2)
    user.find(marker="watch").click()
    gathered = page_plan.pull_request_gathers
    await asyncio.sleep(0.2)
    assert page_plan.pull_request_gathers == gathered
    await user.should_see(content="the reader stopped the watch")


async def test_it_stops_on_a_change_and_marks_the_browser_tabs_title(user: User, page_plan: Plan) -> None:
    await open_tab(user, page_plan, pull_requests=scenarios.watch_sees_a_change())
    user.find(marker="watch").click()
    await until(lambda: user.client.title != DISPLAY_NAME)
    assert user.client.title == f"1 new pull request · {DISPLAY_NAME}"
    await user.should_see(content="handbook #12 arrived")
    await user.should_see(content="#12 docs: the branching page")
    gathered = page_plan.pull_request_gathers
    await asyncio.sleep(0.2)
    assert page_plan.pull_request_gathers == gathered


async def test_a_watch_from_one_row_stops_on_that_pull_requests_status_change(
    user: User, page_plan: Plan
) -> None:
    await open_tab(user, page_plan, pull_requests=scenarios.watch_sees_a_status_change())
    user.find(marker=f"watch-{HAZEL[0]}-{HAZEL[1]}").click()
    await until(lambda: user.client.title != DISPLAY_NAME)
    assert user.client.title == f"#2 ready to merge · {DISPLAY_NAME}"
    await user.should_see(content="hazel-tracking #2 is now ready to merge")


async def test_a_watch_from_the_whole_set_passes_over_one_status_change(user: User, page_plan: Plan) -> None:
    await open_tab(user, page_plan, pull_requests=scenarios.watch_sees_a_status_change())
    user.find(marker="watch").click()
    await until(lambda: page_plan.pull_request_gathers >= 4)
    assert user.client.title == DISPLAY_NAME


async def test_it_stops_when_its_time_runs_out_and_marks_no_title(user: User, page_plan: Plan) -> None:
    await open_tab(user, page_plan, pull_requests=scenarios.watch_times_out())
    user.find(marker="watch").click()
    # The apostrophe of "the watch's time ran out" reaches the browser as a character reference.
    await until(lambda: "time ran out" in content_of(user, "watch-result"), timeout=3.0)
    assert user.client.title == DISPLAY_NAME
    gathered = page_plan.pull_request_gathers
    await asyncio.sleep(0.2)
    assert page_plan.pull_request_gathers == gathered


async def test_it_stops_when_the_reader_leaves_the_tab(user: User, page_plan: Plan) -> None:
    await open_tab(user, page_plan, pull_requests=scenarios.watch_times_out())
    user.find(marker="watch").click()
    await until(lambda: page_plan.pull_request_gathers >= 2)
    user.find("Overview").click()
    await asyncio.sleep(0.15)
    gathered = page_plan.pull_request_gathers
    await asyncio.sleep(0.2)
    assert page_plan.pull_request_gathers == gathered
    assert "the reader left the tab" in content_of(user, "watch-result")


async def test_the_watch_leaves_the_full_gather_alone(user: User, page_plan: Plan) -> None:
    await open_tab(user, page_plan, pull_requests=scenarios.watch_times_out())
    user.find(marker="watch").click()
    await until(lambda: page_plan.pull_request_gathers >= 4)
    assert page_plan.full_gathers == 1


async def test_a_watch_whose_gather_fails_stops_nothing(user: User, page_plan: Plan) -> None:
    await open_tab(user, page_plan, pull_requests=scenarios.watch_times_out())
    user.find(marker="watch").click()
    await until(lambda: page_plan.pull_request_gathers >= 2)
    page_plan.load(pull_requests=scenarios.pull_requests_not_gathered())
    await asyncio.sleep(0.15)
    assert user.client.title == DISPLAY_NAME
