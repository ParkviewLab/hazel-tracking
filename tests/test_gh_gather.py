# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""The full gather against the fake GitHub: every fact of every repository, as
docs/what-it-shows.md's detail tab lists them, the archived count, the rate limit and the token's
expiry, R4's second read, and every list read to its end over as many calls as it takes."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

import httpx
import pytest

from hazel_tracking.app import default_http_client
from hazel_tracking.config import Config
from hazel_tracking.gather import SOURCES, gather
from hazel_tracking.github import queries
from hazel_tracking.model import (
    NOT_GATHERED,
    CheckState,
    DevRelease,
    Gathered,
    PullRequestRef,
    PullRequestStatus,
    ReleaseCondition,
    Trunks,
)
from tests.gh_fakes import FakeGitHub, FakeOrganisation, FakePackage, FakeRepository
from tests.gh_fixtures import ORGANISATION, gh_found


async def test_a_gather_that_wants_nothing_is_whole(gh_config: Config, gh_client: httpx.AsyncClient) -> None:
    snapshot = await gather(gh_config, gh_client)
    assert snapshot.completed
    assert snapshot.problems == ()
    assert snapshot.sources == SOURCES
    assert snapshot.began_at.tzinfo == gh_config.time_zone
    assert snapshot.duration_seconds >= 0


async def test_every_repository_appears_in_name_order_and_the_archived_are_counted(
    gh_config: Config, gh_client: httpx.AsyncClient
) -> None:
    snapshot = await gather(gh_config, gh_client)
    names = [repository.name for repository in snapshot.repositories]
    assert names == sorted(names)
    assert f"{ORGANISATION}/dormant" not in names
    assert snapshot.archived == 1


async def test_the_rate_limit_and_the_tokens_expiry_come_from_the_answers(
    gh_config: Config, gh_client: httpx.AsyncClient, gh_github: FakeGitHub
) -> None:
    snapshot = await gather(gh_config, gh_client)
    assert snapshot.rate_limit is not None
    assert snapshot.rate_limit.remaining == gh_github.remaining
    assert snapshot.rate_limit.resets_at.isoformat() == "2026-10-03T15:00:00+00:00"
    assert snapshot.credential_expires_at is not None
    assert snapshot.credential_expires_at.isoformat() == "2027-09-18T00:00:00+00:00"


async def test_no_expiry_is_reported_where_github_sends_no_header(
    gh_config: Config, gh_client: httpx.AsyncClient, gh_github: FakeGitHub
) -> None:
    gh_github.expiry = None
    snapshot = await gather(gh_config, gh_client)
    assert snapshot.credential_expires_at is None


async def test_the_token_travels_in_the_clients_header(
    gh_config: Config, gh_client: httpx.AsyncClient, gh_github: FakeGitHub, sentinel_token: str
) -> None:
    """The gather must really send the token, or every test that looks for it elsewhere is vacuous."""
    await gather(gh_config, gh_client)
    assert f"Bearer {sentinel_token}" in gh_github.credentials


async def test_a_repository_ready_to_cut_a_release(gh_config: Config, gh_client: httpx.AsyncClient) -> None:
    atlas = gh_found(await gather(gh_config, gh_client), "atlas")
    assert atlas.trunks == Trunks(integration="develop", release="main")
    assert atlas.open_issues == Gathered(3)
    assert atlas.last_push == Gathered(datetime.fromisoformat("2026-10-03T11:30:00+00:00"))
    assert atlas.newest_tag == Gathered("v0.10.0")
    assert atlas.newest_release == Gathered("v0.2.0")
    assert atlas.dev_release == Gathered(None)
    assert atlas.unreleased is not None
    assert atlas.unreleased.pull_requests == Gathered(1)
    assert atlas.unreleased.documentation == Gathered(True)
    assert atlas.readiness == Gathered(replace(atlas.readiness.value, failing=frozenset()))
    assert atlas.back_merge_pending == Gathered(False)
    assert [(check.trunk, check.state) for check in atlas.checks] == [
        ("main", Gathered(CheckState.PASSING)),
        ("develop", Gathered(CheckState.PASSING)),
    ]


async def test_a_bots_branch_and_one_with_no_lag_are_working_branches(
    gh_config: Config, gh_client: httpx.AsyncClient
) -> None:
    atlas = gh_found(await gather(gh_config, gh_client), "atlas")
    assert isinstance(atlas.working_branches, Gathered)
    branches = {branch.name: branch for branch in atlas.working_branches.value}
    assert set(branches) == {"feature-charts", "dependabot/pip/httpx-1.0.0", "hotfix-pick"}
    assert branches["feature-charts"].behind == Gathered(2)
    assert branches["feature-charts"].pull_request == Gathered(
        PullRequestRef(number=9, url=f"https://github.com/{ORGANISATION}/atlas/pull/9")
    )
    assert branches["dependabot/pip/httpx-1.0.0"].behind == Gathered(0)
    assert branches["dependabot/pip/httpx-1.0.0"].pull_request == Gathered(
        PullRequestRef(number=10, url=f"https://github.com/{ORGANISATION}/atlas/pull/10")
    )


async def test_every_open_pull_request_is_listed_with_its_status(
    gh_config: Config, gh_client: httpx.AsyncClient
) -> None:
    atlas = gh_found(await gather(gh_config, gh_client), "atlas")
    assert isinstance(atlas.pull_requests, Gathered)
    assert [(pull.number, pull.status) for pull in atlas.pull_requests.value] == [
        (9, Gathered(PullRequestStatus.READY)),
        (10, Gathered(PullRequestStatus.DRAFT)),
        (14, Gathered(PullRequestStatus.READY)),
    ]


async def test_a_repository_with_every_condition_of_readiness_failing(
    gh_config: Config, gh_client: httpx.AsyncClient
) -> None:
    basalt = gh_found(await gather(gh_config, gh_client), "basalt")
    assert basalt.readiness == Gathered(
        replace(
            basalt.readiness.value,
            failing=frozenset(
                {
                    ReleaseCondition.NOTHING_TO_RELEASE,
                    ReleaseCondition.CHECKS_FAILING,
                    ReleaseCondition.BACK_MERGE_PENDING,
                }
            ),
        )
    )
    assert basalt.back_merge_pending == Gathered(True)
    assert basalt.unreleased is not None
    assert basalt.unreleased.pull_requests == Gathered(0)
    assert basalt.unreleased.documentation == Gathered(False)
    assert [(check.trunk, check.state) for check in basalt.checks] == [
        ("main", Gathered(CheckState.RUNNING)),
        ("develop", Gathered(CheckState.FAILING)),
    ]
    assert basalt.working_branches == Gathered(())
    assert basalt.pull_requests == Gathered(())


async def test_a_website_repository_shows_a_pending_back_merge_and_no_readiness(
    gh_config: Config, gh_client: httpx.AsyncClient
) -> None:
    website = gh_found(await gather(gh_config, gh_client), "brightwork.example")
    assert website.trunks == Trunks(integration="staging", release="live")
    assert website.readiness is None
    assert website.back_merge_pending == Gathered(True)
    assert website.unreleased is not None
    assert website.unreleased.pull_requests == Gathered(1)
    assert website.unreleased.documentation == Gathered(True)
    assert [check.trunk for check in website.checks] == ["live", "staging"]
    assert website.newest_tag == Gathered(None)
    assert website.newest_release == Gathered(None)


async def test_a_repository_whose_default_branch_is_its_only_trunk(
    gh_config: Config, gh_client: httpx.AsyncClient
) -> None:
    cedar = gh_found(await gather(gh_config, gh_client), "cedar")
    assert cedar.trunks == Trunks(integration="main", release=None)
    assert cedar.unreleased is None
    assert cedar.readiness is None
    assert cedar.back_merge_pending is None
    assert [check.trunk for check in cedar.checks] == ["main"]
    assert isinstance(cedar.working_branches, Gathered)
    branch = cedar.working_branches.value[0]
    assert (branch.name, branch.behind, branch.pull_request) == ("claude", Gathered(7), Gathered(None))


async def test_a_repository_with_several_packages_takes_the_highest_dev_version(
    gh_config: Config, gh_client: httpx.AsyncClient
) -> None:
    fieldwork = gh_found(await gather(gh_config, gh_client), "fieldwork")
    assert fieldwork.dev_release == Gathered(DevRelease(version="0.4.0.dev2"))
    assert fieldwork.newest_tag == Gathered(None)
    assert [(check.trunk, check.state) for check in fieldwork.checks] == [
        ("main", Gathered(CheckState.NONE)),
        ("develop", Gathered(CheckState.PASSING)),
    ]
    assert isinstance(fieldwork.pull_requests, Gathered)
    assert fieldwork.pull_requests.value[0].status == Gathered(PullRequestStatus.CONFLICTS)


async def test_a_repository_with_no_package_has_no_dev_release(
    gh_config: Config, gh_client: httpx.AsyncClient
) -> None:
    assert gh_found(await gather(gh_config, gh_client), "cedar").dev_release == Gathered(None)


async def test_a_status_github_had_not_computed_is_read_once_more(
    gh_config: Config, gh_client: httpx.AsyncClient, gh_github: FakeGitHub
) -> None:
    quarry = gh_found(await gather(gh_config, gh_client), "quarry")
    assert isinstance(quarry.pull_requests, Gathered)
    statuses = {pull.number: pull.status for pull in quarry.pull_requests.value}
    assert statuses[11] == Gathered(PullRequestStatus.READY)
    assert statuses[12] == NOT_GATHERED
    assert gh_github.asked(queries.STATUSES_OPERATION) == 1


async def test_no_second_read_is_sent_where_github_computed_every_status(gh_config: Config) -> None:
    organisation = FakeOrganisation(login=ORGANISATION, repositories=(FakeRepository(name="atlas"),))
    fake = FakeGitHub(organisation=organisation)
    async with default_http_client(gh_config, transport=fake.transport()) as client:
        await gather(gh_config, client)
    assert fake.asked(queries.STATUSES_OPERATION) == 0


async def test_a_release_back_merge_branch_is_a_working_branch_and_its_pull_request_is_listed(
    gh_config: Config, gh_client: httpx.AsyncClient
) -> None:
    """The detail lists every open pull request; only the unreleased count and the pull-requests
    tab leave a back-merge out (R5)."""
    quarry = gh_found(await gather(gh_config, gh_client), "quarry")
    assert isinstance(quarry.working_branches, Gathered)
    assert "back-merge-v0.5.0" in {branch.name for branch in quarry.working_branches.value}
    assert isinstance(quarry.pull_requests, Gathered)
    assert 13 in {pull.number for pull in quarry.pull_requests.value}


async def test_the_open_issues_are_asked_for_without_the_open_pull_requests() -> None:
    """GitHub's own figure for open issues counts pull requests too, so the query asks for issues
    alone."""
    assert "issues(states: OPEN) { totalCount }" in queries.REPOSITORIES


async def test_every_list_is_read_to_its_end_however_many_calls_it_takes(
    gh_config: Config, gh_organisation: FakeOrganisation
) -> None:
    """The same facts, whether each list arrives in one page or one item at a time: the
    repositories, the tags, the branches, the open pull requests, the compared commits and a pull
    request's files are each read to their end."""
    whole = FakeGitHub(organisation=gh_organisation)
    paged = FakeGitHub(organisation=gh_organisation, page_cap=1)
    async with default_http_client(gh_config, transport=whole.transport()) as client:
        first = await gather(gh_config, client)
    async with default_http_client(gh_config, transport=paged.transport()) as client:
        second = await gather(gh_config, client)
    assert second.problems == ()
    assert second.repositories == first.repositories
    assert second.archived == first.archived
    assert len(paged.calls) > len(whole.calls)


async def test_a_rest_list_is_read_past_its_first_page(gh_config: Config) -> None:
    """A package with more versions than one REST page holds: the dev version on the last page is
    found all the same."""
    versions = [(f"sha-{index}",) for index in range(100)] + [("dev", "2.0.0.dev7")]
    organisation = FakeOrganisation(
        login=ORGANISATION,
        repositories=(FakeRepository(name="atlas", tags=("v1.0.0",), latest_release="v1.0.0"),),
        packages=(FakePackage(name="atlas", repository=f"{ORGANISATION}/atlas", versions=versions),),
    )
    fake = FakeGitHub(organisation=organisation)
    async with default_http_client(gh_config, transport=fake.transport()) as client:
        snapshot = await gather(gh_config, client)
    assert gh_found(snapshot, "atlas").dev_release == Gathered(DevRelease(version="2.0.0.dev7"))
    assert fake.asked("versions:atlas") == 2


@pytest.mark.parametrize("cap", [1, 2, 3])
async def test_the_pages_of_a_pull_requests_files_are_read_until_the_documentation_is_found(
    gh_config: Config, gh_organisation: FakeOrganisation, cap: int
) -> None:
    fake = FakeGitHub(organisation=gh_organisation, page_cap=cap)
    async with default_http_client(gh_config, transport=fake.transport()) as client:
        snapshot = await gather(gh_config, client)
    atlas = gh_found(snapshot, "atlas")
    assert atlas.unreleased is not None
    assert atlas.unreleased.documentation == Gathered(True)
