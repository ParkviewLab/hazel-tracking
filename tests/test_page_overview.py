# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""The overview tab: the release state, the readiness and what waits on the reader.

The rule is docs/what-it-shows.md, "The overview": one screen, a repository a
line, distilled from the full gather with no gather of its own; a repository with
nothing waiting is shown quietly, and a fact that could not be gathered counts as
waiting.
"""

from __future__ import annotations

from nicegui.testing import User

from hazel_tracking.ui import overview_view
from tests import page_scenarios as scenarios
from tests.page_fixtures import Plan, open_page, sheet_of


async def test_the_overview_has_a_line_for_every_repository(user: User, page_plan: Plan) -> None:
    await open_page(user, page_plan)
    overview = sheet_of(user, "overview")
    assert overview.headers == list(overview_view.COLUMNS)
    assert len(overview.rows) == len(scenarios.LIVE_LIKE_NAMES)
    assert list(overview.rows) == sorted(overview.rows)


async def test_the_release_state_carries_the_dev_version_where_it_is_newer(
    user: User, page_plan: Plan
) -> None:
    await open_page(user, page_plan)
    rows = sheet_of(user, "overview").rows
    assert rows["paper-boxing"][1].text == "v0.4.3 dev 0.4.4.dev502"
    assert rows["handbook"][1].text == "v2.1.1"
    assert rows["hazel-tracking"][1].text == "none dev 0.1.0.dev301"


async def test_readiness_carries_the_count_and_the_documentation_note(user: User, page_plan: Plan) -> None:
    await open_page(user, page_plan)
    rows = sheet_of(user, "overview").rows
    assert rows["handbook"][2].text == "● ready to cut a release (2 pull requests, documentation)"
    assert rows["pensa-grex"][2].text == "● ready to cut a release (3 pull requests)"
    assert rows["cobalt-grinding"][2].text == "nothing to release"
    assert rows["parkviewlab.ai"][2].text == "◐ back-merge pending"


async def test_a_repository_with_nothing_waiting_is_shown_quietly(user: User, page_plan: Plan) -> None:
    await open_page(user, page_plan)
    overview = sheet_of(user, "overview")
    assert "cobalt-grinding" in overview.quiet
    assert "ebony-enriching" in overview.quiet
    for waiting in ("handbook", "pensa-grex", "flint-slating", "parkviewlab.ai"):
        assert waiting not in overview.quiet


async def test_what_waits_names_the_failing_trunks_and_counts_the_pull_requests(
    user: User, page_plan: Plan
) -> None:
    await open_page(user, page_plan)
    rows = sheet_of(user, "overview").rows
    assert rows["flint-slating"][3].text == "✕ checks failing on develop"
    assert rows["conception-space"][3].text == "● 1 ready to merge 2 issues"
    assert rows["deco-assaying"][3].text == "◐ 1 behind its base"
    assert rows["jonobones"][3].text == "1 issue"


async def test_every_status_that_calls_for_the_reader_is_counted(user: User, page_plan: Plan) -> None:
    await open_page(user, page_plan, scenarios.stress())
    waiting = sheet_of(user, "overview").rows["amber-kilning"][3].text
    assert "1 ready to merge" in waiting
    assert "1 conflicts" in waiting
    assert "1 checks failing" in waiting
    assert "12 issues" in waiting


async def test_a_fact_not_gathered_counts_as_waiting_and_is_greyed(user: User, page_plan: Plan) -> None:
    await open_page(user, page_plan, scenarios.stress())
    overview = sheet_of(user, "overview")
    row = overview.rows["ochre-milling"]
    assert "ochre-milling" not in overview.quiet
    assert row[1].ungathered
    assert row[2].ungathered
    assert "0 pull requests" in row[3].text
    assert "0 issues" in row[3].text
    assert row[3].ungathered


async def test_switching_to_the_overview_gathers_nothing(user: User, page_plan: Plan) -> None:
    await open_page(user, page_plan)
    user.find(marker="overview")
    assert page_plan.full_gathers == 1
    assert page_plan.pull_request_gathers == 1
