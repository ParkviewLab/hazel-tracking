# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""The gather of the open pull requests alone, which the pull-requests tab and its watch use: one
search, filtered to the pull requests into the integration trunks with the back-merges left out,
Dependabot's kept, each with its R4 status, in the order of their repositories and numbers
(docs/what-it-shows.md, "The pull requests")."""

from __future__ import annotations

from dataclasses import replace

import httpx

from hazel_tracking.app import default_http_client
from hazel_tracking.config import Config
from hazel_tracking.gather import gather_pull_requests
from hazel_tracking.github import queries
from hazel_tracking.model import NOT_GATHERED, Fact, Gathered, OpenPullRequest, PullRequestStatus
from tests.gh_fakes import (
    FakeGitHub,
    FakeOrganisation,
    FakePullRequest,
    FakeRepository,
    server_error,
)
from tests.gh_fixtures import ORGANISATION, gh_problem, gh_uncomputed


def listed(gathered: Fact[tuple[OpenPullRequest, ...]]) -> list[tuple[str, int]]:
    assert isinstance(gathered, Gathered)
    return [(one.repository, one.pull_request.number) for one in gathered.value]


async def test_one_search_answers_the_tab(
    gh_config: Config, gh_client: httpx.AsyncClient, gh_github: FakeGitHub
) -> None:
    snapshot = await gather_pull_requests(gh_config, gh_client)
    assert snapshot.completed
    assert snapshot.problems == ()
    assert snapshot.began_at.tzinfo == gh_config.time_zone
    assert gh_github.asked(queries.OPEN_PULL_REQUESTS_OPERATION) == 1
    assert gh_github.asked(queries.REPOSITORIES_OPERATION) == 0
    assert "packages" not in gh_github.calls


async def test_the_search_asks_for_the_open_pull_requests_of_the_organisation(gh_config: Config) -> None:
    assert queries.search_query(gh_config.github_org) == f"org:{ORGANISATION} is:pr is:open archived:false"


async def test_the_pull_requests_come_in_the_order_of_their_repositories_and_numbers(
    gh_config: Config, gh_client: httpx.AsyncClient
) -> None:
    snapshot = await gather_pull_requests(gh_config, gh_client)
    assert listed(snapshot.pull_requests) == sorted(listed(snapshot.pull_requests))


async def test_a_pull_request_into_anything_but_the_integration_trunk_is_left_out(
    gh_config: Config, gh_client: httpx.AsyncClient
) -> None:
    """atlas has one open pull request into `main`; the tab lists the integration trunks alone."""
    snapshot = await gather_pull_requests(gh_config, gh_client)
    assert (f"{ORGANISATION}/atlas", 14) not in listed(snapshot.pull_requests)
    assert (f"{ORGANISATION}/atlas", 9) in listed(snapshot.pull_requests)


async def test_a_releases_back_merge_is_left_out(gh_config: Config, gh_client: httpx.AsyncClient) -> None:
    snapshot = await gather_pull_requests(gh_config, gh_client)
    assert (f"{ORGANISATION}/quarry", 13) not in listed(snapshot.pull_requests)
    assert (f"{ORGANISATION}/quarry", 11) in listed(snapshot.pull_requests)


async def test_dependabots_pull_request_is_kept(gh_config: Config, gh_client: httpx.AsyncClient) -> None:
    snapshot = await gather_pull_requests(gh_config, gh_client)
    assert (f"{ORGANISATION}/atlas", 10) in listed(snapshot.pull_requests)


async def test_a_pull_request_into_a_staging_trunk_is_kept(
    gh_config: Config, gh_client: httpx.AsyncClient
) -> None:
    snapshot = await gather_pull_requests(gh_config, gh_client)
    assert (f"{ORGANISATION}/brightwork.example", 4) in listed(snapshot.pull_requests)


async def test_each_pull_request_carries_its_title_its_link_and_its_status(
    gh_config: Config, gh_client: httpx.AsyncClient
) -> None:
    snapshot = await gather_pull_requests(gh_config, gh_client)
    assert isinstance(snapshot.pull_requests, Gathered)
    found = {one.pull_request.number: one for one in snapshot.pull_requests.value}
    assert found[9].title == "feat: the charts"
    assert found[9].pull_request.url == f"https://github.com/{ORGANISATION}/atlas/pull/9"
    assert found[9].pull_request.status == Gathered(PullRequestStatus.READY)
    assert found[10].pull_request.status == Gathered(PullRequestStatus.DRAFT)
    assert found[4].pull_request.status == Gathered(PullRequestStatus.BEHIND)
    assert found[2].pull_request.status == Gathered(PullRequestStatus.CONFLICTS)


async def test_a_status_github_had_not_computed_is_read_once_more(
    gh_config: Config, gh_client: httpx.AsyncClient, gh_github: FakeGitHub
) -> None:
    snapshot = await gather_pull_requests(gh_config, gh_client)
    assert isinstance(snapshot.pull_requests, Gathered)
    statuses = {one.pull_request.number: one.pull_request.status for one in snapshot.pull_requests.value}
    assert statuses[11] == Gathered(PullRequestStatus.READY)
    assert gh_github.asked(queries.STATUSES_OPERATION) == 1
    assert snapshot.problems == ()


async def test_a_status_still_uncomputed_at_the_second_read_is_a_problem_of_its_own(
    gh_config: Config,
) -> None:
    fake = FakeGitHub(organisation=gh_uncomputed())
    async with default_http_client(gh_config, transport=fake.transport()) as client:
        snapshot = await gather_pull_requests(gh_config, client)
    assert isinstance(snapshot.pull_requests, Gathered)
    assert snapshot.pull_requests.value[0].pull_request.status == NOT_GATHERED
    problem = gh_problem(snapshot.problems, f"the status of {ORGANISATION}/quarry#12")
    assert problem.why == "GitHub had not computed it, asked a second time"


async def test_the_search_is_read_to_its_end(gh_config: Config, gh_organisation: FakeOrganisation) -> None:
    whole = FakeGitHub(organisation=gh_organisation)
    paged = FakeGitHub(organisation=gh_organisation, page_cap=1)
    async with default_http_client(gh_config, transport=whole.transport()) as client:
        first = await gather_pull_requests(gh_config, client)
    async with default_http_client(gh_config, transport=paged.transport()) as client:
        second = await gather_pull_requests(gh_config, client)
    assert second.pull_requests == first.pull_requests
    assert paged.asked(queries.OPEN_PULL_REQUESTS_OPERATION) > 1


async def test_a_search_page_that_fails_leaves_the_tab_with_no_list(
    gh_config: Config, gh_organisation: FakeOrganisation
) -> None:
    """The first page answers and the second fails: a list read in part is not the list of what is
    open, so none of it is gathered."""
    fake = FakeGitHub(organisation=gh_organisation, page_cap=1)
    failure = server_error()
    failure.after = 1
    fake.failures[queries.OPEN_PULL_REQUESTS_OPERATION] = failure
    async with default_http_client(gh_config, transport=fake.transport()) as client:
        snapshot = await gather_pull_requests(gh_config, client)
    assert snapshot.pull_requests == NOT_GATHERED
    problem = gh_problem(snapshot.problems, "the open pull requests")
    assert problem.why == "GitHub failed on the call"


async def test_an_organisation_with_nothing_open_gathers_an_empty_list(gh_config: Config) -> None:
    """A fact gathered and found empty is not a fact that could not be gathered (R7)."""
    organisation = FakeOrganisation(
        login=ORGANISATION,
        repositories=(FakeRepository(name="atlas"), FakeRepository(name="dormant", archived=True)),
    )
    fake = FakeGitHub(organisation=organisation)
    async with default_http_client(gh_config, transport=fake.transport()) as client:
        snapshot = await gather_pull_requests(gh_config, client)
    assert snapshot.pull_requests == Gathered(())
    assert snapshot.problems == ()


async def test_a_pull_request_in_an_archived_repository_is_not_listed(gh_config: Config) -> None:
    """GitHub's search leaves archived repositories out; the fake answers as it does, and the tab
    shows nothing from one."""
    organisation = FakeOrganisation(
        login=ORGANISATION,
        repositories=(
            FakeRepository(
                name="dormant",
                archived=True,
                pulls=(FakePullRequest(number=1, head="feature-old"),),
            ),
        ),
    )
    fake = FakeGitHub(organisation=organisation)
    async with default_http_client(gh_config, transport=fake.transport()) as client:
        snapshot = await gather_pull_requests(gh_config, client)
    assert snapshot.pull_requests == Gathered(())


async def test_a_gather_cut_short_after_the_search_keeps_the_list_it_answered(
    gh_config: Config, gh_organisation: FakeOrganisation
) -> None:
    """The search answered and the second read of the uncomputed statuses did not: the list stands,
    marked incomplete, with those statuses greyed (R11)."""
    fake = FakeGitHub(organisation=gh_organisation, delays={queries.STATUSES_OPERATION: 0.5})
    cfg = replace(gh_config, wait_seconds=0.05)
    async with default_http_client(cfg, transport=fake.transport()) as client:
        snapshot = await gather_pull_requests(cfg, client)
    assert not snapshot.completed
    assert (f"{ORGANISATION}/quarry", 11) in listed(snapshot.pull_requests)
    assert isinstance(snapshot.pull_requests, Gathered)
    statuses = {one.pull_request.number: one.pull_request.status for one in snapshot.pull_requests.value}
    assert statuses[11] == NOT_GATHERED
    assert statuses[9] == Gathered(PullRequestStatus.READY)
    problem = gh_problem(snapshot.problems, "the facts GitHub had not yet given")
    assert any("status" in detail.call for detail in problem.details)
