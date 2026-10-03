# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""The overview, distilled from the full gather's `Snapshot` with no gather of its own.

Per repository (docs/what-it-shows.md, "The overview"): the release state (the
newest final version, and the dev version where it is newer), readiness, and
what waits on the reader (checks failing on either trunk; open pull requests
counted by the statuses that call for the reader; open issues). A repository
with nothing waiting is shown quietly; a fact not gathered counts as waiting,
since what is unknown is shown, not hidden (axiom 4).
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from packaging.version import InvalidVersion, Version

from hazel_tracking.model import (
    NOT_GATHERED,
    CheckState,
    DevRelease,
    Fact,
    Gathered,
    NotGathered,
    PullRequestStatus,
    Readiness,
    Repository,
    Snapshot,
    Unreleased,
)

# The pull-request statuses that call for the reader, in the order the overview counts them.
WAITING_STATUSES = (
    PullRequestStatus.READY,
    PullRequestStatus.CONFLICTS,
    PullRequestStatus.CHECKS_FAILING,
    PullRequestStatus.BEHIND,
)


@dataclass(frozen=True)
class OverviewRow:
    """One repository on the overview.

    `final_version` is the higher by version of the newest tag and the newest
    Release (R3). `failing_trunks` names each trunk whose checks fail; it is
    `NOT_GATHERED` where no trunk is known to fail and some trunk's checks were not
    gathered. `pull_requests_waiting` counts the open pull requests in each of
    `WAITING_STATUSES`, every status listed, zero included. `waiting` is false only
    when every fact is gathered and none calls for the reader.
    """

    name: str
    final_version: Fact[str | None]
    dev_release: Fact[DevRelease | None]
    unreleased: Unreleased | None
    readiness: Fact[Readiness] | None
    back_merge_pending: Fact[bool] | None
    failing_trunks: Fact[tuple[str, ...]]
    pull_requests_waiting: Fact[tuple[tuple[PullRequestStatus, int], ...]]
    open_issues: Fact[int]
    waiting: bool


def _version(name: str) -> Version | None:
    try:
        return Version(name.removeprefix("v"))
    except InvalidVersion:
        return None


def final_version(repo: Repository) -> Fact[str | None]:
    """The higher by version of the newest tag and the newest Release; not gathered if either is not."""
    if not (isinstance(repo.newest_tag, Gathered) and isinstance(repo.newest_release, Gathered)):
        return NOT_GATHERED
    names = [n for n in (repo.newest_tag.value, repo.newest_release.value) if n is not None]
    ranked = [(v, n) for n in names if (v := _version(n)) is not None]
    if ranked:
        return Gathered(max(ranked)[1])
    return Gathered(names[0] if names else None)


def failing_trunks(repo: Repository) -> Fact[tuple[str, ...]]:
    failing = tuple(c.trunk for c in repo.checks if c.state == Gathered(CheckState.FAILING))
    if failing or all(isinstance(c.state, Gathered) for c in repo.checks):
        return Gathered(failing)
    return NOT_GATHERED


def pull_requests_waiting(repo: Repository) -> Fact[tuple[tuple[PullRequestStatus, int], ...]]:
    if not isinstance(repo.pull_requests, Gathered):
        return NOT_GATHERED
    statuses = [p.status.value for p in repo.pull_requests.value if isinstance(p.status, Gathered)]
    return Gathered(tuple((s, statuses.count(s)) for s in WAITING_STATUSES))


def _calls_for_the_reader(row: OverviewRow) -> bool:
    facts: list[object] = [
        row.final_version,
        row.dev_release,
        row.failing_trunks,
        row.pull_requests_waiting,
        row.open_issues,
    ]
    facts += [f for f in (row.readiness, row.back_merge_pending) if f is not None]
    if any(isinstance(f, NotGathered) for f in facts):
        return True
    ready = isinstance(row.readiness, Gathered) and not row.readiness.value.failing
    return (
        ready
        or row.back_merge_pending == Gathered(True)
        or row.failing_trunks != Gathered(())
        or any(n for _, n in _gathered(row.pull_requests_waiting))
        or _gathered(row.open_issues) > 0
    )


def _gathered[T](fact: Fact[T]) -> T:
    assert isinstance(fact, Gathered)
    return fact.value


def overview_row(repo: Repository) -> OverviewRow:
    row = OverviewRow(
        name=repo.name,
        final_version=final_version(repo),
        dev_release=repo.dev_release,
        unreleased=repo.unreleased,
        readiness=repo.readiness,
        back_merge_pending=repo.back_merge_pending,
        failing_trunks=failing_trunks(repo),
        pull_requests_waiting=pull_requests_waiting(repo),
        open_issues=repo.open_issues,
        waiting=False,
    )
    return replace(row, waiting=_calls_for_the_reader(row))


def overview(snapshot: Snapshot) -> tuple[OverviewRow, ...]:
    """The overview's rows, one per repository of the snapshot, in the snapshot's order."""
    return tuple(overview_row(repo) for repo in snapshot.repositories)
