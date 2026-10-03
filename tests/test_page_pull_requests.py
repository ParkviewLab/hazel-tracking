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

from nicegui.testing import User

from tests import page_scenarios as scenarios
from tests.page_fixtures import Plan, open_page, until


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
