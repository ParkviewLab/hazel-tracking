# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Data not gathered: zeroed and greyed, and only where the gather fell short (R7).

Zeroed means 0 for a count, "no" for a yes-or-no fact and an empty value for a
version or a state, each in grey; a fact gathered and found empty reads "none" in
ordinary type. Grey carries nothing else on the page (R10), so a grey cell always
means that this fact could not be gathered, and the test is as much that the
other cells are not grey as that these are.
"""

from __future__ import annotations

from nicegui.testing import User

from tests import page_scenarios as scenarios
from tests.page_fixtures import Plan, open_page, sheet_of

DEV = 4
UNRELEASED = 5
RELEASE = 6
ISSUES = 2
LAST_PUSH = 1
BRANCHES = 8
PULL_REQUESTS = 9


def greyed(row: list) -> set[int]:
    return {index for index, cell in enumerate(row) if cell.ungathered}


async def test_a_refused_call_greys_the_facts_it_feeds_and_no_others(user: User, page_plan: Plan) -> None:
    await open_page(user, page_plan, scenarios.failures())
    rows = sheet_of(user, "detail").rows
    assert greyed(rows["handbook"]) == {DEV, UNRELEASED, RELEASE}
    assert greyed(rows["paper-boxing"]) == {DEV}
    assert greyed(rows["parkviewlab.ai"]) == {DEV}


async def test_a_count_not_gathered_is_zeroed_and_a_value_is_emptied(user: User, page_plan: Plan) -> None:
    await open_page(user, page_plan, scenarios.failures())
    row = sheet_of(user, "detail").rows["handbook"]
    assert row[DEV].text == "—"
    assert row[UNRELEASED].text == "0"
    assert row[RELEASE].text == "—"


async def test_a_fact_gathered_and_empty_reads_none_in_ordinary_type(user: User, page_plan: Plan) -> None:
    await open_page(user, page_plan)
    row = sheet_of(user, "detail").rows["handbook"]
    assert row[DEV].text == "none"
    assert not row[DEV].ungathered
    assert row[BRANCHES].text == "none"
    assert not row[BRANCHES].ungathered


async def test_a_gather_not_complete_shows_what_arrived_and_greys_the_rest(
    user: User, page_plan: Plan
) -> None:
    await open_page(user, page_plan, scenarios.timed_out())
    rows = sheet_of(user, "detail").rows
    assert len(rows) == len(scenarios.LIVE_LIKE_NAMES)
    for name, row in rows.items():
        assert greyed(row) == {ISSUES, DEV, BRANCHES, PULL_REQUESTS}, name
        assert row[ISSUES].text == "0"
        assert row[BRANCHES].text == "—"
        assert row[LAST_PUSH].text and not row[LAST_PUSH].ungathered


async def test_a_yes_or_no_fact_not_gathered_reads_no(user: User, page_plan: Plan) -> None:
    await open_page(user, page_plan, scenarios.stress())
    row = sheet_of(user, "detail").rows["ochre-milling"]
    assert row[RELEASE].text == "—"
    assert row[RELEASE].ungathered


async def test_a_branch_whose_lag_is_unknown_is_greyed_alone(user: User, page_plan: Plan) -> None:
    await open_page(user, page_plan, scenarios.stress())
    row = sheet_of(user, "detail").rows["sienna-tempering"]
    assert "feature-eight (—)" in row[BRANCHES].text
    assert "feature-seven (0) #401" in row[BRANCHES].text


async def test_a_pull_request_whose_status_is_unknown_is_greyed_alone(user: User, page_plan: Plan) -> None:
    await open_page(user, page_plan, scenarios.stress())
    row = sheet_of(user, "detail").rows["sienna-tempering"]
    assert row[PULL_REQUESTS].text == "#401 —"
    assert row[PULL_REQUESTS].ungathered
