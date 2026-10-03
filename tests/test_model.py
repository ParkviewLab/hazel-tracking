# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""The contract of model.py: a snapshot can be built for each shape of repository, every fact
carries its own state, nothing in it can be changed, and the enumerations are the rulings'."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime

import pytest

from hazel_tracking import model
from hazel_tracking.model import (
    NOT_GATHERED,
    CheckState,
    DevRelease,
    Gathered,
    NotGathered,
    Problem,
    ProblemDetail,
    PullRequest,
    PullRequestStatus,
    Readiness,
    ReleaseCondition,
    Repository,
    Snapshot,
    TrunkChecks,
    Trunks,
    Unreleased,
    WorkingBranch,
)

BEGAN = datetime(2026, 9, 18, 21, 3, 12, tzinfo=UTC)


def develop_repository() -> Repository:
    """A repository whose trunks are main and develop, one of its calls failed."""
    return Repository(
        name="ParkviewLab/hazel-tracking",
        trunks=Trunks(integration="develop", release="main"),
        last_push=Gathered(BEGAN),
        open_issues=Gathered(2),
        newest_tag=Gathered("v0.1.0"),
        newest_release=Gathered(None),
        dev_release=Gathered(DevRelease(version="0.1.1.dev7", expired=False)),
        unreleased=Unreleased(pull_requests=Gathered(3), documentation=NOT_GATHERED),
        readiness=Gathered(
            Readiness(failing=frozenset({ReleaseCondition.CHECKS_FAILING}), documentation=True)
        ),
        back_merge_pending=Gathered(False),
        checks=(
            TrunkChecks(trunk="main", state=Gathered(CheckState.PASSING)),
            TrunkChecks(trunk="develop", state=Gathered(CheckState.FAILING)),
        ),
        working_branches=Gathered(
            (
                WorkingBranch(name="feature-page", behind=Gathered(0), pull_request_open=Gathered(True)),
                WorkingBranch(
                    name="dependabot/uv/httpx", behind=NOT_GATHERED, pull_request_open=Gathered(False)
                ),
            )
        ),
        pull_requests=Gathered(
            (
                PullRequest(number=2, status=Gathered(PullRequestStatus.CHECKS_RUNNING)),
                PullRequest(number=3, status=NOT_GATHERED),
            )
        ),
    )


def staging_repository() -> Repository:
    """A website repository: live and staging, no readiness, a back-merge pending (R6)."""
    return Repository(
        name="ParkviewLab/parkviewlab.ai",
        trunks=Trunks(integration="staging", release="live"),
        last_push=Gathered(BEGAN),
        open_issues=Gathered(0),
        newest_tag=Gathered(None),
        newest_release=Gathered(None),
        dev_release=Gathered(None),
        unreleased=Unreleased(pull_requests=Gathered(0), documentation=Gathered(False)),
        readiness=None,
        back_merge_pending=Gathered(True),
        checks=(
            TrunkChecks(trunk="live", state=Gathered(CheckState.NONE)),
            TrunkChecks(trunk="staging", state=Gathered(CheckState.RUNNING)),
        ),
        working_branches=Gathered(()),
        pull_requests=Gathered(()),
    )


def single_trunk_repository() -> Repository:
    """A repository whose default branch is its only trunk: no comparison, no readiness (R1)."""
    return Repository(
        name="ParkviewLab/example",
        trunks=Trunks(integration="main", release=None),
        last_push=NOT_GATHERED,
        open_issues=NOT_GATHERED,
        newest_tag=NOT_GATHERED,
        newest_release=NOT_GATHERED,
        dev_release=NOT_GATHERED,
        unreleased=None,
        readiness=None,
        back_merge_pending=None,
        checks=(TrunkChecks(trunk="main", state=NOT_GATHERED),),
        working_branches=NOT_GATHERED,
        pull_requests=NOT_GATHERED,
    )


def test_a_snapshot_holds_each_shape_of_repository_and_its_problems() -> None:
    problem = Problem(
        what="the packages",
        why="The token was refused.",
        details=(ProblemDetail(call="GET /orgs/ParkviewLab/packages", status=403, message="Forbidden"),),
    )
    snapshot = Snapshot(
        began_at=BEGAN,
        duration_seconds=3.1,
        completed=True,
        sources=("GitHub",),
        repositories=(develop_repository(), staging_repository(), single_trunk_repository()),
        problems=(problem,),
    )
    assert [r.trunks.release for r in snapshot.repositories] == ["main", "live", None]
    assert snapshot.problems[0].details[0].status == 403


def test_a_gather_not_complete_before_the_list_arrived_holds_no_repository() -> None:
    """R11: the columns and no rows; the problem names each call outstanding."""
    outstanding = tuple(
        ProblemDetail(call=call, status=None, message=None) for call in ("repositories", "packages")
    )
    snapshot = Snapshot(
        began_at=BEGAN,
        duration_seconds=15.0,
        completed=False,
        sources=("GitHub",),
        repositories=(),
        problems=(
            Problem(what="everything", why="GitHub did not answer within the wait.", details=outstanding),
        ),
    )
    assert not snapshot.completed
    assert snapshot.repositories == ()
    assert len(snapshot.problems[0].details) == 2


def test_every_fact_carries_its_own_state() -> None:
    repo = develop_repository()
    assert isinstance(repo.unreleased, Unreleased)
    assert repo.unreleased.pull_requests == Gathered(3)
    assert isinstance(repo.unreleased.documentation, NotGathered)
    assert isinstance(repo.working_branches, Gathered)
    assert [b.behind for b in repo.working_branches.value] == [Gathered(0), NOT_GATHERED]


def test_a_fact_found_empty_is_gathered_not_missing() -> None:
    """R7: a gathered fact found empty reads "none"; only a fact not gathered is greyed."""
    assert Gathered(None) != NOT_GATHERED
    assert Gathered(()) != NOT_GATHERED
    assert NotGathered() == NOT_GATHERED


def test_facts_that_do_not_apply_are_none() -> None:
    repo = single_trunk_repository()
    assert (repo.unreleased, repo.readiness, repo.back_merge_pending) == (None, None, None)
    assert staging_repository().readiness is None


def test_nothing_in_the_model_can_be_changed() -> None:
    repo = develop_repository()
    with pytest.raises(dataclasses.FrozenInstanceError):
        repo.name = "ParkviewLab/other"  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        repo.checks[0].state = NOT_GATHERED  # type: ignore[misc]
    with pytest.raises(AttributeError):
        repo.checks.append(repo.checks[0])  # type: ignore[attr-defined]
    for name, value in vars(model).items():
        if isinstance(value, type) and dataclasses.is_dataclass(value):
            assert value.__dataclass_params__.frozen, name  # type: ignore[attr-defined]


def test_readiness_is_ready_when_no_condition_fails_and_names_every_one_that_does() -> None:
    assert not Readiness(failing=frozenset(), documentation=False).failing
    every = frozenset(ReleaseCondition)
    assert Readiness(failing=every, documentation=True).failing == every
    assert [c.value for c in ReleaseCondition] == [
        "nothing to release",
        "checks failing on develop",
        "back-merge pending",
    ]


def test_the_pull_request_statuses_are_in_the_ruled_order() -> None:
    """R4: the first that applies of draft, conflicts, checks failing, checks running, behind its base, ready."""
    assert [s.value for s in PullRequestStatus] == [
        "draft",
        "conflicts",
        "checks failing",
        "checks running",
        "behind its base",
        "ready to merge",
    ]


def test_the_check_states() -> None:
    assert [s.value for s in CheckState] == ["passing", "failing", "running", "none"]


def test_no_field_of_the_model_holds_a_header_or_a_credential() -> None:
    for name, value in vars(model).items():
        if isinstance(value, type) and dataclasses.is_dataclass(value):
            for f in dataclasses.fields(value):
                assert not any(word in f.name for word in ("header", "token", "secret", "password")), (
                    name,
                    f.name,
                )
