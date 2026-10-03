# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""The detail tab: its ten columns, read from the page a browser is shown.

Each test opens the page with a scenario, reads the table back out of the
element the browser holds, and checks the column against its definition in
docs/what-it-shows.md, "The detail".
"""

from __future__ import annotations

from nicegui.testing import User

from hazel_tracking.ui import detail_view
from tests import page_scenarios as scenarios
from tests.page_fixtures import Plan, open_page, sheet_of


async def test_the_columns_stand_in_the_order_the_specification_gives(user: User, page_plan: Plan) -> None:
    await open_page(user, page_plan)
    assert sheet_of(user, "detail").headers == list(detail_view.COLUMNS)


async def test_the_rows_are_the_repositories_in_name_order(user: User, page_plan: Plan) -> None:
    await open_page(user, page_plan)
    rows = sheet_of(user, "detail").rows
    assert list(rows) == sorted(rows)
    assert len(rows) == len(scenarios.LIVE_LIKE_NAMES)


async def test_the_repository_links_to_itself_on_github(user: User, page_plan: Plan) -> None:
    await open_page(user, page_plan)
    await user.should_see(content="https://github.com/ParkviewLab/handbook")


async def test_the_last_push_reads_as_a_time_since_it_up_to_thirty_six_hours(
    user: User, page_plan: Plan
) -> None:
    await open_page(user, page_plan)
    rows = sheet_of(user, "detail").rows
    assert rows["hazel-tracking"][1].text == "6 min ago"
    assert rows["paper-boxing"][1].text == "34 h ago"
    assert rows["cobalt-grinding"][1].text == "29 Sep 2026"


async def test_the_issues_column_counts_issues_alone(user: User, page_plan: Plan) -> None:
    await open_page(user, page_plan)
    rows = sheet_of(user, "detail").rows
    assert rows["pensa-grex"][2].text == "6"
    assert rows["handbook"][2].text == "0"


async def test_the_tag_and_the_release_are_both_shown(user: User, page_plan: Plan) -> None:
    await open_page(user, page_plan, scenarios.stress())
    rows = sheet_of(user, "detail").rows
    assert rows["amber-kilning"][3].text == "v1.2.0 / release v1.1.0"
    assert rows["umber-glazing"][3].text == "no tag / release v0.3.0"
    assert rows["parkviewlab.ai"][3].text == "none"


async def test_a_tag_without_its_release_is_marked(user: User, page_plan: Plan) -> None:
    await open_page(user, page_plan)
    assert sheet_of(user, "detail").rows["pensa-forma"][3].text == "v0.2.1 / no release"


async def test_the_dev_release_is_shown_only_where_it_is_newer(user: User, page_plan: Plan) -> None:
    await open_page(user, page_plan)
    rows = sheet_of(user, "detail").rows
    assert rows["paper-boxing"][4].text == "0.4.4.dev502"
    assert rows["handbook"][4].text == "none"


async def test_the_unreleased_work_is_one_line_with_the_documentation_mark(
    user: User, page_plan: Plan
) -> None:
    await open_page(user, page_plan)
    rows = sheet_of(user, "detail").rows
    assert rows["handbook"][5].text == "2 pull requests ahead · documentation"
    assert rows["dev-tools"][5].text == "1 pull request ahead"
    assert rows["jonobones"][5].text == "none"


async def test_a_lone_trunk_has_no_comparison_and_no_readiness(user: User, page_plan: Plan) -> None:
    await open_page(user, page_plan, scenarios.stress())
    row = sheet_of(user, "detail").rows["indigo-forging"]
    assert row[5].text == ""
    assert row[6].text == ""


async def test_the_release_column_names_every_condition_that_fails(user: User, page_plan: Plan) -> None:
    await open_page(user, page_plan, scenarios.stress())
    rows = sheet_of(user, "detail").rows
    assert rows["carmine-etching"][6].text == "nothing to release ✕ checks failing on develop"
    assert rows["azure-smelting"][6].text == "✕ checks failing on develop ◐ back-merge pending"


async def test_ready_to_cut_notes_the_documentation(user: User, page_plan: Plan) -> None:
    await open_page(user, page_plan)
    rows = sheet_of(user, "detail").rows
    assert rows["handbook"][6].text == "● ready to cut a release · documentation"
    assert rows["pensa-grex"][6].text == "● ready to cut a release"


async def test_a_website_repository_shows_its_pending_back_merge(user: User, page_plan: Plan) -> None:
    await open_page(user, page_plan)
    rows = sheet_of(user, "detail").rows
    assert rows["parkviewlab.ai"][6].text == "◐ back-merge pending"
    assert rows["zoestum.ai"][6].text == "no back-merge pending"


async def test_the_checks_are_shown_for_both_trunks_the_release_trunk_first(
    user: User, page_plan: Plan
) -> None:
    await open_page(user, page_plan)
    rows = sheet_of(user, "detail").rows
    assert rows["flint-slating"][7].text == "main ● passing develop ✕ failing"
    assert rows["hazel-tracking"][7].text == "main ● passing develop ◐ running"


async def test_checks_that_do_not_exist_read_none(user: User, page_plan: Plan) -> None:
    await open_page(user, page_plan, scenarios.stress())
    assert sheet_of(user, "detail").rows["carmine-etching"][7].text == "main none develop none"


async def test_each_working_branch_carries_its_lag_and_any_pull_request(user: User, page_plan: Plan) -> None:
    await open_page(user, page_plan)
    rows = sheet_of(user, "detail").rows
    assert rows["hazel-tracking"][8].text == "feature-github (0) #2 feature-page (0) #3"
    assert rows["pensa-forma"][8].text == "doc-spec (2)"
    assert rows["handbook"][8].text == "none"


async def test_every_pull_request_status_reads_as_a_word(user: User, page_plan: Plan) -> None:
    await open_page(user, page_plan, scenarios.stress())
    shown = " ".join(cell[9].text for cell in sheet_of(user, "detail").rows.values())
    for status in (
        "draft",
        "conflicts",
        "checks failing",
        "checks running",
        "behind its base",
        "ready to merge",
    ):
        assert status in shown


async def test_the_pull_requests_are_numbered_and_linked(user: User, page_plan: Plan) -> None:
    await open_page(user, page_plan)
    assert sheet_of(user, "detail").rows["hazel-tracking"][9].text == "#2 ◐ checks running #3 draft"
    await user.should_see(content="https://github.com/ParkviewLab/hazel-tracking/pull/2")


async def test_a_gather_without_the_list_shows_the_columns_and_no_rows(user: User, page_plan: Plan) -> None:
    await open_page(user, page_plan, scenarios.no_repositories())
    detail = sheet_of(user, "detail")
    assert detail.headers == list(detail_view.COLUMNS)
    assert detail.rows == {}
