# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""The status bar: its one sentence, its information icon and the dialog behind it.

The rule is docs/what-it-shows.md, "Data not gathered and the status bar": the
health of the last gather in one sentence, with the rate limit remaining and when
it resets, the count of archived repositories not shown, and when the GitHub
token expires, yellow within thirty days of it; when something went wrong, what
and why, and an icon opening a dialog with the detail of each problem.
"""

from __future__ import annotations

from datetime import UTC, datetime

from nicegui.testing import User

from hazel_tracking.config import TOKEN_EXPIRY_WARNING_DAYS, Config
from tests import page_scenarios as scenarios
from tests.page_fixtures import Plan, content_of, open_page, until


async def test_a_wholly_successful_gather_reads_as_one_sentence(user: User, page_plan: Plan) -> None:
    await open_page(user, page_plan)
    sentence = content_of(user, "status-sentence")
    assert "Gathered from GitHub at 14:03:12 in 3.1 s" in sentence
    assert "4832 points left, resetting at 14:47" in sentence
    assert "2 archived repositories not shown" in sentence
    assert "the GitHub token expires in 350 days" in sentence
    assert sentence.endswith(".")


async def test_nothing_went_wrong_so_the_icon_is_not_there(user: User, page_plan: Plan) -> None:
    await open_page(user, page_plan)
    await user.should_not_see(marker="status-icon")


async def test_a_gather_with_failed_calls_says_what_and_why(user: User, page_plan: Plan) -> None:
    await open_page(user, page_plan, scenarios.failures())
    sentence = content_of(user, "status-sentence")
    assert "Gathered from GitHub at 14:03:12 in 4.7 s" in sentence
    assert "the dev releases could not be read (GitHub refused the container packages)" in sentence
    assert "one comparison could not be read" in sentence
    await user.should_see(marker="status-icon")


async def test_a_gather_not_complete_names_the_configured_wait_and_the_next_try(
    user: User, page_plan: Plan, page_config: Config
) -> None:
    await open_page(user, page_plan, scenarios.timed_out())
    sentence = content_of(user, "status-sentence")
    assert f"GitHub did not answer within the {page_config.wait_seconds:g} s wait" in sentence
    assert page_config.wait_seconds != 15.0, "the wait must differ from the default to be proven"
    assert "the page tries again at" in sentence


async def test_the_dialog_holds_every_problem_and_each_outstanding_call(user: User, page_plan: Plan) -> None:
    await open_page(user, page_plan, scenarios.timed_out())
    user.find(marker="status-icon").click()
    await user.should_see("What could not be gathered")
    dialog = content_of(user, "status-dialog")
    assert "GitHub did not answer within the wait" in dialog
    assert "two calls were still outstanding when the wait ran out" in dialog
    assert "the open pull requests of each repository" in dialog
    assert "the container packages of the organisation" in dialog


async def test_the_dialog_carries_the_status_and_the_message_of_a_refused_call(
    user: User, page_plan: Plan
) -> None:
    await open_page(user, page_plan, scenarios.failures())
    user.find(marker="status-icon").click()
    dialog = content_of(user, "status-dialog")
    assert "HTTP 403" in dialog
    assert "Forbidden" in dialog
    assert "HTTP 502" in dialog


async def test_an_expiry_within_the_warning_is_yellow(user: User, page_plan: Plan) -> None:
    await open_page(user, page_plan, scenarios.expiring_soon())
    sentence = content_of(user, "status-sentence")
    assert '<span class="yellow">the GitHub token expires in 11 days</span>' in sentence


async def test_an_expiry_beyond_the_warning_is_not_yellow(user: User, page_plan: Plan) -> None:
    beyond = scenarios.snapshot(
        scenarios.live_like().repositories, expires_in_days=TOKEN_EXPIRY_WARNING_DAYS + 5
    )
    await open_page(user, page_plan, beyond)
    sentence = content_of(user, "status-sentence")
    assert "the GitHub token expires in 35 days" in sentence
    assert '<span class="yellow">the GitHub token' not in sentence


async def test_a_gather_that_raised_says_the_gather_failed_and_shows_no_traceback(
    user: User, page_plan: Plan
) -> None:
    page_plan.load(scenarios.live_like(), scenarios.open_pull_requests())
    page_plan.full_raises = RuntimeError("a secret-looking detail that must not reach the page")
    await user.open("/")
    await until(lambda: "The gather failed" in content_of(user, "status-sentence"))
    sentence = content_of(user, "status-sentence")
    assert "the gather failed (the gathering stopped with an error before it finished)" in sentence
    assert "secret-looking" not in sentence
    user.find(marker="status-icon").click()
    dialog = content_of(user, "status-dialog")
    assert "the error was a RuntimeError" in dialog
    assert "secret-looking" not in dialog
    assert "Traceback" not in dialog


async def test_the_pull_requests_own_problem_is_named_in_the_sentence_and_the_dialog(
    user: User, page_plan: Plan
) -> None:
    """The icon opens every problem, so the sentence states every problem: one gather's trouble
    is not hidden by the other's going well (axiom 8)."""
    await open_page(user, page_plan, scenarios.live_like(), scenarios.pull_requests_not_gathered())
    await user.should_see(marker="status-icon")
    sentence = content_of(user, "status-sentence")
    assert "Gathered from GitHub at 14:03:12" in sentence
    assert "the open pull requests could not be read (GitHub refused the search)" in sentence
    user.find(marker="status-icon").click()
    assert "GitHub refused the search" in content_of(user, "status-dialog")


async def test_the_times_are_shown_in_the_labs_zone(user: User, page_plan: Plan) -> None:
    moment = datetime(2026, 10, 3, 23, 30, 0, tzinfo=UTC)
    await open_page(user, page_plan, scenarios.live_like(moment))
    assert "at 00:30:00" in content_of(user, "status-sentence")
