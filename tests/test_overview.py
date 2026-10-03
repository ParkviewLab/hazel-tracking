# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""The overview, distilled from the snapshot: the release state, readiness, what waits on the
reader, and the quiet repository with nothing waiting (docs/what-it-shows.md, "The overview")."""

from __future__ import annotations

from dataclasses import replace

from hazel_tracking.model import (
    NOT_GATHERED,
    CheckState,
    Gathered,
    PullRequest,
    PullRequestStatus,
    Readiness,
    ReleaseCondition,
    Repository,
    Snapshot,
    TrunkChecks,
)
from hazel_tracking.overview import WAITING_STATUSES, final_version, overview, overview_row
from tests.test_model import BEGAN, URL, develop_repository, single_trunk_repository, staging_repository


def quiet_repository() -> Repository:
    """A released repository with nothing waiting: nothing to release, checks passing, no pull
    request, no issue."""
    return replace(
        develop_repository(),
        open_issues=Gathered(0),
        newest_tag=Gathered("v0.1.3"),
        newest_release=Gathered("v0.1.3"),
        dev_release=Gathered(None),
        readiness=Gathered(Readiness(failing=frozenset({ReleaseCondition.NOTHING_TO_RELEASE}))),
        back_merge_pending=Gathered(False),
        checks=(
            TrunkChecks(trunk="main", state=Gathered(CheckState.PASSING)),
            TrunkChecks(trunk="develop", state=Gathered(CheckState.PASSING)),
        ),
        pull_requests=Gathered(()),
    )


def test_a_repository_with_nothing_waiting_is_quiet() -> None:
    row = overview_row(quiet_repository())
    assert not row.waiting
    assert row.final_version == Gathered("v0.1.3")
    assert row.failing_trunks == Gathered(())
    assert row.pull_requests_waiting == Gathered(tuple((s, 0) for s in WAITING_STATUSES))


def test_each_thing_that_waits_on_the_reader_makes_the_repository_waiting() -> None:
    quiet = quiet_repository()
    ready = Readiness(failing=frozenset())
    pull = PullRequest(number=9, url=f"{URL}/pull/9", status=Gathered(PullRequestStatus.READY))
    for changed in (
        replace(quiet, readiness=Gathered(ready)),
        replace(quiet, back_merge_pending=Gathered(True)),
        replace(
            quiet, checks=(TrunkChecks(trunk="main", state=Gathered(CheckState.FAILING)), quiet.checks[1])
        ),
        replace(quiet, pull_requests=Gathered((pull,))),
        replace(quiet, open_issues=Gathered(1)),
    ):
        assert overview_row(changed).waiting, changed


def test_a_draft_or_a_running_pull_request_does_not_wait_on_the_reader() -> None:
    quiet = quiet_repository()
    pulls = tuple(
        PullRequest(number=n, url=f"{URL}/pull/{n}", status=Gathered(s))
        for n, s in ((1, PullRequestStatus.DRAFT), (2, PullRequestStatus.CHECKS_RUNNING))
    )
    assert not overview_row(replace(quiet, pull_requests=Gathered(pulls))).waiting


def test_a_fact_not_gathered_is_shown_not_hidden() -> None:
    quiet = quiet_repository()
    assert overview_row(replace(quiet, open_issues=NOT_GATHERED)).waiting
    assert overview_row(single_trunk_repository()).waiting


def test_the_pull_requests_are_counted_by_the_statuses_that_call_for_the_reader() -> None:
    statuses = (
        PullRequestStatus.READY,
        PullRequestStatus.READY,
        PullRequestStatus.BEHIND,
        PullRequestStatus.DRAFT,
    )
    pulls = tuple(
        PullRequest(number=n, url=f"{URL}/pull/{n}", status=Gathered(s)) for n, s in enumerate(statuses)
    )
    row = overview_row(replace(quiet_repository(), pull_requests=Gathered(pulls)))
    assert row.pull_requests_waiting == Gathered(
        (
            (PullRequestStatus.READY, 2),
            (PullRequestStatus.CONFLICTS, 0),
            (PullRequestStatus.CHECKS_FAILING, 0),
            (PullRequestStatus.BEHIND, 1),
        )
    )


def test_failing_trunks_are_named_and_unknown_checks_are_not_gathered() -> None:
    repo = develop_repository()
    assert overview_row(repo).failing_trunks == Gathered(("develop",))
    unknown = replace(
        quiet_repository(),
        checks=(TrunkChecks(trunk="main", state=NOT_GATHERED), quiet_repository().checks[1]),
    )
    assert overview_row(unknown).failing_trunks == NOT_GATHERED


def test_the_final_version_is_the_higher_of_the_tag_and_the_release_by_version() -> None:
    repo = quiet_repository()
    assert final_version(
        replace(repo, newest_tag=Gathered("v1.10.0"), newest_release=Gathered("v1.9.0"))
    ) == Gathered("v1.10.0")
    assert final_version(
        replace(repo, newest_tag=Gathered("v1.1.0"), newest_release=Gathered("v1.2.0"))
    ) == Gathered("v1.2.0")
    assert final_version(
        replace(repo, newest_tag=Gathered("v0.1.4"), newest_release=Gathered(None))
    ) == Gathered("v0.1.4")
    assert final_version(replace(repo, newest_tag=Gathered(None), newest_release=Gathered(None))) == Gathered(
        None
    )
    assert final_version(replace(repo, newest_release=NOT_GATHERED)) == NOT_GATHERED


def test_the_overview_has_a_row_per_repository_in_the_snapshot_s_order() -> None:
    repos = (develop_repository(), staging_repository(), single_trunk_repository())
    snapshot = Snapshot(
        began_at=BEGAN,
        duration_seconds=1.0,
        completed=True,
        sources=("GitHub",),
        repositories=repos,
        archived=0,
        problems=(),
        rate_limit=None,
    )
    assert [row.name for row in overview(snapshot)] == [r.name for r in repos]
    assert overview(snapshot)[1].readiness is None


def test_a_pull_request_whose_status_was_not_gathered_is_shown_not_hidden() -> None:
    pull = PullRequest(number=4, url=f"{URL}/pull/4", status=NOT_GATHERED)
    row = overview_row(replace(quiet_repository(), pull_requests=Gathered((pull,))))
    assert row.pull_requests_waiting == NOT_GATHERED
    assert row.waiting
