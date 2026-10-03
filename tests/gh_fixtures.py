# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""The gathering's pytest fixtures, loaded as a plugin from `tests/conftest.py`.

Their names carry the prefix `gh_`. `gh_organisation` is the synthetic organisation
the tests read: it is shaped like the one the Dashboard will read, with a repository
for each case the readings turn on (a repository ready to cut a release, one with
every condition failing, a website repository, one whose default branch is its only
trunk, one with no release and two packages, one whose statuses GitHub had not
computed, and an archived one that is counted and left out). `gh_github` answers
from it, `gh_config` names it, and `gh_client` is the client the gathering reads
through, built by `app.default_http_client` so that the seam under test is the one
the service uses.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterable
from zoneinfo import ZoneInfo

import httpx
import pytest

from hazel_tracking.app import default_http_client
from hazel_tracking.config import Config
from hazel_tracking.model import Problem, Repository, Snapshot
from tests.gh_fakes import (
    FakeAssociated,
    FakeCommit,
    FakeGitHub,
    FakeOrganisation,
    FakePackage,
    FakePullRequest,
    FakeRepository,
)

ORGANISATION = "ExampleOrg"


def gh_atlas() -> FakeRepository:
    """Ready to cut a release: one unreleased pull request, which changes the documentation, the
    checks on `develop` passing under a `[skip ci]` head, and no pending back-merge. Its newest
    tag is higher than its newest Release, and its dev release is older than both. One of its
    open pull requests is into `main` rather than the integration trunk, which the detail lists
    and the pull-requests tab leaves out."""
    return FakeRepository(
        name="atlas",
        issues=3,
        tags=("v0.1.0", "v0.2.0", "v0.10.0", "not-a-version"),
        latest_release="v0.2.0",
        branches=("feature-charts", "dependabot/pip/httpx-1.0.0", "hotfix-pick"),
        history={
            "develop": (FakeCommit("d2"), FakeCommit("d1", "SUCCESS")),
            "main": (FakeCommit("m1", "SUCCESS"),),
        },
        pulls=(
            FakePullRequest(number=9, head="feature-charts", title="feat: the charts"),
            FakePullRequest(
                number=10, head="dependabot/pip/httpx-1.0.0", title="build(deps): httpx", draft=True
            ),
            FakePullRequest(number=14, head="hotfix-pick", base="main", title="fix: the pick"),
        ),
        ahead=(
            FakeCommit("a1", pulls=(FakeAssociated(7, "feature-tables"),)),
            FakeCommit("a2", pulls=(FakeAssociated(7, "feature-tables"),)),
            FakeCommit("a3"),
            FakeCommit("a4", pulls=(FakeAssociated(6, "back-merge-v0.2.0"),)),
        ),
        branch_behind={"feature-charts": 2, "dependabot/pip/httpx-1.0.0": 0, "hotfix-pick": 0},
        files={7: ("src/atlas/core.py", "docs/guide.md")},
    )


def gh_basalt() -> FakeRepository:
    """Every condition of readiness failing at once: nothing unreleased, the checks on `develop`
    failing, and the previous release's back-merge pending."""
    return FakeRepository(
        name="basalt",
        tags=("v1.0.0",),
        latest_release="v1.0.0",
        history={"develop": (FakeCommit("d1", "FAILURE"),), "main": (FakeCommit("m1", "PENDING"),)},
        behind=3,
    )


def gh_brightwork() -> FakeRepository:
    """A website repository, whose trunks are `staging` and `live`: no readiness indicator, a
    pending back-merge in its place, and documentation under `site/`."""
    return FakeRepository(
        name="brightwork.example",
        default_branch="staging",
        branches=("doc-pages",),
        history={"staging": (FakeCommit("s1", "SUCCESS"),), "live": (FakeCommit("l1", "SUCCESS"),)},
        pulls=(FakePullRequest(number=4, head="doc-pages", title="docs: the pages", state="BEHIND"),),
        ahead=(FakeCommit("a1", pulls=(FakeAssociated(3, "doc-copy"),)),),
        behind=1,
        branch_behind={"doc-pages": 5},
        files={3: ("site/index.html",)},
    )


def gh_cedar() -> FakeRepository:
    """A repository whose default branch is its only trunk: no comparison and no readiness, and a
    working branch with no pull request open from it."""
    return FakeRepository(
        name="cedar",
        default_branch="main",
        tags=("v0.3.0",),
        latest_release="v0.3.0",
        branches=("claude",),
        history={"main": (FakeCommit("m1", "SUCCESS"),)},
        branch_behind={"claude": 7},
    )


def gh_fieldwork() -> FakeRepository:
    """No release of any kind, two packages, and a trunk with no checks at all: its dev release is
    shown, the highest of the two, there being no final release it could be older than."""
    return FakeRepository(
        name="fieldwork",
        issues=1,
        branches=("feature-sensors",),
        history={"develop": (FakeCommit("d1", "SUCCESS"),), "main": ()},
        pulls=(
            FakePullRequest(
                number=2, head="feature-sensors", title="feat: the sensors", mergeable="CONFLICTING"
            ),
        ),
        branch_behind={"feature-sensors": 0},
    )


def gh_quarry() -> FakeRepository:
    """Two statuses GitHub had not computed at the first read: one it computes at the second, and
    one it does not, which is then not gathered (R4). Its third open pull request is a release's
    back-merge, which the detail lists and the pull-requests tab leaves out (R5)."""
    return FakeRepository(
        name="quarry",
        tags=("v0.5.0",),
        latest_release="v0.5.0",
        branches=("fix-leak", "ops-runner", "back-merge-v0.5.0"),
        history={"develop": (FakeCommit("d1", "SUCCESS"),), "main": (FakeCommit("m1", "SUCCESS"),)},
        pulls=(
            FakePullRequest(
                number=11, head="fix-leak", title="fix: the leak", rollup=None, uncomputed_reads=1
            ),
            FakePullRequest(number=12, head="ops-runner", title="ops: the runner", uncomputed_reads=5),
            FakePullRequest(
                number=13,
                head="back-merge-v0.5.0",
                title="chore(release): back-merge main into develop after v0.5.0",
            ),
        ),
        branch_behind={"fix-leak": 1, "ops-runner": 0, "back-merge-v0.5.0": 0},
    )


def gh_dormant() -> FakeRepository:
    """An archived repository: counted in the status bar and shown nowhere."""
    return FakeRepository(name="dormant", archived=True, tags=("v9.0.0",))


def gh_packages() -> tuple[FakePackage, ...]:
    """The organisation's container packages: one whose dev release is older than its final
    release, one with untagged versions alone, two belonging to the same repository, and one that
    names no repository at all."""
    return (
        FakePackage(
            name="atlas",
            repository=f"{ORGANISATION}/atlas",
            versions=(("dev", "0.2.1.dev4", "sha-abc"), ("sha-def",)),
        ),
        FakePackage(name="basalt", repository=f"{ORGANISATION}/basalt", versions=(("sha-111",), ())),
        FakePackage(
            name="fieldwork", repository=f"{ORGANISATION}/fieldwork", versions=(("dev", "0.3.0.dev1"),)
        ),
        FakePackage(
            name="fieldwork-worker",
            repository=f"{ORGANISATION}/fieldwork",
            versions=(("dev", "0.4.0.dev2"), ("sha-222",)),
        ),
        FakePackage(name="orphan", repository=None, versions=(("dev", "9.9.9.dev1"),)),
    )


@pytest.fixture
def gh_organisation() -> FakeOrganisation:
    return FakeOrganisation(
        login=ORGANISATION,
        repositories=(
            gh_atlas(),
            gh_basalt(),
            gh_brightwork(),
            gh_cedar(),
            gh_dormant(),
            gh_fieldwork(),
            gh_quarry(),
        ),
        packages=gh_packages(),
    )


@pytest.fixture
def gh_github(gh_organisation: FakeOrganisation) -> FakeGitHub:
    return FakeGitHub(organisation=gh_organisation)


@pytest.fixture
def gh_config(sentinel_token: str) -> Config:
    """A configuration naming the synthetic organisation, the token a sentinel, and a wait long
    enough that only a test that delays an answer runs into it."""
    return Config(
        github_token=sentinel_token,
        github_org=ORGANISATION,
        github_api_url="http://github.invalid",
        wait_seconds=5.0,
        time_zone=ZoneInfo("Europe/London"),
    )


@pytest.fixture
async def gh_client(gh_config: Config, gh_github: FakeGitHub) -> AsyncIterator[httpx.AsyncClient]:
    """The client the gathering reads through, answered by the fake and never by the network."""
    async with default_http_client(gh_config, transport=gh_github.transport()) as client:
        yield client


def gh_found(snapshot: Snapshot, name: str) -> Repository:
    """The repository of that name in a snapshot, named without its owner."""
    full = f"{ORGANISATION}/{name}"
    found = next((one for one in snapshot.repositories if one.name == full), None)
    assert found is not None, f"{full} is not in the snapshot"
    return found


def gh_problem(problems: Iterable[Problem], what: str) -> Problem:
    """The problem whose `what` names this, for a test that reads one problem of several."""
    found = next((one for one in problems if what in one.what), None)
    assert found is not None, f"no problem names {what!r}"
    return found
