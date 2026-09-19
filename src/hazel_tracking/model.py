# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""The contract between the gathering and the page: what one gather yields.

Frozen dataclasses and enumerations with no behaviour. The gathering
(`hazel_tracking.gather`) builds a `Snapshot`; the page (`hazel_tracking.page`)
shows it and reads nothing else. The words are those of docs/what-it-shows.md,
whose readings (R1 to R11) the docstrings cite, and no type here is shaped by
one source's interface.

Every fact is carried with its own state, `Gathered` or `NotGathered`, so that a
call that fails greys only the facts it feeds (R7). A fact that does not apply
to a repository, given its trunks (R1), is `None` rather than a `Fact`.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


@dataclass(frozen=True)
class Gathered[T]:
    """A fact the gather obtained. `value` is what the source gave, which may be empty
    (`None`, or an empty tuple): such a fact reads "none" in ordinary type (R7)."""

    value: T


@dataclass(frozen=True)
class NotGathered:
    """A fact the gather could not obtain: the page shows it zeroed and greyed (R7)."""


type Fact[T] = Gathered[T] | NotGathered

NOT_GATHERED = NotGathered()


class CheckState(StrEnum):
    """The state of the checks on a trunk's newest commit that has any (R2)."""

    PASSING = "passing"
    FAILING = "failing"
    RUNNING = "running"
    NONE = "none"


class PullRequestStatus(StrEnum):
    """An open pull request's status: the first of these that applies, in this order (R4)."""

    DRAFT = "draft"
    CONFLICTS = "conflicts"
    CHECKS_FAILING = "checks failing"
    CHECKS_RUNNING = "checks running"
    BEHIND = "behind its base"
    READY = "ready to merge"


class ReleaseCondition(StrEnum):
    """A condition of readiness to cut a release that fails; the indicator names each one (R6)."""

    NOTHING_TO_RELEASE = "nothing to release"
    CHECKS_FAILING = "checks failing on develop"
    BACK_MERGE_PENDING = "back-merge pending"


@dataclass(frozen=True)
class Trunks:
    """A repository's trunks, which its default branch decides (R1).

    `integration` is the default branch: `develop`, `staging`, or `main` alone.
    `release` is `main` where the default branch is `develop` and `live` where it
    is `staging`; `None` where the default branch is the only trunk, which has no
    comparison and no readiness.
    """

    integration: str
    release: str | None


@dataclass(frozen=True)
class TrunkChecks:
    """The checks on one trunk (R2)."""

    trunk: str
    state: Fact[CheckState]


@dataclass(frozen=True)
class DevRelease:
    """The newest dev release, where it is newer than the final release (R3).

    `version` is the dev version as published (`0.1.1.dev3`); `expired` says that
    its downloadable files have expired, which only installers kept as a dev
    build's artefacts do.
    """

    version: str
    expired: bool


@dataclass(frozen=True)
class Unreleased:
    """Unreleased work (R5): the merged pull requests among the commits the integration
    trunk has and the release trunk lacks, and whether any of them changes the
    documentation (the files under `docs/` and `site/`). The count is also how far the
    integration trunk is ahead of the release trunk, so the page shows the two as one line.
    """

    pull_requests: Fact[int]
    documentation: Fact[bool]


@dataclass(frozen=True)
class Readiness:
    """Ready to cut a release, for a repository whose trunks are `main` and `develop` (R6).

    Ready when `failing` is empty; otherwise `failing` holds every condition that
    fails. `documentation` says whether the unreleased work includes documentation,
    which the indicator notes.
    """

    failing: frozenset[ReleaseCondition]
    documentation: bool


@dataclass(frozen=True)
class WorkingBranch:
    """A branch other than the trunks (R1): how far it is behind the default branch, in
    commits the default branch has and it lacks, and whether a pull request is open from it."""

    name: str
    behind: Fact[int]
    pull_request_open: Fact[bool]


@dataclass(frozen=True)
class PullRequest:
    """An open pull request (R4)."""

    number: int
    status: Fact[PullRequestStatus]


@dataclass(frozen=True)
class Repository:
    """One repository and each of its facts.

    `name` is `owner/name`. `last_push` is aware, `None` where the source records no
    push. `newest_tag` is the highest version tag by version and `newest_release`
    the tag of the newest Release (R3), each `None` where there is none.
    `dev_release` is `None` where no dev release is newer than the final release.
    `unreleased` and `back_merge_pending` (the release trunk holding commits the
    integration trunk lacks) are `None` where there is no release trunk;
    `readiness` is `None` except where the trunks are `main` and `develop` (R6).
    `checks` holds one entry per trunk, the release trunk first.
    """

    name: str
    trunks: Trunks
    last_push: Fact[datetime | None]
    open_issues: Fact[int]
    newest_tag: Fact[str | None]
    newest_release: Fact[str | None]
    dev_release: Fact[DevRelease | None]
    unreleased: Unreleased | None
    readiness: Fact[Readiness] | None
    back_merge_pending: Fact[bool] | None
    checks: tuple[TrunkChecks, ...]
    working_branches: Fact[tuple[WorkingBranch, ...]]
    pull_requests: Fact[tuple[PullRequest, ...]]


@dataclass(frozen=True)
class ProblemDetail:
    """One call behind a problem, as the page's dialog lists it: the call, the HTTP
    status where an answer came, and the source's own message where it gave one."""

    call: str
    status: int | None
    message: str | None


@dataclass(frozen=True)
class Problem:
    """Something a gather could not obtain: what, why in one sentence, and the detail.

    It never holds a request header or a credential; a credential is named in
    general terms only, such as "the token was refused".
    """

    what: str
    why: str
    details: tuple[ProblemDetail, ...]


@dataclass(frozen=True)
class Snapshot:
    """What one gather yields.

    `began_at` is aware; `duration_seconds` is how long the gather took; `completed`
    says whether it completed within the wait (D7). `sources` names the sources the
    gather asked, in the page's words. `repositories` holds every repository whose
    name arrived, which is none if the list of repositories did not (R11), and
    `problems` everything that could not be gathered.
    """

    began_at: datetime
    duration_seconds: float
    completed: bool
    sources: tuple[str, ...]
    repositories: tuple[Repository, ...]
    problems: tuple[Problem, ...]


# What the page awaits for each snapshot: `install()` binds the gathering and its
# client to it, and a test of the page passes a stub.
type Gather = Callable[[], Awaitable[Snapshot]]
