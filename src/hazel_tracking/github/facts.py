# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""The derivations the readings rule, as pure functions of what GitHub answered.

Every rule that turns GitHub's words into the page's lives here and nowhere else:
the trunks a default branch gives (R1), the commit a trunk's checks are judged on
(R2), the newest version and the dev release beside it (R3), a pull request's
status (R4), the unreleased pull requests and the documentation mark (R5), and the
conditions of readiness (R6). The functions take GitHub's nodes as mappings and
answer in the words of `model.py`, so that each reading can be read against
docs/what-it-shows.md and tested without a call.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from packaging.version import InvalidVersion, Version

from hazel_tracking.github.calls import dig, nodes
from hazel_tracking.model import (
    CheckState,
    DevRelease,
    PullRequestStatus,
    Readiness,
    ReleaseCondition,
    Trunks,
)

# The release trunk each default branch gives; a default branch not named here is a
# repository's only trunk, with no comparison and no readiness (R1).
RELEASE_TRUNKS = {"develop": "main", "staging": "live"}

# The branches whose merged pull requests are not unreleased work: `git back-merge` opens one
# at the end of every release (R5).
BACK_MERGE_PREFIX = "back-merge-"

# The documentation the mark stands for: the files a documentation site is built from (R5).
DOCUMENTATION_DIRECTORIES = ("docs/", "site/")

# A version tag, as every tag in the organisation is written and as R3 reads the newest: `vX.Y.Z`
# and nothing else, so that a tag such as `v1.2.3rc1` or `0.1.0` is not the newest final version.
VERSION_TAG = re.compile(r"^v\d+\.\d+\.\d+$")

# GitHub's rollup states, in the words of the page. EXPECTED is a check GitHub has been told to
# expect and has not received, which reads as running like a pending one.
_ROLLUP_STATES = {
    "SUCCESS": CheckState.PASSING,
    "FAILURE": CheckState.FAILING,
    "ERROR": CheckState.FAILING,
    "PENDING": CheckState.RUNNING,
    "EXPECTED": CheckState.RUNNING,
}
_FINISHED = (CheckState.PASSING, CheckState.FAILING)


def trunks(default_branch: str | None) -> Trunks:
    """A repository's trunks, which its default branch decides (R1).

    A repository with no default branch has no commits and so no trunk to name; it is shown
    with no comparison and no readiness, like one whose default branch is its only trunk.
    """
    if not default_branch:
        return Trunks(integration="", release=None)
    return Trunks(integration=default_branch, release=RELEASE_TRUNKS.get(default_branch))


def working_branches(branches: Iterable[str], shape: Trunks) -> tuple[str, ...]:
    """Every branch that is not a trunk, in name order, whoever made it: a bot's branch counts,
    and so does one holding nothing the default branch lacks (R1)."""
    trunk_names = {shape.integration, shape.release}
    return tuple(sorted(name for name in branches if name not in trunk_names))


def rollup_state(commit: Any) -> CheckState | None:
    """What the checks on one commit say, and `None` where it has none: the commit a release's
    changelog made with `[skip ci]` has none, which is how R2 passes it over."""
    state = dig(commit, "statusCheckRollup", "state")
    return _ROLLUP_STATES.get(state) if isinstance(state, str) else None


def trunk_checks(ref: Any) -> CheckState:
    """The checks on a trunk: those of its newest commit that has any, finished or running, and
    `NONE` where no commit in the history read has any, or where the trunk does not exist (R2)."""
    for commit in nodes(dig(ref, "target", "history")):
        state = rollup_state(commit)
        if state is not None:
            return state
    return CheckState.NONE


def finished_checks(ref: Any) -> CheckState | None:
    """The checks on the trunk's latest commit that ran them, which readiness is judged on: the
    newest commit whose checks have finished, a commit still running passed over, and `None`
    where no commit in the history read has finished checks (R2)."""
    for commit in nodes(dig(ref, "target", "history")):
        state = rollup_state(commit)
        if state in _FINISHED:
            return state
    return None


def version(name: str) -> Version | None:
    """A tag as a version, the leading `v` set aside; `None` where it is not one."""
    try:
        return Version(name.removeprefix("v"))
    except InvalidVersion:
        return None


def highest_version(names: Iterable[str]) -> str | None:
    """The highest by version of these names, as the name itself, by version and not by date;
    `None` where none of them is a version. Any version PEP 440 reads counts, which is what a dev
    version (`0.2.1.dev4`) needs; for a tag, `highest_tag` is the stricter reading R3 rules."""
    ranked = [(parsed, name) for name in names if (parsed := version(name)) is not None]
    return max(ranked)[1] if ranked else None


def highest_tag(names: Iterable[str]) -> str | None:
    """The newest version tag: the highest `vX.Y.Z` by version and not by date, as the tag itself
    (R3). A tag of any other form is not a final version and is passed over, a pre-release
    (`v1.2.3rc1`) and an unprefixed version (`0.1.0`) alike."""
    return highest_version(name for name in names if VERSION_TAG.match(name))


def dev_release(dev_versions: Iterable[str], final: str | None) -> DevRelease | None:
    """The newest dev release where it is newer than the final release, and `None` otherwise.

    The dev version is compared with the higher of the newest tag and the newest Release, which
    `final` carries; a repository with several packages takes the highest among them (R3). A
    repository with no final release at all shows its dev release, there being nothing it could
    be older than.
    """
    highest = highest_version(dev_versions)
    if highest is None:
        return None
    released = version(final) if final else None
    newest = version(highest)
    if newest is None or (released is not None and newest <= released):
        return None
    return DevRelease(version=highest)


def head_checks(pull: Any) -> CheckState:
    """The checks on a pull request's head commit, `NONE` where it has none."""
    head = next(iter(nodes(dig(pull, "commits"))), None)
    return rollup_state(dig(head, "commit")) or CheckState.NONE


def pull_request_status(pull: Any) -> PullRequestStatus | None:
    """A pull request's status: the first of R4's six that applies, and `None` where GitHub has
    not computed it (`UNKNOWN`), which is read once more and else not gathered."""
    if dig(pull, "isDraft"):
        return PullRequestStatus.DRAFT
    mergeable, state = dig(pull, "mergeable"), dig(pull, "mergeStateStatus")
    if mergeable == "CONFLICTING" or state == "DIRTY":
        return PullRequestStatus.CONFLICTS
    if mergeable in (None, "UNKNOWN") or state in (None, "UNKNOWN"):
        # Whether it conflicts comes before whether its checks pass, so a status read whilst GitHub
        # has yet to compute the merge is no status at all, however the checks stand: it is read
        # once more. Only draft, which nothing else can displace, is settled before this.
        return None
    checks = head_checks(pull)
    if checks is CheckState.FAILING:
        return PullRequestStatus.CHECKS_FAILING
    if checks is CheckState.RUNNING:
        return PullRequestStatus.CHECKS_RUNNING
    if state == "BEHIND":
        return PullRequestStatus.BEHIND
    return PullRequestStatus.READY


def merged_pull_requests(commits: Iterable[Any]) -> dict[int, str]:
    """The merged pull requests among the compared commits, by number, with each one's head
    branch: distinct, the back-merges of releases left out, and direct commits not counted at
    all, since a commit that belongs to no pull request contributes none (R5)."""
    found: dict[int, str] = {}
    for commit in commits:
        for pull in nodes(dig(commit, "associatedPullRequests")):
            number, head = dig(pull, "number"), dig(pull, "headRefName")
            if not dig(pull, "merged") or not isinstance(number, int):
                continue
            head = head if isinstance(head, str) else ""
            if head.startswith(BACK_MERGE_PREFIX):
                continue
            found[number] = head
    return found


def is_documentation(path: Any) -> bool:
    """Whether a changed file is one the documentation site is built from (R5). The README does
    not count: GitHub shows it from the integration trunk as soon as a pull request merges."""
    return isinstance(path, str) and path.startswith(DOCUMENTATION_DIRECTORIES)


def documentation(paths: Iterable[Any]) -> bool:
    return any(is_documentation(path) for path in paths)


def readiness(unreleased: int, integration_checks: CheckState | None, back_merge_pending: bool) -> Readiness:
    """Ready to cut a release, with every condition that fails named (R6).

    The checks condition fails only where the integration trunk's latest commit that ran checks
    failed: where no commit in the history read has finished checks, as in a repository that
    runs none, there is nothing that fails, and the indicator says so rather than naming a
    failure GitHub has not reported (axiom 1).
    """
    failing: set[ReleaseCondition] = set()
    if unreleased == 0:
        failing.add(ReleaseCondition.NOTHING_TO_RELEASE)
    if integration_checks is CheckState.FAILING:
        failing.add(ReleaseCondition.CHECKS_FAILING)
    if back_merge_pending:
        failing.add(ReleaseCondition.BACK_MERGE_PENDING)
    return Readiness(failing=frozenset(failing))


def dev_versions(tags: Sequence[Any]) -> list[str]:
    """The dev version a package version's tags carry: the tag beside `dev` that parses as a
    version. A version not tagged `dev` is not a dev release, whatever else it is tagged."""
    named = [tag for tag in tags if isinstance(tag, str)]
    if "dev" not in named:
        return []
    return [tag for tag in named if tag != "dev" and version(tag) is not None]


def container_tags(package_version: Any) -> list[Any]:
    """The tags GitHub's REST answer records for one container package version."""
    tags = dig(package_version, "metadata", "container", "tags")
    return list(tags) if isinstance(tags, list) else []


def repository_of(package: Any) -> str | None:
    """The repository a package belongs to, which its `repository.full_name` names."""
    name = dig(package, "repository", "full_name")
    return name if isinstance(name, str) else None


def package_name(package: Any) -> str | None:
    name = dig(package, "name")
    return name if isinstance(name, str) else None


def default_branch(repository: Any) -> str | None:
    name = dig(repository, "defaultBranchRef", "name")
    return name if isinstance(name, str) else None


def trunk_ref(repository: Mapping[str, Any], trunk: str | None, integration: str | None) -> Any:
    """The ref the repositories query answered with for one trunk: the default branch's own, or
    the candidate `main` or `live` the query asks for by name beside it."""
    if trunk is None:
        return None
    if trunk == integration:
        return repository.get("defaultBranchRef")
    return repository.get("mainTrunk") if trunk == "main" else repository.get("liveTrunk")
