# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""When the page gathers by itself: the cycle, and the retries behind it.

The rule is docs/what-it-shows.md, "When the page gathers". The sequence itself
is read directly from `next_delay`, with the ruled intervals, so that the 1, 2,
4, 8 and 16 minutes are checked without waiting for them; the page's own tests
then prove that the timer is set from it, under a configuration whose intervals
are short.
"""

from __future__ import annotations

import asyncio
import time

from nicegui.testing import User

from hazel_tracking.config import GATHER_INTERVAL_SECONDS, RETRY_DELAYS_SECONDS, Config
from hazel_tracking.ui.schedule import next_delay
from tests import page_scenarios as scenarios
from tests.page_fixtures import Plan, open_page, until

RULED = Config()


def delays(results: list[bool]) -> list[float]:
    """The delays the schedule sets, given how each gather in turn went."""
    attempt = 0
    set_for = []
    for wholly_successful in results:
        delay, attempt = next_delay(RULED, attempt, wholly_successful=wholly_successful)
        set_for.append(delay)
    return set_for


def test_a_wholly_successful_gather_sets_the_cycle() -> None:
    assert delays([True]) == [GATHER_INTERVAL_SECONDS]
    assert GATHER_INTERVAL_SECONDS == 1800.0


def test_the_retries_double_and_then_the_cycle_resumes() -> None:
    assert delays([False] * 6) == [*RETRY_DELAYS_SECONDS, GATHER_INTERVAL_SECONDS]
    assert RETRY_DELAYS_SECONDS == (60.0, 120.0, 240.0, 480.0, 960.0)


def test_a_wholly_successful_gather_ends_the_retries() -> None:
    assert delays([False, False, True, False]) == [60.0, 120.0, 1800.0, 60.0]


def test_the_retries_begin_again_after_the_cycle_resumed() -> None:
    assert delays([False] * 8) == [*RETRY_DELAYS_SECONDS, 1800.0, 60.0, 120.0]


async def test_a_gather_that_is_not_wholly_successful_is_tried_again(user: User, page_plan: Plan) -> None:
    await open_page(user, page_plan, scenarios.timed_out())
    assert page_plan.full_gathers == 1
    await until(lambda: page_plan.full_gathers == 2, timeout=1.5)
    assert page_plan.pull_request_gathers == 1


async def test_a_gather_whose_calls_failed_is_tried_again(user: User, page_plan: Plan) -> None:
    await open_page(user, page_plan, scenarios.failures())
    await until(lambda: page_plan.full_gathers == 2, timeout=1.5)


async def test_a_wholly_successful_gather_restarts_the_cycle(user: User, page_plan: Plan) -> None:
    await open_page(user, page_plan, [scenarios.timed_out(), scenarios.live_like()])
    await until(lambda: page_plan.full_gathers == 2, timeout=1.5)
    await asyncio.sleep(0.5)
    assert page_plan.full_gathers == 2


async def test_refresh_cancels_the_pending_gather_and_sets_it_afresh(user: User, page_plan: Plan) -> None:
    await open_page(user, page_plan)
    await asyncio.sleep(0.5)
    user.find(marker="refresh").click()
    await until(lambda: page_plan.full_gathers == 2)
    await asyncio.sleep(0.7)
    assert page_plan.full_gathers == 2, "the gather set before the Refresh should have been cancelled"


async def test_the_automatic_gather_runs_the_full_gather_alone_under_the_large_spinner(
    user: User, page_plan: Plan
) -> None:
    await open_page(user, page_plan, scenarios.timed_out())
    await user.should_not_see(marker="spinner")
    hold = page_plan.block()
    await until(lambda: page_plan.full_gathers == 2, timeout=1.5)
    await user.should_see(marker="spinner")
    await user.should_not_see(marker="tab-spinner")
    assert page_plan.pull_request_gathers == 1
    hold.set()
    await user.should_not_see(marker="spinner")


async def test_refresh_is_disabled_while_the_automatic_gather_runs(user: User, page_plan: Plan) -> None:
    await open_page(user, page_plan, scenarios.timed_out())
    hold = page_plan.block()
    await until(lambda: page_plan.full_gathers == 2, timeout=1.5)
    (button,) = user.find(marker="refresh").elements
    assert not button.enabled
    user.find(marker="refresh").click()
    await asyncio.sleep(0.1)
    assert page_plan.full_gathers == 2, "a disabled Refresh starts no second full gather"
    hold.set()
    await until(lambda: button.enabled)


async def test_the_next_gather_is_measured_from_when_the_last_one_began(user: User, page_plan: Plan) -> None:
    """The first retry falls due 0.2 s after the gather began, not 0.2 s after it returned, so a
    gather of 0.3 s is followed at once rather than half a second later."""
    page_plan.delay = 0.3
    began = time.monotonic()
    await open_page(user, page_plan, scenarios.timed_out())
    await until(lambda: page_plan.full_gathers == 2, timeout=2.0)
    assert 0.25 < time.monotonic() - began < 0.45
