# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""The full gather: every repository of the organisation and each of its facts.

`collect` sends the calls and writes what they answer into a `FullState` as each
answer arrives, so that `gather` can build a snapshot from it whether the gather
completed or the wait cut it short (R11). The calls, in the order they depend on
one another:

- the repositories query, page by page to its end: each repository's name, default
  branch, last push, open issues, newest Release, every tag and branch, its trunks'
  recent history with the check rollups R2 reads, and its open pull requests with
  what R4 reads;
- alongside it, over REST, the organisation's container packages and the versions of
  each, from which the dev releases come (R3, R9): GraphQL does not expose packages
  at all;
- then, for a repository whose tags, branches or open pull requests ran past one
  page, the rest of that list, since each is a list a definition needs whole;
- then, together, the comparisons and the second read of any pull-request status
  GitHub had not computed (R4). The comparisons are REST's: one call for a
  repository's trunks, which gives how far the integration trunk is ahead, the
  commits it is ahead by, and whether the release trunk holds anything it lacks, and
  one for each working branch, which gives its lag (R1, R5, R6). GraphQL's
  `Ref.compare` is not used, because it refuses `aheadBy`, `behindBy` and `status` to
  a token without the `repo` scope, which this token does not have and by ruling D10
  must not have (live, 2026-10-03);
- then, over GraphQL, what the compared commits belong to, by the oids REST gave:
  their merged pull requests, with the head branch each one is from, which is what the
  unreleased work counts (R5);
- then the changed files of those pull requests, for the documentation mark (R5).

Every call that fails costs the facts it feeds and nothing else: the fact is left
not gathered and a problem names it (R7, axiom 8).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any
from urllib.parse import quote

from hazel_tracking.config import Config
from hazel_tracking.github import facts, problems, queries
from hazel_tracking.github.calls import (
    PAGE_LIMIT,
    REST_PAGE,
    Reader,
    Reply,
    aware,
    dig,
    nodes,
    page_cursor,
    too_long,
)
from hazel_tracking.github.collecting import groups, guard, lost, report, second_read
from hazel_tracking.model import (
    NOT_GATHERED,
    CheckState,
    DevRelease,
    Fact,
    Gathered,
    Problem,
    PullRequest,
    PullRequestRef,
    PullRequestStatus,
    Readiness,
    Repository,
    TrunkChecks,
    Trunks,
    Unreleased,
    WorkingBranch,
)

logger = logging.getLogger(__name__)

# The trunks for which the readiness indicator is shown (R6); the website repositories, whose
# trunks are `staging` and `live`, show a pending back-merge in its place.
RELEASE_READY_TRUNKS = Trunks(integration="develop", release="main")

_TAGS, _BRANCHES, _PULLS = "tags", "branches", "pulls"


@dataclass
class RepositoryState:
    """One repository as the gather fills it in, before it is frozen into the contract.

    A list that is `None` is one that was not gathered, which is not the same as one gathered
    and found empty: a repository with no tag has `tags == []` and its newest tag reads "none"
    (R7). A list is written only when it has been read to its end, what has arrived of it waiting in
    `reading` or `reading_pulls` until then, so that a list still being read when the wait runs out
    is not gathered rather than published part-read (R11).

    `merged` is the merged pull requests among the commits the integration trunk has and the release
    trunk lacks, by number with each one's head branch, written when every call feeding it has
    answered. `files_pending` is true whilst the unreleased work is still being read, which is what
    leaves the documentation mark ungathered until it is settled.
    """

    name: str
    repository: str
    trunks: Trunks
    last_push: Fact[datetime | None] = NOT_GATHERED
    open_issues: Fact[int] = NOT_GATHERED
    newest_release: Fact[str | None] = NOT_GATHERED
    tags: list[str] | None = None
    branches: list[str] | None = None
    reading: dict[str, list[str]] = field(default_factory=dict)
    reading_pulls: list[PullRequest] | None = None
    checks: dict[str, Fact[CheckState]] = field(default_factory=dict)
    integration_checks: CheckState | None = None
    integration_read: bool = False
    behind: dict[str, Fact[int]] = field(default_factory=dict)
    pulls: list[PullRequest] | None = None
    heads: dict[str, PullRequestRef] = field(default_factory=dict)
    uncomputed: set[int] = field(default_factory=set)
    merged: dict[int, str] | None = None
    back_merge_pending: Fact[bool] = NOT_GATHERED
    files_pending: bool = False
    documentation_found: bool = False
    documentation_failed: bool = False
    cursors: dict[str, str | None] = field(default_factory=dict)

    def working_branch_names(self) -> tuple[str, ...]:
        return facts.working_branches(self.branches or (), self.trunks)

    def to_model(self, dev_release: Fact[DevRelease | None]) -> Repository:
        """This repository in the words of the contract, every fact it lacks not gathered."""
        counted = self.merged is not None
        unreleased_count: Fact[int] = Gathered(len(self.merged or {})) if counted else NOT_GATHERED
        has_release_trunk = self.trunks.release is not None
        return Repository(
            name=self.name,
            trunks=self.trunks,
            last_push=self.last_push,
            open_issues=self.open_issues,
            newest_tag=NOT_GATHERED if self.tags is None else Gathered(facts.highest_tag(self.tags)),
            newest_release=self.newest_release,
            dev_release=dev_release,
            unreleased=Unreleased(unreleased_count, self._documentation()) if has_release_trunk else None,
            readiness=self._readiness(unreleased_count),
            back_merge_pending=self.back_merge_pending if has_release_trunk else None,
            checks=tuple(TrunkChecks(trunk=trunk, state=state) for trunk, state in self.checks.items()),
            working_branches=self._working_branches(),
            pull_requests=NOT_GATHERED if self.pulls is None else Gathered(tuple(self.pulls)),
        )

    def _documentation(self) -> Fact[bool]:
        """The documentation mark (R5). A mark one pull request has proved true stands whatever
        became of the others: no further file can make it false."""
        if self.documentation_found:
            return Gathered(True)
        if self.merged is None or self.files_pending or self.documentation_failed:
            return NOT_GATHERED
        return Gathered(False)

    def _readiness(self, unreleased: Fact[int]) -> Fact[Readiness] | None:
        """Readiness, for a repository whose trunks are `main` and `develop` alone (R6), and not
        gathered where any of its three conditions could not be judged."""
        if self.trunks != RELEASE_READY_TRUNKS:
            return None
        if not isinstance(unreleased, Gathered) or not isinstance(self.back_merge_pending, Gathered):
            return NOT_GATHERED
        if not self.integration_read:
            return NOT_GATHERED
        return Gathered(
            facts.readiness(unreleased.value, self.integration_checks, self.back_merge_pending.value)
        )

    def _working_branches(self) -> Fact[tuple[WorkingBranch, ...]]:
        if self.branches is None:
            return NOT_GATHERED
        return Gathered(
            tuple(
                WorkingBranch(
                    name=name,
                    behind=self.behind.get(name, NOT_GATHERED),
                    pull_request=NOT_GATHERED if self.pulls is None else Gathered(self.heads.get(name)),
                )
                for name in self.working_branch_names()
            )
        )


@dataclass
class FullState:
    """What the full gather has collected so far.

    `archived` counts the archived repositories left out, and is written only where the list of
    repositories was read to its end, since a count of some of the pages is no count (R11).
    `dev_versions` is `None` until the packages answer, and holds the dev versions published for each
    repository that has any; `dev_pending` counts the packages of a repository still being read and
    `dev_failures` names the repositories whose package could not be read, whose dev release alone is
    ungathered in either case.
    """

    repositories: list[RepositoryState] = field(default_factory=list)
    archived: int | None = None
    dev_versions: dict[str, list[str]] | None = None
    dev_pending: dict[str, int] = field(default_factory=dict)
    dev_failures: set[str] = field(default_factory=set)
    problems: list[Problem] = field(default_factory=list)

    def to_model(self) -> tuple[Repository, ...]:
        """Every repository whose name arrived, in name order, as the contract holds it."""
        ordered = sorted(self.repositories, key=lambda state: state.name)
        return tuple(state.to_model(self._dev_release(state)) for state in ordered)

    def _dev_release(self, state: RepositoryState) -> Fact[DevRelease | None]:
        """The dev release where it is newer than the final release (R3), and not gathered where
        the packages, or the final release it is compared with, could not be read."""
        if self.dev_versions is None or state.name in self.dev_failures:
            return NOT_GATHERED
        if self.dev_pending.get(state.name):
            return NOT_GATHERED
        if state.tags is None or not isinstance(state.newest_release, Gathered):
            return NOT_GATHERED
        # The newest tag is R3's `vX.Y.Z`; the newest Release is whatever GitHub's latest Release is
        # tagged, so the higher of the two is taken by any version either name reads as.
        newest_tag = facts.highest_tag(state.tags)
        named = [name for name in (newest_tag, state.newest_release.value) if name]
        final = facts.highest_version(named) or (named[0] if named else None)
        return Gathered(facts.dev_release(self.dev_versions.get(state.name, []), final))


async def collect(cfg: Config, reader: Reader, state: FullState) -> None:
    """Send the full gather's calls and write their answers into `state`."""
    async with asyncio.TaskGroup() as group:
        group.create_task(_repositories_and_what_follows(cfg, reader, state))
        group.create_task(guard(state.problems, "the dev releases", _dev_releases(cfg, reader, state)))


async def _repositories_and_what_follows(cfg: Config, reader: Reader, state: FullState) -> None:
    await guard(state.problems, "every repository's facts", _repositories(cfg, reader, state))
    if not state.repositories:
        return
    await guard(state.problems, "the lists GitHub answered in part", _continuations(cfg, reader, state))
    async with asyncio.TaskGroup() as group:
        group.create_task(
            guard(state.problems, "the unreleased work and the branch lag", _comparisons(cfg, reader, state))
        )
        group.create_task(
            guard(
                state.problems,
                "the status of each pull request GitHub had not computed",
                _second_read(cfg, reader, state),
            )
        )


async def _repositories(cfg: Config, reader: Reader, state: FullState) -> None:
    """The repositories query, page by page to its end.

    Archived repositories are counted and left out: GitHub's organisation connection cannot
    filter them, so they are read with the rest and dropped, which also makes the count and the
    list one answer.
    """
    cursor: str | None = None
    archived = 0
    whole = True
    for number in range(1, PAGE_LIMIT + 1):
        call = problems.page(problems.REPOSITORIES, number)
        reply = await reader.graphql(
            call,
            queries.REPOSITORIES_OPERATION,
            queries.REPOSITORIES,
            {
                "org": cfg.github_org,
                "cursor": cursor,
                "repositories": queries.REPOSITORIES_PAGE,
                "refs": queries.REFS_PAGE,
                "pulls": queries.PULL_REQUESTS_PAGE,
                "history": queries.HISTORY_DEPTH,
            },
        )
        connection = dig(reply.data, "organization", "repositories")
        if reply.failure is not None or connection is None:
            what = "every repository's facts" if number == 1 else "the repositories GitHub had not yet listed"
            report(state.problems, cfg, what, reply)
            whole = False
        if connection is None:
            return
        if not isinstance(dig(connection, "nodes"), list):
            # The one loss that is total: without this list there is no repository to show at all,
            # so an answer whose shape cannot be read is reported rather than read as empty.
            report(state.problems, cfg, "every repository's facts", Reply(call=call))
            return
        for node in nodes(connection):
            archived += _read_repository(state, node)
        cursor = page_cursor(connection)
        if cursor is None:
            if whole:
                # The count is a count of the whole list, so it is written only where the whole list
                # arrived; the repositories that did arrive stand either way (R11).
                state.archived = archived
            return
    state.problems.append(
        problems.from_failure("the repositories GitHub had not yet listed", too_long(call), cfg.time_zone)
    )


def _read_repository(state: FullState, node: Any) -> int:
    """One repository of the answer, archived ones left out; returns 1 where one was counted.

    A list GitHub answered in full here is written as the fact it feeds; one it answered in part
    waits in `reading` until the rest of it has been read, and one it answered with a null is left
    not gathered, since a null is a loss and not an empty list.
    """
    name = dig(node, "nameWithOwner")
    if not isinstance(name, str):
        return 0
    if dig(node, "isArchived"):
        return 1
    shape = facts.trunks(facts.default_branch(node))
    repository = RepositoryState(name=name, repository=name.rpartition("/")[2], trunks=shape)
    repository.last_push = Gathered(aware(dig(node, "pushedAt")))
    issues = dig(node, "issues", "totalCount")
    repository.open_issues = Gathered(issues) if isinstance(issues, int) else NOT_GATHERED
    release = dig(node, "latestRelease", "tagName")
    repository.newest_release = Gathered(release if isinstance(release, str) else None)
    for kind in (_TAGS, _BRANCHES):
        connection = dig(node, kind)
        if connection is None:
            continue
        names = [found for found in (dig(ref, "name") for ref in nodes(connection)) if isinstance(found, str)]
        cursor = page_cursor(connection)
        if cursor is None:
            setattr(repository, kind, names)  # `kind` is the field's own name, `tags` or `branches`
        else:
            repository.reading[kind] = names
            repository.cursors[kind] = cursor
    for trunk in (shape.release, shape.integration):
        if trunk:
            repository.checks[trunk] = Gathered(
                facts.trunk_checks(facts.trunk_ref(node, trunk, shape.integration))
            )
    if shape.integration:
        integration = facts.trunk_ref(node, shape.integration, shape.integration)
        repository.integration_checks = facts.finished_checks(integration)
        repository.integration_read = True
    pulls = dig(node, "pullRequests")
    if pulls is not None:
        staged = _read_pull_requests(repository, nodes(pulls), [])
        cursor = page_cursor(pulls)
        if cursor is None:
            repository.pulls = staged
        else:
            repository.reading_pulls = staged
            repository.cursors[_PULLS] = cursor
    state.repositories.append(repository)
    return 0


def _read_pull_requests(
    repository: RepositoryState, pull_nodes: list[Any], into: list[PullRequest]
) -> list[PullRequest]:
    """The open pull requests of one repository, with their statuses (R4) and the branch each
    one is open from, which is how a working branch finds its pull request.

    A branch is matched on its name and on the repository it is in, so that a pull request from a
    fork's branch of the same name is not read as this repository's branch; where two pull requests
    are open from one branch, the lower number is the one the branch carries.
    """
    for pull in pull_nodes:
        number, url = dig(pull, "number"), dig(pull, "url")
        if not isinstance(number, int):
            continue
        address = url if isinstance(url, str) else ""
        status = facts.pull_request_status(pull)
        if status is None:
            repository.uncomputed.add(number)
        into.append(
            PullRequest(
                number=number, url=address, status=NOT_GATHERED if status is None else Gathered(status)
            )
        )
        head = dig(pull, "headRefName")
        from_here = dig(pull, "headRepository", "nameWithOwner") == repository.name
        if isinstance(head, str) and from_here:
            open_already = repository.heads.get(head)
            if open_already is None or number < open_already.number:
                repository.heads[head] = PullRequestRef(number=number, url=address)
    return into


async def _continuations(cfg: Config, reader: Reader, state: FullState) -> None:
    """The rest of every list one page did not hold. They are read before the comparisons, which
    need the whole list of branches to know what to compare; each list is written as the fact it
    feeds only when it has been read to its end."""
    async with asyncio.TaskGroup() as group:
        for repository in state.repositories:
            for kind in (_TAGS, _BRANCHES):
                if repository.cursors.get(kind):
                    what = f"the {kind} of {repository.name}"
                    group.create_task(
                        guard(state.problems, what, _more_refs(cfg, reader, state, repository, kind))
                    )
            if repository.cursors.get(_PULLS):
                what = f"the open pull requests of {repository.name}"
                group.create_task(guard(state.problems, what, _more_pulls(cfg, reader, state, repository)))


async def _more_refs(
    cfg: Config, reader: Reader, state: FullState, repository: RepositoryState, kind: str
) -> None:
    """The rest of a repository's tags or branches.

    A list that cannot be read to its end is not gathered at all: the newest tag by version, and
    which branches exist, are facts of the whole list (R1, R3).
    """
    prefix = "refs/tags/" if kind == _TAGS else "refs/heads/"
    call = problems.of_repository(f"the {kind}", repository.name)
    what = f"the {'newest tag' if kind == _TAGS else 'branches'} of {repository.name}"
    cursor = repository.cursors.get(kind)
    found = repository.reading.get(kind, [])
    for number in range(2, PAGE_LIMIT + 1):
        page = problems.page(call, number)
        reply = await reader.graphql(
            page,
            queries.REFS_OPERATION,
            queries.REFS,
            {
                "owner": cfg.github_org,
                "name": repository.repository,
                "prefix": prefix,
                "cursor": cursor,
                "refs": queries.REFS_PAGE,
            },
        )
        connection = dig(reply.data, "repository", "refs")
        if reply.failure is not None or connection is None:
            report(state.problems, cfg, what, reply)
            return
        found.extend(name for ref in nodes(connection) if isinstance(name := dig(ref, "name"), str))
        cursor = page_cursor(connection)
        if cursor is None:
            setattr(repository, kind, found)  # `kind` is the field's own name, `tags` or `branches`
            return
    state.problems.append(problems.from_failure(what, too_long(call), cfg.time_zone))


async def _more_pulls(cfg: Config, reader: Reader, state: FullState, repository: RepositoryState) -> None:
    """The rest of a repository's open pull requests. Read to its end or not gathered: which
    branch has a pull request open from it is a fact of the whole list."""
    call = problems.of_repository("the open pull requests", repository.name)
    what = f"the open pull requests of {repository.name}"
    cursor = repository.cursors.get(_PULLS)
    staged = repository.reading_pulls if repository.reading_pulls is not None else []
    for number in range(2, PAGE_LIMIT + 1):
        reply = await reader.graphql(
            problems.page(call, number),
            queries.REPOSITORY_PULL_REQUESTS_OPERATION,
            queries.REPOSITORY_PULL_REQUESTS,
            {
                "owner": cfg.github_org,
                "name": repository.repository,
                "cursor": cursor,
                "pulls": queries.PULL_REQUESTS_PAGE,
            },
        )
        connection = dig(reply.data, "repository", "pullRequests")
        if reply.failure is not None or connection is None:
            repository.heads.clear()
            repository.uncomputed.clear()
            report(state.problems, cfg, what, reply)
            return
        _read_pull_requests(repository, nodes(connection), staged)
        cursor = page_cursor(connection)
        if cursor is None:
            repository.pulls = staged
            return
    repository.heads.clear()
    repository.uncomputed.clear()
    state.problems.append(problems.from_failure(what, too_long(call), cfg.time_zone))


async def _second_read(cfg: Config, reader: Reader, state: FullState) -> None:
    """R4's second read, for the statuses the repositories query answered as uncomputed."""
    by_name = {
        repository.name: repository for repository in state.repositories if repository.pulls is not None
    }
    targets = [
        (name, number) for name, repository in by_name.items() for number in sorted(repository.uncomputed)
    ]

    def publish(name: str, number: int, status: PullRequestStatus) -> None:
        _set_status(by_name[name], number, status)

    await second_read(cfg, reader, state.problems, targets, publish)


def _set_status(repository: RepositoryState, number: int, status: PullRequestStatus) -> None:
    if repository.pulls is None:
        return
    repository.pulls = [
        replace(pull, status=Gathered(status)) if pull.number == number else pull for pull in repository.pulls
    ]


async def _comparisons(cfg: Config, reader: Reader, state: FullState) -> None:
    """The comparisons, each repository on its own: its trunks' and each working branch's.

    A repository's unreleased work is read as one chain, the comparison and then what the commits it
    gave belong to and then the files of those pull requests, so that it starts as soon as that
    repository's own comparison has answered and one repository's loss is no other's (axiom 8).
    """
    async with asyncio.TaskGroup() as group:
        for repository in state.repositories:
            if not repository.trunks.integration:
                continue
            release = repository.trunks.release
            if release is not None:
                what = f"the unreleased work of {repository.name}"
                group.create_task(
                    guard(state.problems, what, _unreleased(cfg, reader, state, repository, release))
                )
            for branch in repository.working_branch_names():
                what = f"the lag of the branch {branch} of {repository.name}"
                group.create_task(
                    guard(state.problems, what, _branch_lag(cfg, reader, state, repository, branch))
                )


async def _unreleased(
    cfg: Config, reader: Reader, state: FullState, repository: RepositoryState, release: str
) -> None:
    """One repository's unreleased work, end to end (R5).

    Each fact is written only when every call feeding it has answered: the count when the comparison
    and every commit of it have been read, the documentation mark when the files have. Whilst the
    chain runs, `files_pending` keeps the mark ungathered, and it stays set where the chain is cut
    short by the wait or by an answer that could not be read.
    """
    repository.files_pending = True
    oids = await _trunk_comparison(cfg, reader, state, repository, release)
    if oids is None:
        repository.files_pending = False
        return
    merged = await _commits_of(cfg, reader, state, repository, oids) if oids else {}
    if merged is None:
        repository.files_pending = False
        return
    repository.merged = merged
    if merged:
        await _files_of(cfg, reader, state, repository, merged)
    repository.files_pending = False


def _compare_path(cfg: Config, repository: RepositoryState, base: str, head: str) -> str:
    """REST's comparison of two refs of one repository, `base...head`. A branch name's slashes
    belong to the name and are left as they are, which is the form GitHub's comparison takes."""
    refs = quote(f"{base}...{head}", safe="/.")
    return f"/repos/{cfg.github_org}/{repository.repository}/compare/{refs}"


async def _trunk_comparison(
    cfg: Config, reader: Reader, state: FullState, repository: RepositoryState, release: str
) -> list[str] | None:
    """The oids of the commits the integration trunk has and the release trunk lacks, and `None`
    where the comparison could not be read whole (R5, R6).

    Whether the release trunk holds any commit the integration trunk lacks comes from the same
    answer and stands on its own. The comparison is read page by page for its commits, 100 a
    page, to the page guard; where GitHub stops listing before its own total, the guard is reached,
    or the answer does not say how long the comparison is, the count cannot be made.
    """
    integration = repository.trunks.integration
    call = problems.of_repository(problems.COMPARISON, repository.name)
    what = f"the unreleased work of {repository.name}"
    path = _compare_path(cfg, repository, release, integration)
    oids: list[str] = []
    total = 0
    for number in range(1, PAGE_LIMIT + 1):
        reply = await reader.rest(problems.page(call, number), path, {"per_page": REST_PAGE, "page": number})
        comparison = reply.data if isinstance(reply.data, Mapping) else None
        if comparison is None:
            report(state.problems, cfg, what, reply)
            if number == 1:
                report(state.problems, cfg, f"a pending back-merge of {repository.name}", reply)
            return None
        if number == 1:
            behind = comparison.get("behind_by")
            repository.back_merge_pending = Gathered(behind > 0) if isinstance(behind, int) else NOT_GATHERED
            counted = comparison.get("total_commits")
            if not isinstance(counted, int):
                state.problems.append(problems.empty(what, reply.call))
                return None
            total = counted
            logger.debug(
                "%s is ahead of %s by %s commits in %s",
                integration,
                release,
                comparison.get("ahead_by"),
                repository.name,
            )
        page = [
            sha for commit in comparison.get("commits") or [] if isinstance(sha := dig(commit, "sha"), str)
        ]
        oids.extend(page)
        if len(oids) >= total:
            return oids
        if not page:
            break
    if len(oids) < total:
        state.problems.append(problems.truncated(what, call, len(oids), total))
    return None


async def _branch_lag(
    cfg: Config, reader: Reader, state: FullState, repository: RepositoryState, branch: str
) -> None:
    """How far a working branch is behind the default branch, in commits the default branch has
    and it lacks (R1). Only the count is wanted, so one commit a page is asked for."""
    call = problems.of_repository(f"{problems.BRANCH_COMPARISON} {branch}", repository.name)
    path = _compare_path(cfg, repository, repository.trunks.integration, branch)
    reply = await reader.rest(call, path, {"per_page": 1})
    behind = dig(reply.data, "behind_by")
    if isinstance(behind, int):
        repository.behind[branch] = Gathered(behind)
    else:
        report(state.problems, cfg, f"the lag of the branch {branch} of {repository.name}", reply)


async def _commits_of(
    cfg: Config, reader: Reader, state: FullState, repository: RepositoryState, oids: Sequence[str]
) -> dict[int, str] | None:
    """The merged pull requests among these commits, by number with each one's head branch, and
    `None` where any of them could not be read (R5).

    A commit that belongs to no pull request is a direct commit and counts as none. The commits are
    read in groups, one group to a query, and one after another: a repository with more commits
    unreleased than one query names is rare, and the count is of all of them or of none.
    """
    found: dict[int, str] = {}
    batches = groups(list(oids), queries.COMMIT_GROUP)
    for index, batch in enumerate(batches, start=1):
        call = problems.group(problems.of_repository(problems.COMMITS, repository.name), index, len(batches))
        what = f"the unreleased work of {repository.name}"
        document = queries.commit_pull_requests([queries.CommitTarget(repository.repository, batch)])
        reply = await reader.graphql(
            call,
            queries.COMMIT_PULL_REQUESTS_OPERATION,
            document,
            {"owner": cfg.github_org, "associated": queries.ASSOCIATED_PULL_REQUESTS},
        )
        if reply.failure is not None:
            report(state.problems, cfg, what, reply)
        if reply.data is None:
            return None
        commits = []
        for place in range(len(batch)):
            commit = dig(reply.data, "r0", f"c{place}")
            if lost(state.problems, what, reply, commit, "r0", f"c{place}"):
                return None
            commits.append(commit)
        found.update(facts.merged_pull_requests(commits))
    return found


async def _files_of(
    cfg: Config, reader: Reader, state: FullState, repository: RepositoryState, merged: Mapping[int, str]
) -> None:
    """Whether any of this repository's unreleased pull requests changes the documentation, the
    files under `docs/` and `site/` (R5).

    The first page of each pull request's files comes in one query for all of them; where a pull
    request changed more than a page of files and none of that page was documentation, the rest of
    its pages are read beside the other pull requests' and not after them. Once one path settles the
    mark, the rest need not be read at all.
    """
    numbers = sorted(merged)
    batches = groups(numbers, queries.PULL_REQUEST_GROUP)
    for index, batch in enumerate(batches, start=1):
        call = problems.group(problems.of_repository(problems.FILES, repository.name), index, len(batches))
        what = f"whether the unreleased work of {repository.name} changes the documentation"
        targets = [queries.PullRequestTarget(repository.repository, number) for number in batch]
        reply = await reader.graphql(
            call,
            queries.FILES_OPERATION,
            queries.files(targets),
            {"owner": cfg.github_org, "files": queries.FILES_PAGE},
        )
        if reply.failure is not None:
            report(state.problems, cfg, what, reply)
        if reply.data is None:
            repository.documentation_failed = True
            return
        unread: list[tuple[int, str]] = []
        for position, number in enumerate(batch):
            alias = f"f{position}"
            connection = dig(reply.data, alias, "pullRequest", "files")
            if lost(state.problems, what, reply, connection, alias):
                repository.documentation_failed = True
                continue
            if _read_files(repository, connection):
                return
            cursor = page_cursor(connection)
            if cursor is not None:
                unread.append((number, cursor))
        if unread:
            async with asyncio.TaskGroup() as group:
                for number, cursor in unread:
                    group.create_task(
                        guard(
                            state.problems, what, _more_files(cfg, reader, state, repository, number, cursor)
                        )
                    )


def _read_files(repository: RepositoryState, connection: Any) -> bool:
    """The paths of one page of a pull request's files; true where the documentation mark is
    settled, after which no further file of that repository need be read."""
    if facts.documentation(dig(entry, "path") for entry in nodes(connection)):
        repository.documentation_found = True
    return repository.documentation_found


async def _more_files(
    cfg: Config, reader: Reader, state: FullState, repository: RepositoryState, number: int, cursor: str
) -> None:
    """The rest of one pull request's files, where it changes more than one page of them and none
    of that page was documentation."""
    call = problems.of_repository(f"the files of pull request {number}", repository.name)
    what = f"whether the unreleased work of {repository.name} changes the documentation"
    next_cursor: str | None = cursor
    for page in range(2, PAGE_LIMIT + 1):
        reply = await reader.graphql(
            problems.page(call, page),
            queries.FILES_PAGE_OPERATION,
            queries.FILES_PAGE_QUERY,
            {
                "owner": cfg.github_org,
                "name": repository.repository,
                "number": number,
                "cursor": next_cursor,
                "files": queries.FILES_PAGE,
            },
        )
        connection = dig(reply.data, "repository", "pullRequest", "files")
        if reply.failure is not None or connection is None:
            repository.documentation_failed = True
            report(state.problems, cfg, what, reply)
            return
        if _read_files(repository, connection):
            return
        next_cursor = page_cursor(connection)
        if next_cursor is None:
            return
    repository.documentation_failed = True
    state.problems.append(problems.from_failure(what, too_long(call), cfg.time_zone))


async def _dev_releases(cfg: Config, reader: Reader, state: FullState) -> None:
    """The dev releases, from GHCR alone (R9): the organisation's container packages, then the
    versions of each, among which a version tagged `dev` carries its dev version in the tag
    beside it (R3). A package belongs to the repository its `repository.full_name` names.

    Every repository whose packages are still being read is pending until the last of them has
    answered, so that a dev release read in part is not published as the whole of it (R11).
    """
    packages, failure = await reader.rest_list(
        problems.PACKAGES, f"/orgs/{cfg.github_org}/packages", {"package_type": "container"}
    )
    if failure is not None:
        state.problems.append(problems.from_failure("the dev releases", failure, cfg.time_zone))
        return
    belongs: list[tuple[str, str]] = []
    for package in packages:
        name, repository = facts.package_name(package), facts.repository_of(package)
        if name is None or repository is None:
            logger.warning("a container package names no repository and belongs to none")
            continue
        belongs.append((name, repository))
        state.dev_pending[repository] = state.dev_pending.get(repository, 0) + 1
    state.dev_versions = {}
    async with asyncio.TaskGroup() as group:
        for name, repository in belongs:
            what = f"the dev release of {repository}"
            group.create_task(
                guard(state.problems, what, _package_versions(cfg, reader, state, name, repository))
            )


async def _package_versions(
    cfg: Config, reader: Reader, state: FullState, package: str, repository: str
) -> None:
    """One package's versions, read page by page only as far as the dev release needs.

    GHCR lists a package's versions newest first, so the first page holding a version tagged `dev`
    holds the newest dev release and the rest of the list says nothing the page shows.
    """
    path = f"/orgs/{cfg.github_org}/packages/container/{quote(package, safe='')}/versions"
    call = f"the versions of the package {package}"
    what = f"the dev release of {repository}"
    found: list[str] = []
    failed = False
    for number in range(1, PAGE_LIMIT + 1):
        reply = await reader.rest(problems.page(call, number), path, {"per_page": REST_PAGE, "page": number})
        listed = reply.data if isinstance(reply.data, list) else None
        if reply.failure is not None or listed is None:
            report(state.problems, cfg, what, reply)
            failed = True
            break
        for entry in listed:
            found.extend(facts.dev_versions(facts.container_tags(entry)))
        if found or len(listed) < REST_PAGE:
            break
        if number == PAGE_LIMIT:
            state.problems.append(problems.from_failure(what, too_long(call), cfg.time_zone))
            failed = True
    if failed:
        state.dev_failures.add(repository)
    elif state.dev_versions is not None:
        state.dev_versions.setdefault(repository, []).extend(found)
    state.dev_pending[repository] = max(0, state.dev_pending.get(repository, 0) - 1)
