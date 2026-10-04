# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""What a gather does when GitHub does not answer, or answers badly: a call that fails greys the
facts it feeds and no others (R7, axiom 8), a gather not complete within the wait returns what
arrived and names each call outstanding (R11), and in every case the token appears in no problem
and no log record."""

from __future__ import annotations

import logging
from dataclasses import replace
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import httpx
import pytest

from hazel_tracking.app import default_http_client
from hazel_tracking.config import Config
from hazel_tracking.gather import gather, gather_pull_requests
from hazel_tracking.github import queries
from hazel_tracking.model import NOT_GATHERED, Gathered, Problem, Snapshot
from tests.gh_fakes import (
    COMPARE,
    PACKAGES,
    VERSIONS,
    FakeAnswer,
    FakeGitHub,
    FakeOrganisation,
    FakePackage,
    FakeRepository,
    forbidden,
    graphql_error,
    malformed,
    not_found,
    rate_limited_graphql,
    rate_limited_rest,
    server_error,
    unauthorised,
)
from tests.gh_fixtures import ORGANISATION, gh_found, gh_problem

RESET = 1_790_000_000


def reset_time(zone: ZoneInfo) -> str:
    return datetime.fromtimestamp(RESET, UTC).astimezone(zone).strftime("%H:%M")


def sentences(problems: tuple[Problem, ...]) -> str:
    """Every word of every problem, for a test that looks for what must not be in any of them."""
    return " ".join(
        f"{problem.what} {problem.why} "
        + " ".join(f"{detail.call} {detail.status} {detail.message}" for detail in problem.details)
        for problem in problems
    )


# A call that fails, in a gather complete within the wait.


async def test_a_refused_token_leaves_the_page_with_no_repository(
    gh_config: Config, gh_client: httpx.AsyncClient, gh_github: FakeGitHub
) -> None:
    gh_github.failures[queries.REPOSITORIES_OPERATION] = unauthorised()
    snapshot = await gather(gh_config, gh_client)
    assert snapshot.completed
    assert snapshot.repositories == ()
    assert snapshot.archived is None
    problem = gh_problem(snapshot.problems, "every repository's facts")
    assert problem.why == "the GitHub token was refused"
    assert problem.details[0].status == 401
    assert problem.details[0].call == "the organisation's repositories"


async def test_the_packages_refused_grey_the_dev_releases_alone(
    gh_config: Config, gh_client: httpx.AsyncClient, gh_github: FakeGitHub
) -> None:
    gh_github.failures[PACKAGES] = forbidden()
    snapshot = await gather(gh_config, gh_client)
    assert snapshot.completed
    assert len(snapshot.repositories) == 6
    for repository in snapshot.repositories:
        assert repository.dev_release == NOT_GATHERED
        assert isinstance(repository.newest_tag, Gathered)
        assert isinstance(repository.open_issues, Gathered)
    problem = gh_problem(snapshot.problems, "the dev releases")
    assert problem.why == "GitHub refused the call; the GitHub token may not be allowed to read it"
    assert problem.details[0].call == "the organisation's container packages"


async def test_one_packages_versions_refused_grey_that_repositorys_dev_release_alone(
    gh_config: Config, gh_client: httpx.AsyncClient, gh_github: FakeGitHub
) -> None:
    gh_github.failures[f"{VERSIONS}:fieldwork-worker"] = server_error()
    snapshot = await gather(gh_config, gh_client)
    assert gh_found(snapshot, "fieldwork").dev_release == NOT_GATHERED
    assert gh_found(snapshot, "atlas").dev_release == Gathered(None)
    problem = gh_problem(snapshot.problems, f"the dev release of {ORGANISATION}/fieldwork")
    assert problem.why == "GitHub failed on the call"


async def test_a_comparison_that_fails_greys_the_unreleased_work_and_the_lag_alone(
    gh_config: Config, gh_client: httpx.AsyncClient, gh_github: FakeGitHub
) -> None:
    """Every comparison of one repository refused: its unreleased work, its readiness, its pending
    back-merge and each branch's lag are greyed, and nothing else of it is."""
    gh_github.failures[f"{COMPARE}:atlas"] = not_found()
    snapshot = await gather(gh_config, gh_client)
    atlas = gh_found(snapshot, "atlas")
    assert atlas.unreleased is not None
    assert atlas.unreleased.pull_requests == NOT_GATHERED
    assert atlas.unreleased.documentation == NOT_GATHERED
    assert atlas.readiness == NOT_GATHERED
    assert atlas.back_merge_pending == NOT_GATHERED
    assert isinstance(atlas.working_branches, Gathered)
    assert [branch.behind for branch in atlas.working_branches.value] == [NOT_GATHERED] * 3
    assert isinstance(atlas.pull_requests, Gathered)
    assert all(isinstance(check.state, Gathered) for check in atlas.checks)
    problem = gh_problem(snapshot.problems, f"the unreleased work of {ORGANISATION}/atlas")
    assert problem.why == "GitHub found nothing to read"
    assert problem.details[0].call.startswith("the comparison of the trunks")
    basalt = gh_found(snapshot, "basalt")
    assert basalt.unreleased is not None
    assert basalt.unreleased.pull_requests == Gathered(0)
    assert basalt.back_merge_pending == Gathered(True)


async def test_the_files_that_fail_grey_the_documentation_mark_alone(
    gh_config: Config, gh_client: httpx.AsyncClient, gh_github: FakeGitHub
) -> None:
    gh_github.failures[queries.FILES_OPERATION] = server_error()
    snapshot = await gather(gh_config, gh_client)
    atlas = gh_found(snapshot, "atlas")
    assert atlas.unreleased is not None
    assert atlas.unreleased.pull_requests == Gathered(1)
    assert atlas.unreleased.documentation == NOT_GATHERED
    assert atlas.readiness == Gathered(replace(atlas.readiness.value, failing=frozenset()))
    gh_problem(snapshot.problems, "changes the documentation")


async def test_a_second_read_that_fails_leaves_that_status_not_gathered(
    gh_config: Config, gh_client: httpx.AsyncClient, gh_github: FakeGitHub
) -> None:
    gh_github.failures[queries.STATUSES_OPERATION] = server_error()
    snapshot = await gather(gh_config, gh_client)
    quarry = gh_found(snapshot, "quarry")
    assert isinstance(quarry.pull_requests, Gathered)
    statuses = {pull.number: pull.status for pull in quarry.pull_requests.value}
    assert statuses[11] == NOT_GATHERED
    assert isinstance(statuses[13], Gathered)
    gh_problem(snapshot.problems, "the status of")


async def test_an_answer_that_is_not_json_costs_the_facts_it_carried(
    gh_config: Config, gh_client: httpx.AsyncClient, gh_github: FakeGitHub
) -> None:
    gh_github.failures[queries.REPOSITORIES_OPERATION] = malformed()
    snapshot = await gather(gh_config, gh_client)
    assert snapshot.completed
    assert snapshot.repositories == ()
    problem = gh_problem(snapshot.problems, "every repository's facts")
    assert problem.why == "GitHub's answer could not be read"


async def test_an_error_beside_the_data_keeps_the_data_and_names_the_problem(
    gh_config: Config, gh_client: httpx.AsyncClient, gh_github: FakeGitHub
) -> None:
    """A GraphQL answer may carry an error and data at once; the facts that arrived stand."""
    gh_github.errors[queries.REPOSITORIES_OPERATION] = [{"message": "Something went wrong"}]
    snapshot = await gather(gh_config, gh_client)
    assert len(snapshot.repositories) == 6
    assert isinstance(gh_found(snapshot, "atlas").open_issues, Gathered)
    problem = gh_problem(snapshot.problems, "every repository's facts")
    assert problem.why == "GitHub answered with an error"
    assert problem.details[0].message == "Something went wrong"


async def test_a_branch_github_no_longer_holds_is_a_problem_of_its_own(
    gh_config: Config, gh_client: httpx.AsyncClient, gh_github: FakeGitHub
) -> None:
    """A branch deleted between two calls: its comparison has nothing to read, and its lag alone is
    greyed."""
    gh_github.organisation = replace(
        gh_github.organisation,
        repositories=tuple(
            replace(repository, missing=frozenset({"feature-charts"}))
            if repository.name == "atlas"
            else repository
            for repository in gh_github.organisation.repositories
        ),
    )
    snapshot = await gather(gh_config, gh_client)
    atlas = gh_found(snapshot, "atlas")
    assert isinstance(atlas.working_branches, Gathered)
    lags = {branch.name: branch.behind for branch in atlas.working_branches.value}
    assert lags["feature-charts"] == NOT_GATHERED
    assert lags["hotfix-pick"] == Gathered(0)
    problem = gh_problem(snapshot.problems, "the lag of the branch feature-charts")
    assert problem.why == "GitHub found nothing to read"


async def test_a_call_that_gives_no_answer_at_all_is_a_problem(
    gh_config: Config, gh_client: httpx.AsyncClient, gh_github: FakeGitHub
) -> None:
    gh_github.refuses.add(PACKAGES)
    snapshot = await gather(gh_config, gh_client)
    assert snapshot.completed
    problem = gh_problem(snapshot.problems, "the dev releases")
    assert problem.why == "GitHub gave no answer"
    assert problem.details[0].status is None


# A refusal for the rate limit, from either interface.


async def test_graphqls_refusal_for_the_rate_limit_says_when_the_budget_resets(
    gh_config: Config, gh_client: httpx.AsyncClient, gh_github: FakeGitHub
) -> None:
    gh_github.failures[queries.COMMIT_PULL_REQUESTS_OPERATION] = rate_limited_graphql(RESET)
    snapshot = await gather(gh_config, gh_client)
    assert snapshot.completed
    problem = gh_problem(snapshot.problems, "the unreleased work of")
    assert (
        problem.why == f"GitHub's rate limit is spent; the budget resets at {reset_time(gh_config.time_zone)}"
    )
    assert problem.details[0].status == 200


@pytest.mark.parametrize("status", [403, 429])
async def test_rests_refusal_for_the_rate_limit_says_when_the_budget_resets(
    gh_config: Config, gh_client: httpx.AsyncClient, gh_github: FakeGitHub, status: int
) -> None:
    gh_github.failures[PACKAGES] = rate_limited_rest(status, RESET)
    snapshot = await gather(gh_config, gh_client)
    problem = gh_problem(snapshot.problems, "the dev releases")
    assert (
        problem.why == f"GitHub's rate limit is spent; the budget resets at {reset_time(gh_config.time_zone)}"
    )
    assert problem.details[0].status == status


async def test_the_search_refused_for_the_rate_limit_leaves_the_tab_with_no_list(
    gh_config: Config, gh_client: httpx.AsyncClient, gh_github: FakeGitHub
) -> None:
    gh_github.failures[queries.OPEN_PULL_REQUESTS_OPERATION] = rate_limited_graphql(RESET)
    snapshot = await gather_pull_requests(gh_config, gh_client)
    assert snapshot.completed
    assert snapshot.pull_requests == NOT_GATHERED
    problem = gh_problem(snapshot.problems, "the open pull requests")
    assert problem.why.startswith("GitHub's rate limit is spent")


# A gather not complete within the wait (R11).


def hurried(cfg: Config) -> Config:
    """A configuration whose wait is far shorter than the answer a test holds back."""
    return replace(cfg, wait_seconds=0.05)


async def test_a_gather_cut_short_before_the_repositories_arrive_shows_none_of_them(
    gh_config: Config, gh_github: FakeGitHub
) -> None:
    gh_github.delays[queries.REPOSITORIES_OPERATION] = 0.5
    cfg = hurried(gh_config)
    async with default_http_client(cfg, transport=gh_github.transport()) as client:
        snapshot = await gather(cfg, client)
    assert not snapshot.completed
    assert snapshot.repositories == ()
    assert snapshot.archived is None
    problem = gh_problem(snapshot.problems, "the facts GitHub had not yet given")
    assert problem.why == "GitHub did not answer within the wait of 0.05 seconds"
    assert [detail.call for detail in problem.details] == ["the organisation's repositories"]
    assert problem.details[0].message == "no answer within the wait"


async def test_a_gather_cut_short_after_the_repositories_arrive_keeps_what_did(
    gh_config: Config, gh_github: FakeGitHub
) -> None:
    gh_github.delays[COMPARE] = 0.5
    cfg = hurried(gh_config)
    async with default_http_client(cfg, transport=gh_github.transport()) as client:
        snapshot = await gather(cfg, client)
    assert not snapshot.completed
    assert len(snapshot.repositories) == 6
    atlas = gh_found(snapshot, "atlas")
    assert atlas.open_issues == Gathered(3)
    assert atlas.newest_tag == Gathered("v0.10.0")
    assert isinstance(atlas.pull_requests, Gathered)
    assert atlas.unreleased is not None
    assert atlas.unreleased.pull_requests == NOT_GATHERED
    assert atlas.readiness == NOT_GATHERED
    problem = gh_problem(snapshot.problems, "the facts GitHub had not yet given")
    assert any("the comparison" in detail.call for detail in problem.details)


async def test_a_gather_of_the_open_pull_requests_cut_short_shows_no_list(
    gh_config: Config, gh_github: FakeGitHub
) -> None:
    gh_github.delays[queries.OPEN_PULL_REQUESTS_OPERATION] = 0.5
    cfg = hurried(gh_config)
    async with default_http_client(cfg, transport=gh_github.transport()) as client:
        snapshot = await gather_pull_requests(cfg, client)
    assert not snapshot.completed
    assert snapshot.pull_requests == NOT_GATHERED
    problem = gh_problem(snapshot.problems, "the facts GitHub had not yet given")
    assert [detail.call for detail in problem.details] == ["the organisation's open pull requests"]


# The token, in nothing a reader or a log can see.


async def test_the_token_appears_in_no_problem_and_no_log_record(
    gh_config: Config,
    gh_client: httpx.AsyncClient,
    gh_github: FakeGitHub,
    sentinel_token: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Every failure at once, GitHub echoing the token in two of its own messages."""
    echoed = FakeAnswer(status=403, payload={"message": f"the token {sentinel_token} is not allowed"})
    gh_github.failures[PACKAGES] = echoed
    gh_github.failures[queries.COMMIT_PULL_REQUESTS_OPERATION] = graphql_error(f"bad token {sentinel_token}")
    gh_github.failures[queries.STATUSES_OPERATION] = unauthorised()
    gh_github.errors[queries.REPOSITORIES_OPERATION] = [{"message": f"token {sentinel_token}"}]
    with caplog.at_level(logging.DEBUG):
        snapshot = await gather(gh_config, gh_client)
    assert len(snapshot.problems) >= 4
    assert sentinel_token not in sentences(snapshot.problems)
    assert "the GitHub token" in sentences(snapshot.problems)
    assert all(sentinel_token not in record.getMessage() for record in caplog.records)
    assert f"Bearer {sentinel_token}" in gh_github.credentials


async def test_the_token_appears_in_no_problem_of_the_pull_requests_gather(
    gh_config: Config,
    gh_client: httpx.AsyncClient,
    gh_github: FakeGitHub,
    sentinel_token: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    gh_github.failures[queries.OPEN_PULL_REQUESTS_OPERATION] = FakeAnswer(
        status=401, payload={"message": f"bad credentials: {sentinel_token}"}
    )
    with caplog.at_level(logging.DEBUG):
        snapshot = await gather_pull_requests(gh_config, gh_client)
    assert snapshot.problems
    assert sentinel_token not in sentences(snapshot.problems)
    assert all(sentinel_token not in record.getMessage() for record in caplog.records)


async def test_an_answer_of_an_unexpected_shape_is_a_problem_and_not_a_traceback(
    gh_config: Config, gh_client: httpx.AsyncClient, gh_github: FakeGitHub
) -> None:
    """A GraphQL answer whose data is not of the shape the reading expects: the gather returns a
    snapshot that says what it lost, and raises nothing."""
    gh_github.failures[queries.REPOSITORIES_OPERATION] = FakeAnswer(
        status=200, payload={"data": {"organization": {"repositories": {"nodes": "not a list of nodes"}}}}
    )
    snapshot: Snapshot = await gather(gh_config, gh_client)
    assert snapshot.completed
    assert snapshot.repositories == ()
    assert snapshot.archived is None
    gh_problem(snapshot.problems, "every repository's facts")


# A list that cannot be read to its end is not gathered at all.


async def test_a_list_of_tags_or_branches_cut_short_is_not_gathered(
    gh_config: Config, gh_organisation: FakeOrganisation
) -> None:
    """The newest tag by version, and which branches exist, are facts of the whole list, so a list
    whose later pages fail is greyed whole whilst every other fact stands (R1, R3)."""
    fake = FakeGitHub(organisation=gh_organisation, page_cap=1)
    fake.failures[queries.REFS_OPERATION] = server_error()
    async with default_http_client(gh_config, transport=fake.transport()) as client:
        snapshot = await gather(gh_config, client)
    atlas = gh_found(snapshot, "atlas")
    assert atlas.newest_tag == NOT_GATHERED
    assert atlas.working_branches == NOT_GATHERED
    assert atlas.newest_release == Gathered("v0.2.0")
    assert atlas.open_issues == Gathered(3)
    assert isinstance(atlas.pull_requests, Gathered)
    assert atlas.dev_release == NOT_GATHERED  # the final release it is compared with is unknown
    gh_problem(snapshot.problems, f"the newest tag of {ORGANISATION}/atlas")
    gh_problem(snapshot.problems, f"the branches of {ORGANISATION}/atlas")


async def test_a_list_of_open_pull_requests_cut_short_is_not_gathered(
    gh_config: Config, gh_organisation: FakeOrganisation
) -> None:
    """Which branch has a pull request open from it is a fact of the whole list, so both the list
    and each branch's pull request are greyed, whilst the branches and their lag stand."""
    fake = FakeGitHub(organisation=gh_organisation, page_cap=1)
    fake.failures[queries.REPOSITORY_PULL_REQUESTS_OPERATION] = server_error()
    async with default_http_client(gh_config, transport=fake.transport()) as client:
        snapshot = await gather(gh_config, client)
    atlas = gh_found(snapshot, "atlas")
    assert atlas.pull_requests == NOT_GATHERED
    assert isinstance(atlas.working_branches, Gathered)
    branches = {branch.name: branch for branch in atlas.working_branches.value}
    assert branches["feature-charts"].behind == Gathered(2)
    assert branches["feature-charts"].pull_request == NOT_GATHERED
    gh_problem(snapshot.problems, f"the open pull requests of {ORGANISATION}/atlas")


async def test_a_comparison_github_will_not_list_whole_greys_the_count_and_keeps_the_back_merge(
    gh_config: Config, gh_organisation: FakeOrganisation
) -> None:
    """A comparison whose commits GitHub stops listing before its own total cannot be counted;
    whether the release trunk holds anything the integration trunk
    lacks is answered by the same call and stands."""
    organisation = replace(
        gh_organisation,
        repositories=tuple(
            replace(repository, ahead_total=300) if repository.name == "atlas" else repository
            for repository in gh_organisation.repositories
        ),
    )
    fake = FakeGitHub(organisation=organisation)
    async with default_http_client(gh_config, transport=fake.transport()) as client:
        snapshot = await gather(gh_config, client)
    atlas = gh_found(snapshot, "atlas")
    assert atlas.unreleased is not None
    assert atlas.unreleased.pull_requests == NOT_GATHERED
    assert atlas.unreleased.documentation == NOT_GATHERED
    assert atlas.back_merge_pending == Gathered(False)
    assert atlas.readiness == NOT_GATHERED
    problem = gh_problem(snapshot.problems, f"the unreleased work of {ORGANISATION}/atlas")
    assert problem.why == "GitHub listed only 4 of the 300 commits of the comparison"
    assert (
        problem.details[0].message
        == "the comparison's commits were listed 100 a page, to a guard of 20 pages"
    )


async def test_a_comparison_refused_for_want_of_a_scope_says_so(
    gh_config: Config, gh_client: httpx.AsyncClient, gh_github: FakeGitHub
) -> None:
    """GraphQL refuses a field the token's scopes do not reach with status 200 and an
    INSUFFICIENT_SCOPES error, as it does `Ref.compare`'s counts; the problem names the credential
    in general terms and its detail carries GitHub's own message."""
    message = (
        "Your token has not been granted the required scopes to execute this query. "
        "The 'aheadBy' field requires one of the following scopes: ['repo'], but your token has "
        "only been granted the: ['read:packages'] scopes."
    )
    gh_github.failures[queries.COMMIT_PULL_REQUESTS_OPERATION] = FakeAnswer(
        status=200,
        payload={"data": None, "errors": [{"type": "INSUFFICIENT_SCOPES", "message": message}]},
    )
    snapshot = await gather(gh_config, gh_client)
    assert snapshot.completed
    problem = gh_problem(snapshot.problems, "the unreleased work of")
    assert problem.why == "GitHub refused the call; the GitHub token lacks the scope it would need"
    assert problem.details[0].message == message
    assert problem.details[0].status == 200


async def test_an_answer_refused_at_the_http_level_is_read_by_its_status_not_its_body(
    gh_config: Config, gh_client: httpx.AsyncClient, gh_github: FakeGitHub
) -> None:
    """A 502 from a proxy carries no JSON at all; it is GitHub failing, not an answer that could not
    be read."""
    gh_github.failures[queries.REPOSITORIES_OPERATION] = FakeAnswer(status=502, text="<html>Bad gateway")
    snapshot = await gather(gh_config, gh_client)
    assert snapshot.completed
    problem = gh_problem(snapshot.problems, "every repository's facts")
    assert problem.why == "GitHub failed on the call"
    assert problem.details[0].status == 502


async def test_a_graphql_call_refused_for_a_secondary_rate_limit_says_so(
    gh_config: Config, gh_client: httpx.AsyncClient, gh_github: FakeGitHub
) -> None:
    """GitHub answers a secondary rate limit with 403 and its own message, in GraphQL as in REST; the
    message is what tells it from a refusal of the credential's scope."""
    gh_github.failures[queries.REPOSITORIES_OPERATION] = rate_limited_rest(403, RESET)
    snapshot = await gather(gh_config, gh_client)
    problem = gh_problem(snapshot.problems, "every repository's facts")
    assert (
        problem.why == f"GitHub's rate limit is spent; the budget resets at {reset_time(gh_config.time_zone)}"
    )


# R11: a fact still being read when the wait runs out is not gathered, not published part-read.


async def test_a_list_still_being_read_when_the_wait_runs_out_is_not_gathered(
    gh_config: Config, gh_organisation: FakeOrganisation
) -> None:
    """The tags and branches of a repository whose lists ran past the first page: the first page had
    arrived, the rest had not, and the newest tag is of the whole list or of none."""
    fake = FakeGitHub(organisation=gh_organisation, page_cap=2, delays={queries.REFS_OPERATION: 0.5})
    cfg = hurried(gh_config)
    async with default_http_client(cfg, transport=fake.transport()) as client:
        snapshot = await gather(cfg, client)
    assert not snapshot.completed
    atlas = gh_found(snapshot, "atlas")
    assert atlas.newest_tag == NOT_GATHERED
    assert atlas.working_branches == NOT_GATHERED
    assert atlas.open_issues == Gathered(3)
    problem = gh_problem(snapshot.problems, "the facts GitHub had not yet given")
    assert any("the tags of" in detail.call for detail in problem.details)


async def test_open_pull_requests_still_being_read_when_the_wait_runs_out_are_not_gathered(
    gh_config: Config, gh_organisation: FakeOrganisation
) -> None:
    fake = FakeGitHub(
        organisation=gh_organisation,
        page_cap=1,
        delays={queries.REPOSITORY_PULL_REQUESTS_OPERATION: 0.5},
    )
    cfg = hurried(gh_config)
    async with default_http_client(cfg, transport=fake.transport()) as client:
        snapshot = await gather(cfg, client)
    assert gh_found(snapshot, "atlas").pull_requests == NOT_GATHERED


async def test_the_unreleased_count_is_not_gathered_whilst_its_commits_are_still_being_read(
    gh_config: Config, gh_organisation: FakeOrganisation
) -> None:
    """The comparison had answered and what its commits belong to had not: the count is of every
    commit or of none, whilst the pending back-merge the same answer gave stands."""
    fake = FakeGitHub(organisation=gh_organisation, delays={queries.COMMIT_PULL_REQUESTS_OPERATION: 0.5})
    cfg = hurried(gh_config)
    async with default_http_client(cfg, transport=fake.transport()) as client:
        snapshot = await gather(cfg, client)
    atlas = gh_found(snapshot, "atlas")
    assert atlas.unreleased is not None
    assert atlas.unreleased.pull_requests == NOT_GATHERED
    assert atlas.unreleased.documentation == NOT_GATHERED
    assert atlas.readiness == NOT_GATHERED
    assert atlas.back_merge_pending == Gathered(False)


async def test_the_documentation_mark_is_not_gathered_whilst_the_files_are_still_being_read(
    gh_config: Config, gh_organisation: FakeOrganisation
) -> None:
    """The count had been made and the files had not: the mark waits on them, the count does not."""
    fake = FakeGitHub(organisation=gh_organisation, delays={queries.FILES_OPERATION: 0.5})
    cfg = hurried(gh_config)
    async with default_http_client(cfg, transport=fake.transport()) as client:
        snapshot = await gather(cfg, client)
    atlas = gh_found(snapshot, "atlas")
    assert atlas.unreleased is not None
    assert atlas.unreleased.pull_requests == Gathered(1)
    assert atlas.unreleased.documentation == NOT_GATHERED


async def test_a_dev_release_is_not_gathered_whilst_its_packages_are_still_being_read(
    gh_config: Config, gh_organisation: FakeOrganisation
) -> None:
    """The list of packages had arrived and one repository's versions had not; a repository with two
    packages waits for both."""
    fake = FakeGitHub(organisation=gh_organisation, delays={f"{VERSIONS}:fieldwork-worker": 0.5})
    cfg = hurried(gh_config)
    async with default_http_client(cfg, transport=fake.transport()) as client:
        snapshot = await gather(cfg, client)
    assert gh_found(snapshot, "fieldwork").dev_release == NOT_GATHERED
    assert gh_found(snapshot, "atlas").dev_release == Gathered(None)


async def test_the_archived_count_is_not_given_where_the_list_was_not_read_to_its_end(
    gh_config: Config, gh_organisation: FakeOrganisation
) -> None:
    """A count of some of the pages is no count; the repositories that did arrive stand (R11)."""
    fake = FakeGitHub(organisation=gh_organisation, page_cap=2)
    failure = server_error()
    failure.after = 1
    fake.failures[queries.REPOSITORIES_OPERATION] = failure
    async with default_http_client(gh_config, transport=fake.transport()) as client:
        snapshot = await gather(gh_config, client)
    assert snapshot.archived is None
    assert len(snapshot.repositories) == 2
    gh_problem(snapshot.problems, "the repositories GitHub had not yet listed")


# An error beside the data: the targets it names are lost and the rest of the answer stands.


async def test_an_error_on_one_commit_costs_that_repositorys_count_alone(
    gh_config: Config, gh_client: httpx.AsyncClient, gh_github: FakeGitHub
) -> None:
    gh_github.errors[queries.COMMIT_PULL_REQUESTS_OPERATION] = [
        {"message": "Could not resolve to a Commit", "path": ["r0", "c1"]}
    ]
    snapshot = await gather(gh_config, gh_client)
    atlas = gh_found(snapshot, "atlas")
    assert atlas.unreleased is not None
    assert atlas.unreleased.pull_requests == NOT_GATHERED
    assert atlas.back_merge_pending == Gathered(False)
    gh_problem(snapshot.problems, f"the unreleased work of {ORGANISATION}/atlas")


async def test_an_error_on_one_pull_requests_files_costs_the_mark_alone(
    gh_config: Config, gh_client: httpx.AsyncClient, gh_github: FakeGitHub
) -> None:
    gh_github.errors[queries.FILES_OPERATION] = [{"message": "Something went wrong", "path": ["f0"]}]
    snapshot = await gather(gh_config, gh_client)
    atlas = gh_found(snapshot, "atlas")
    assert atlas.unreleased is not None
    assert atlas.unreleased.pull_requests == Gathered(1)
    assert atlas.unreleased.documentation == NOT_GATHERED
    gh_problem(snapshot.problems, "changes the documentation")


async def test_an_error_on_one_status_costs_that_status_alone(
    gh_config: Config, gh_client: httpx.AsyncClient, gh_github: FakeGitHub
) -> None:
    gh_github.errors[queries.STATUSES_OPERATION] = [{"message": "Something went wrong", "path": ["s0"]}]
    snapshot = await gather(gh_config, gh_client)
    quarry = gh_found(snapshot, "quarry")
    assert isinstance(quarry.pull_requests, Gathered)
    statuses = {pull.number: pull.status for pull in quarry.pull_requests.value}
    assert statuses[11] == NOT_GATHERED
    assert isinstance(statuses[13], Gathered)
    gh_problem(snapshot.problems, "the status of")


async def test_an_error_beside_a_continuation_leaves_the_list_not_gathered(
    gh_config: Config, gh_organisation: FakeOrganisation
) -> None:
    fake = FakeGitHub(organisation=gh_organisation, page_cap=2)
    fake.errors[queries.REFS_OPERATION] = [{"message": "Something went wrong"}]
    async with default_http_client(gh_config, transport=fake.transport()) as client:
        snapshot = await gather(gh_config, client)
    atlas = gh_found(snapshot, "atlas")
    assert atlas.newest_tag == NOT_GATHERED
    assert atlas.working_branches == NOT_GATHERED
    gh_problem(snapshot.problems, f"the newest tag of {ORGANISATION}/atlas")


async def test_an_error_beside_a_page_of_files_leaves_the_mark_not_gathered(
    gh_config: Config, gh_organisation: FakeOrganisation
) -> None:
    fake = FakeGitHub(organisation=gh_organisation, page_cap=1)
    fake.errors[queries.FILES_PAGE_OPERATION] = [{"message": "Something went wrong"}]
    async with default_http_client(gh_config, transport=fake.transport()) as client:
        snapshot = await gather(gh_config, client)
    atlas = gh_found(snapshot, "atlas")
    assert atlas.unreleased is not None
    assert atlas.unreleased.pull_requests == Gathered(1)
    assert atlas.unreleased.documentation == NOT_GATHERED


async def test_an_error_beside_the_search_leaves_the_tab_with_no_list(
    gh_config: Config, gh_client: httpx.AsyncClient, gh_github: FakeGitHub
) -> None:
    gh_github.errors[queries.OPEN_PULL_REQUESTS_OPERATION] = [{"message": "Something went wrong"}]
    snapshot = await gather_pull_requests(gh_config, gh_client)
    assert snapshot.pull_requests == NOT_GATHERED
    problem = gh_problem(snapshot.problems, "the open pull requests")
    assert problem.why == "GitHub answered with an error"


# A list that runs past the pages one gather reads, and a comparison that does not say how long it is.


async def test_a_list_longer_than_one_gather_reads_is_not_gathered(gh_config: Config) -> None:
    """Twenty-five pages of tags at one tag a page: the newest tag is of the whole list or of none."""
    organisation = FakeOrganisation(
        login=ORGANISATION,
        repositories=(FakeRepository(name="atlas", tags=tuple(f"v0.{minor}.0" for minor in range(25))),),
    )
    fake = FakeGitHub(organisation=organisation, page_cap=1)
    async with default_http_client(gh_config, transport=fake.transport()) as client:
        snapshot = await gather(gh_config, client)
    atlas = gh_found(snapshot, "atlas")
    assert atlas.newest_tag == NOT_GATHERED
    problem = gh_problem(snapshot.problems, f"the newest tag of {ORGANISATION}/atlas")
    assert problem.why == "GitHub's list is longer than one gather reads"


async def test_a_packages_versions_longer_than_one_gather_reads_leave_no_dev_release(
    gh_config: Config,
) -> None:
    versions = tuple((f"sha-{index}",) for index in range(2001))
    organisation = FakeOrganisation(
        login=ORGANISATION,
        repositories=(FakeRepository(name="atlas", tags=("v1.0.0",), latest_release="v1.0.0"),),
        packages=(FakePackage(name="atlas", repository=f"{ORGANISATION}/atlas", versions=versions),),
    )
    fake = FakeGitHub(organisation=organisation)
    async with default_http_client(gh_config, transport=fake.transport()) as client:
        snapshot = await gather(gh_config, client)
    assert gh_found(snapshot, "atlas").dev_release == NOT_GATHERED
    problem = gh_problem(snapshot.problems, f"the dev release of {ORGANISATION}/atlas")
    assert problem.why == "GitHub's list is longer than one gather reads"


async def test_a_comparison_that_does_not_say_how_long_it_is_cannot_be_counted(
    gh_config: Config, gh_organisation: FakeOrganisation
) -> None:
    organisation = replace(
        gh_organisation,
        repositories=tuple(
            replace(repository, ahead_total_absent=True) if repository.name == "atlas" else repository
            for repository in gh_organisation.repositories
        ),
    )
    fake = FakeGitHub(organisation=organisation)
    async with default_http_client(gh_config, transport=fake.transport()) as client:
        snapshot = await gather(gh_config, client)
    atlas = gh_found(snapshot, "atlas")
    assert atlas.unreleased is not None
    assert atlas.unreleased.pull_requests == NOT_GATHERED
    assert atlas.back_merge_pending == Gathered(False)
    problem = gh_problem(snapshot.problems, f"the unreleased work of {ORGANISATION}/atlas")
    assert problem.why == "GitHub answered without it"
