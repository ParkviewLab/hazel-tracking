# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""The derivations the readings rule, read against docs/what-it-shows.md: the trunks a default
branch gives (R1), the commit the checks are judged on (R2), the newest version and the dev
release (R3), a pull request's status (R4), the unreleased work and the documentation mark (R5),
the conditions of readiness (R6), and the reading of GitHub's instants and its expiry header."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from hazel_tracking.github import facts
from hazel_tracking.github.calls import aware, expiry, redact
from hazel_tracking.model import CheckState, DevRelease, PullRequestStatus, ReleaseCondition, Trunks


def commit(rollup: str | None = None, oid: str = "abc") -> dict[str, object]:
    return {"oid": oid, "statusCheckRollup": {"state": rollup} if rollup else None}


def ref(*commits: dict[str, object]) -> dict[str, object]:
    return {"name": "develop", "target": {"history": {"nodes": list(commits)}}}


def pull(**given: object) -> dict[str, object]:
    """A pull request as GitHub answers it, clean and mergeable unless the test says otherwise."""
    rollup = given.pop("rollup", "SUCCESS")
    node: dict[str, object] = {
        "number": 1,
        "url": "https://github.com/ExampleOrg/atlas/pull/1",
        "isDraft": False,
        "mergeable": "MERGEABLE",
        "mergeStateStatus": "CLEAN",
        "baseRefName": "develop",
        "headRefName": "feature-x",
        "commits": {"nodes": [{"commit": commit(rollup if isinstance(rollup, str) else None)}]},
    }
    node.update(given)
    return node


# R1: the trunks and the working branches.


@pytest.mark.parametrize(
    ("default_branch", "expected"),
    [
        ("develop", Trunks(integration="develop", release="main")),
        ("staging", Trunks(integration="staging", release="live")),
        ("main", Trunks(integration="main", release=None)),
        ("trunk", Trunks(integration="trunk", release=None)),
        (None, Trunks(integration="", release=None)),
    ],
)
def test_the_default_branch_decides_the_trunks(default_branch: str | None, expected: Trunks) -> None:
    assert facts.trunks(default_branch) == expected


def test_every_branch_that_is_not_a_trunk_is_a_working_branch() -> None:
    shape = facts.trunks("develop")
    branches = ("main", "develop", "feature-x", "dependabot/pip/httpx-1.0.0", "back-merge-v0.1.0")
    assert facts.working_branches(branches, shape) == (
        "back-merge-v0.1.0",
        "dependabot/pip/httpx-1.0.0",
        "feature-x",
    )


def test_a_single_trunk_repository_counts_every_other_branch() -> None:
    assert facts.working_branches(("main", "claude"), facts.trunks("main")) == ("claude",)


# R2: the commit the checks are judged on.


def test_a_head_with_no_checks_is_passed_over() -> None:
    history = ref(commit(None, "skip-ci-head"), commit("SUCCESS", "parent"))
    assert facts.trunk_checks(history) is CheckState.PASSING
    assert facts.finished_checks(history) is CheckState.PASSING


def test_the_checks_read_the_newest_commit_that_has_any() -> None:
    assert facts.trunk_checks(ref(commit("PENDING"), commit("FAILURE"))) is CheckState.RUNNING
    assert facts.trunk_checks(ref(commit("FAILURE"))) is CheckState.FAILING
    assert facts.trunk_checks(ref(commit("ERROR"))) is CheckState.FAILING
    assert facts.trunk_checks(ref(commit("EXPECTED"))) is CheckState.RUNNING


def test_a_trunk_with_no_checked_commit_and_a_trunk_that_does_not_exist_read_none() -> None:
    assert facts.trunk_checks(ref(commit(None), commit(None))) is CheckState.NONE
    assert facts.trunk_checks(ref()) is CheckState.NONE
    assert facts.trunk_checks(None) is CheckState.NONE


def test_readiness_passes_over_a_commit_whose_checks_are_still_running() -> None:
    history = ref(commit("PENDING"), commit("FAILURE"))
    assert facts.trunk_checks(history) is CheckState.RUNNING
    assert facts.finished_checks(history) is CheckState.FAILING


def test_readiness_has_no_finished_commit_to_judge_where_none_ran_checks() -> None:
    assert facts.finished_checks(ref(commit("PENDING"), commit(None))) is None


# R3: the newest version, and the dev release beside it.


def test_the_newest_tag_is_the_highest_by_version_and_not_by_date() -> None:
    assert facts.highest_version(("v0.1.0", "v0.10.0", "v0.9.0")) == "v0.10.0"


def test_a_tag_that_is_not_a_version_is_not_the_newest() -> None:
    assert facts.highest_version(("not-a-version", "v1.2.3", "latest")) == "v1.2.3"
    assert facts.highest_version(("not-a-version",)) is None
    assert facts.highest_version(()) is None


def test_the_newest_tag_is_found_over_more_than_a_hundred_tags() -> None:
    tags = tuple(f"v0.{minor}.0" for minor in range(130))
    assert facts.highest_version(tags) == "v0.129.0"


@pytest.mark.parametrize(
    ("versions", "final", "expected"),
    [
        (("0.1.1.dev3",), "v0.1.0", DevRelease(version="0.1.1.dev3")),
        (("0.1.0.dev3",), "v0.1.0", None),
        (("0.1.0.dev3",), "v0.2.0", None),
        (("0.1.1.dev3",), None, DevRelease(version="0.1.1.dev3")),
        (("0.3.0.dev1", "0.4.0.dev2"), None, DevRelease(version="0.4.0.dev2")),
        ((), "v0.1.0", None),
    ],
)
def test_a_dev_release_is_shown_only_where_it_is_newer(
    versions: tuple[str, ...], final: str | None, expected: DevRelease | None
) -> None:
    assert facts.dev_release(versions, final) == expected


def test_the_dev_version_is_the_tag_beside_dev() -> None:
    assert facts.dev_versions(["dev", "0.2.1.dev4", "sha-abc"]) == ["0.2.1.dev4"]
    assert facts.dev_versions(["0.2.1.dev4", "sha-abc"]) == []
    assert facts.dev_versions(["dev", "sha-abc"]) == []
    assert facts.dev_versions([]) == []


# R4: a pull request's status.


def test_a_status_is_the_first_of_the_six_that_applies() -> None:
    assert facts.pull_request_status(pull(isDraft=True, mergeable="CONFLICTING")) is PullRequestStatus.DRAFT
    assert facts.pull_request_status(pull(mergeable="CONFLICTING", rollup="FAILURE")) is (
        PullRequestStatus.CONFLICTS
    )
    assert facts.pull_request_status(pull(mergeStateStatus="DIRTY")) is PullRequestStatus.CONFLICTS
    assert facts.pull_request_status(pull(rollup="FAILURE", mergeStateStatus="BEHIND")) is (
        PullRequestStatus.CHECKS_FAILING
    )
    assert facts.pull_request_status(pull(rollup="PENDING", mergeStateStatus="BEHIND")) is (
        PullRequestStatus.CHECKS_RUNNING
    )
    assert facts.pull_request_status(pull(mergeStateStatus="BEHIND")) is PullRequestStatus.BEHIND
    assert facts.pull_request_status(pull()) is PullRequestStatus.READY


def test_a_pull_request_with_no_checks_at_all_is_ready() -> None:
    assert facts.pull_request_status(pull(rollup=None)) is PullRequestStatus.READY


def test_a_status_github_has_not_computed_is_no_status_yet() -> None:
    assert facts.pull_request_status(pull(mergeable="UNKNOWN")) is None
    assert facts.pull_request_status(pull(mergeStateStatus="UNKNOWN")) is None
    assert facts.pull_request_status({"number": 1}) is None


def test_a_draft_is_a_draft_even_before_github_has_computed_the_rest() -> None:
    assert facts.pull_request_status(pull(isDraft=True, mergeable="UNKNOWN", mergeStateStatus="UNKNOWN")) is (
        PullRequestStatus.DRAFT
    )


# R5: the unreleased work and the documentation mark.


def compared(number: int | None, head: str = "feature-x", merged: bool = True) -> dict[str, object]:
    pulls = [] if number is None else [{"number": number, "headRefName": head, "merged": merged}]
    return {"oid": f"c{number}", "associatedPullRequests": {"nodes": pulls}}


def test_the_unreleased_work_counts_distinct_merged_pull_requests() -> None:
    commits = [compared(7), compared(7), compared(8, "fix-y")]
    assert facts.merged_pull_requests(commits) == {7: "feature-x", 8: "fix-y"}


def test_a_direct_commit_counts_as_no_pull_request() -> None:
    assert facts.merged_pull_requests([compared(None)]) == {}


def test_a_pull_request_that_is_not_merged_is_not_unreleased_work() -> None:
    assert facts.merged_pull_requests([compared(7, merged=False)]) == {}


def test_a_back_merge_is_left_out_of_the_unreleased_work() -> None:
    commits = [compared(6, "back-merge-v0.2.0"), compared(7)]
    assert facts.merged_pull_requests(commits) == {7: "feature-x"}


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("docs/guide.md", True),
        ("site/intro.html", True),
        ("docs/images/one.png", True),
        ("README.md", False),
        ("src/atlas/core.py", False),
        ("mydocs/guide.md", False),
        (None, False),
    ],
)
def test_the_documentation_mark_is_the_files_a_site_is_built_from(path: object, expected: bool) -> None:
    assert facts.is_documentation(path) is expected


def test_the_documentation_mark_holds_where_any_file_is_documentation() -> None:
    assert facts.documentation(["src/atlas/core.py", "docs/guide.md"]) is True
    assert facts.documentation(["src/atlas/core.py"]) is False
    assert facts.documentation([]) is False


# R6: the conditions of readiness.


def test_readiness_is_ready_when_every_condition_holds() -> None:
    assert facts.readiness(1, CheckState.PASSING, False).failing == frozenset()


def test_readiness_names_every_condition_that_fails() -> None:
    assert facts.readiness(0, CheckState.PASSING, False).failing == frozenset(
        {ReleaseCondition.NOTHING_TO_RELEASE}
    )
    assert facts.readiness(2, CheckState.FAILING, False).failing == frozenset(
        {ReleaseCondition.CHECKS_FAILING}
    )
    assert facts.readiness(2, CheckState.PASSING, True).failing == frozenset(
        {ReleaseCondition.BACK_MERGE_PENDING}
    )
    assert facts.readiness(0, CheckState.FAILING, True).failing == frozenset(
        {
            ReleaseCondition.NOTHING_TO_RELEASE,
            ReleaseCondition.CHECKS_FAILING,
            ReleaseCondition.BACK_MERGE_PENDING,
        }
    )


def test_checks_still_running_or_absent_are_not_a_condition_that_fails() -> None:
    assert facts.readiness(1, CheckState.RUNNING, False).failing == frozenset()
    assert facts.readiness(1, None, False).failing == frozenset()


# GitHub's instants, its expiry header, and the redaction of a message.


def test_an_instant_is_read_as_github_writes_it() -> None:
    assert aware("2026-10-03T14:03:12Z") == datetime(2026, 10, 3, 14, 3, 12, tzinfo=UTC)
    assert aware("2026-10-03T14:03:12+01:00") is not None
    assert aware("not an instant") is None
    assert aware(None) is None


def test_the_expiry_is_read_from_the_header_github_sends() -> None:
    assert expiry("2027-09-18 00:00:00 UTC") == datetime(2027, 9, 18, tzinfo=UTC)
    assert expiry("2027-09-18T00:00:00Z") == datetime(2027, 9, 18, tzinfo=UTC)
    assert expiry("2027-09-18 00:00:00 GMT") == datetime(2027, 9, 18, tzinfo=UTC)


def test_no_expiry_is_read_where_the_header_is_absent_or_not_an_instant() -> None:
    assert expiry(None) is None
    assert expiry("") is None
    assert expiry("whenever") is None
    assert expiry("the 18th of September UTC") is None


def test_a_message_names_the_token_in_general_terms(sentinel_token: str) -> None:
    redacted = redact(f"the token {sentinel_token} was refused", sentinel_token)
    assert redacted is not None
    assert sentinel_token not in redacted
    assert redacted == "the token the GitHub token was refused"


def test_a_message_is_carried_on_one_line_and_no_further_than_its_limit(sentinel_token: str) -> None:
    assert redact("  two\n  lines  ", sentinel_token) == "two lines"
    long = redact("x" * 500, sentinel_token)
    assert long is not None and len(long) == 300
    assert redact(None, sentinel_token) is None
