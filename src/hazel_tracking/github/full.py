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
)
from hazel_tracking.github.collecting import groups, guard, report
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

# How many commits of a comparison GitHub will list, however many pages are asked for; a longer
# comparison is reported rather than counted (docs.github.com, "Compare two commits").
COMPARISON_COMMIT_LIMIT = 250


@dataclass
class RepositoryState:
    """One repository as the gather fills it in, before it is frozen into the contract.

    A list that is `None` is one that was not gathered, which is not the same as one gathered
    and found empty: a repository with no tag has `tags == []` and its newest tag reads "none"
    (R7). `compared` holds the oids of the commits the integration trunk has and the release trunk
    lacks, which REST's comparison gives, and `merged` the merged pull requests among them by
    number with each one's head branch, which GraphQL gives for those oids; `compared_failed` marks
    a comparison that could not be read whole, whose count is then not gathered.
    """

    name: str
    repository: str
    trunks: Trunks
    last_push: Fact[datetime | None] = NOT_GATHERED
    open_issues: Fact[int] = NOT_GATHERED
    newest_release: Fact[str | None] = NOT_GATHERED
    tags: list[str] | None = None
    branches: list[str] | None = None
    checks: dict[str, Fact[CheckState]] = field(default_factory=dict)
    integration_checks: CheckState | None = None
    integration_read: bool = False
    behind: dict[str, Fact[int]] = field(default_factory=dict)
    pulls: list[PullRequest] | None = None
    heads: dict[str, PullRequestRef] = field(default_factory=dict)
    uncomputed: set[int] = field(default_factory=set)
    compared: list[str] | None = None
    compared_failed: bool = False
    merged: dict[int, str] | None = None
    back_merge_pending: Fact[bool] = NOT_GATHERED
    documentation_found: bool = False
    documentation_failed: bool = False
    cursors: dict[str, str | None] = field(default_factory=dict)

    def working_branch_names(self) -> tuple[str, ...]:
        return facts.working_branches(self.branches or (), self.trunks)

    def to_model(self, dev_release: Fact[DevRelease | None]) -> Repository:
        """This repository in the words of the contract, every fact it lacks not gathered."""
        counted = self.merged is not None and not self.compared_failed
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
        if self.merged is None or self.compared_failed or self.documentation_failed:
            return NOT_GATHERED
        return Gathered(self.documentation_found)

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

    `archived` counts the archived repositories left out, and stays `None` until the list of
    repositories arrives (R11). `dev_versions` is `None` until the packages answer, and holds the
    dev versions published for each repository that has any; `dev_failures` names the
    repositories whose own package could not be read, whose dev release alone is then ungathered.
    """

    repositories: list[RepositoryState] = field(default_factory=list)
    archived: int | None = None
    dev_versions: dict[str, list[str]] | None = None
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
        if connection is None:
            return
        if not isinstance(dig(connection, "nodes"), list):
            # The one loss that is total: without this list there is no repository to show at all,
            # so an answer whose shape cannot be read is reported rather than read as empty.
            report(state.problems, cfg, "every repository's facts", Reply(call=call))
            return
        if state.archived is None:
            state.archived = 0
        for node in nodes(connection):
            _read_repository(state, node)
        cursor = page_cursor(connection)
        if cursor is None:
            return


def _read_repository(state: FullState, node: Any) -> None:
    """One repository of the answer, archived ones counted and left out."""
    name = dig(node, "nameWithOwner")
    if not isinstance(name, str):
        return
    if dig(node, "isArchived"):
        state.archived = (state.archived or 0) + 1
        return
    shape = facts.trunks(facts.default_branch(node))
    repository = RepositoryState(name=name, repository=name.rpartition("/")[2], trunks=shape)
    repository.last_push = Gathered(aware(dig(node, "pushedAt")))
    issues = dig(node, "issues", "totalCount")
    repository.open_issues = Gathered(issues) if isinstance(issues, int) else NOT_GATHERED
    release = dig(node, "latestRelease", "tagName")
    repository.newest_release = Gathered(release if isinstance(release, str) else None)
    for kind, key in ((_TAGS, "tags"), (_BRANCHES, "branches")):
        connection = dig(node, key)
        names = [found for found in (dig(ref, "name") for ref in nodes(connection)) if isinstance(found, str)]
        setattr(repository, kind, names)
        repository.cursors[kind] = page_cursor(connection)
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
    repository.pulls = []
    _read_pull_requests(repository, nodes(pulls))
    repository.cursors[_PULLS] = page_cursor(pulls)
    state.repositories.append(repository)


def _read_pull_requests(repository: RepositoryState, pull_nodes: list[Any]) -> None:
    """The open pull requests of one repository, with their statuses (R4) and the branch each
    one is open from, which is how a working branch finds its pull request."""
    listed = repository.pulls if repository.pulls is not None else []
    for pull in pull_nodes:
        number, url = dig(pull, "number"), dig(pull, "url")
        if not isinstance(number, int):
            continue
        address = url if isinstance(url, str) else ""
        status = facts.pull_request_status(pull)
        if status is None:
            repository.uncomputed.add(number)
        listed.append(
            PullRequest(
                number=number, url=address, status=NOT_GATHERED if status is None else Gathered(status)
            )
        )
        head = dig(pull, "headRefName")
        if isinstance(head, str):
            repository.heads[head] = PullRequestRef(number=number, url=address)
    repository.pulls = listed


async def _continuations(cfg: Config, reader: Reader, state: FullState) -> None:
    """The rest of every list one page did not hold. They are read before the comparisons, which
    need the whole list of branches to know what to compare."""
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
    for number in range(2, PAGE_LIMIT + 1):
        reply = await reader.graphql(
            problems.page(call, number),
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
        if connection is None:
            setattr(repository, kind, None)
            report(state.problems, cfg, what, reply)
            return
        found: list[str] = getattr(repository, kind) or []
        found.extend(name for ref in nodes(connection) if isinstance(name := dig(ref, "name"), str))
        setattr(repository, kind, found)
        cursor = page_cursor(connection)
        if cursor is None:
            return


async def _more_pulls(cfg: Config, reader: Reader, state: FullState, repository: RepositoryState) -> None:
    """The rest of a repository's open pull requests. Read to its end or not gathered: which
    branch has a pull request open from it is a fact of the whole list."""
    call = problems.of_repository("the open pull requests", repository.name)
    what = f"the open pull requests of {repository.name}"
    cursor = repository.cursors.get(_PULLS)
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
        if connection is None:
            repository.pulls = None
            repository.heads.clear()
            repository.uncomputed.clear()
            report(state.problems, cfg, what, reply)
            return
        _read_pull_requests(repository, nodes(connection))
        cursor = page_cursor(connection)
        if cursor is None:
            return


async def _second_read(cfg: Config, reader: Reader, state: FullState) -> None:
    """R4's second read: a status GitHub had not computed is read once more, and if it is still
    not computed it is not gathered."""
    waiting = [
        (repository, number)
        for repository in state.repositories
        for number in sorted(repository.uncomputed)
        if repository.pulls is not None
    ]
    if not waiting:
        return
    batches = groups(waiting, queries.PULL_REQUEST_GROUP)
    async with asyncio.TaskGroup() as group:
        for index, batch in enumerate(batches, start=1):
            what = "the status of " + problems.listed([f"{r.name}#{n}" for r, n in batch])
            group.create_task(
                guard(state.problems, what, _statuses(cfg, reader, state, batch, index, len(batches)))
            )


async def _statuses(
    cfg: Config,
    reader: Reader,
    state: FullState,
    batch: Sequence[tuple[RepositoryState, int]],
    index: int,
    batches: int,
) -> None:
    call = problems.group(problems.STATUSES, index, batches)
    document = queries.statuses([queries.PullRequestTarget(r.repository, number) for r, number in batch])
    reply = await reader.graphql(call, queries.STATUSES_OPERATION, document, {"owner": cfg.github_org})
    if reply.data is None:
        what = "the status of " + problems.listed([f"{r.name}#{n}" for r, n in batch])
        report(state.problems, cfg, what, reply)
        return
    for position, (repository, number) in enumerate(batch):
        pull = dig(reply.data, f"s{position}", "pullRequest")
        status = facts.pull_request_status(pull) if pull is not None else None
        if status is not None:
            _set_status(repository, number, status)
        elif pull is None:
            report(state.problems, cfg, f"the status of {repository.name}#{number}", reply)


def _set_status(repository: RepositoryState, number: int, status: PullRequestStatus) -> None:
    if repository.pulls is None:
        return
    repository.pulls = [
        replace(pull, status=Gathered(status)) if pull.number == number else pull for pull in repository.pulls
    ]


async def _comparisons(cfg: Config, reader: Reader, state: FullState) -> None:
    """Each repository's trunk comparison, for the unreleased work and a pending back-merge, and
    each working branch's, for its lag; then what the compared commits belong to, and the files of
    those pull requests, which only the comparisons name."""
    async with asyncio.TaskGroup() as group:
        for repository in state.repositories:
            if not repository.trunks.integration:
                continue
            release = repository.trunks.release
            if release is not None:
                what = f"the unreleased work of {repository.name}"
                group.create_task(
                    guard(state.problems, what, _trunk_comparison(cfg, reader, state, repository, release))
                )
            for branch in repository.working_branch_names():
                what = f"the lag of the branch {branch} of {repository.name}"
                group.create_task(
                    guard(state.problems, what, _branch_lag(cfg, reader, state, repository, branch))
                )
    await guard(state.problems, "the unreleased pull requests", _commit_pull_requests(cfg, reader, state))
    await guard(state.problems, "the documentation in the unreleased work", _files(cfg, reader, state))


def _compare_path(cfg: Config, repository: RepositoryState, base: str, head: str) -> str:
    """REST's comparison of two refs of one repository, `base...head`. A branch name's slashes
    belong to the name and are left as they are, which is the form GitHub's comparison takes."""
    refs = quote(f"{base}...{head}", safe="/.")
    return f"/repos/{cfg.github_org}/{repository.repository}/compare/{refs}"


async def _trunk_comparison(
    cfg: Config, reader: Reader, state: FullState, repository: RepositoryState, release: str
) -> None:
    """The commits the integration trunk has and the release trunk lacks, and whether the release
    trunk holds any the integration trunk lacks (R5, R6).

    The comparison is read page by page for its commits. GitHub answers at most 250 of them
    whatever is asked for, so where it says the comparison is longer the count cannot be made and
    is left not gathered beside a problem saying how far the list went.
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
            repository.compared_failed = True
            return
        if number == 1:
            behind = comparison.get("behind_by")
            repository.back_merge_pending = Gathered(behind > 0) if isinstance(behind, int) else NOT_GATHERED
            counted = comparison.get("total_commits")
            total = counted if isinstance(counted, int) else 0
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
        if len(oids) >= total or not page:
            break
    if len(oids) < total:
        state.problems.append(problems.truncated(what, call, len(oids), total, COMPARISON_COMMIT_LIMIT))
        repository.compared_failed = True
        return
    repository.compared = oids
    if not oids:
        repository.merged = {}


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


async def _commit_pull_requests(cfg: Config, reader: Reader, state: FullState) -> None:
    """What the compared commits belong to: the merged pull requests among them, by the oids the
    comparisons gave (R5). A commit that belongs to no pull request is a direct commit and counts
    as none."""
    waiting = [
        (repository, oid)
        for repository in state.repositories
        if repository.compared
        for oid in repository.compared
    ]
    if not waiting:
        return
    batches = groups(waiting, queries.COMMIT_GROUP)
    async with asyncio.TaskGroup() as group:
        for index, batch in enumerate(batches, start=1):
            what = _unreleased_what([repository for repository, _ in batch])
            group.create_task(
                guard(state.problems, what, _commit_group(cfg, reader, state, batch, index, len(batches)))
            )


def _unreleased_what(repositories: Sequence[RepositoryState]) -> str:
    names = problems.listed(sorted({repository.name for repository in repositories}))
    return f"the unreleased work of {names}"


def _by_repository(
    batch: Sequence[tuple[RepositoryState, str]],
) -> list[tuple[RepositoryState, list[str]]]:
    """The batch's commits grouped by their repository, in the batch's order, which is the order
    the aliases of the query take."""
    grouped: list[tuple[RepositoryState, list[str]]] = []
    for repository, oid in batch:
        if grouped and grouped[-1][0] is repository:
            grouped[-1][1].append(oid)
        else:
            grouped.append((repository, [oid]))
    return grouped


async def _commit_group(
    cfg: Config,
    reader: Reader,
    state: FullState,
    batch: Sequence[tuple[RepositoryState, str]],
    index: int,
    batches: int,
) -> None:
    call = problems.group(problems.COMMITS, index, batches)
    grouped = _by_repository(batch)
    document = queries.commit_pull_requests(
        [queries.CommitTarget(repository=repository.repository, oids=oids) for repository, oids in grouped]
    )
    reply = await reader.graphql(
        call,
        queries.COMMIT_PULL_REQUESTS_OPERATION,
        document,
        {"owner": cfg.github_org, "associated": queries.ASSOCIATED_PULL_REQUESTS},
    )
    if reply.data is None:
        for repository, _ in batch:
            repository.compared_failed = True
        report(state.problems, cfg, _unreleased_what([repository for repository, _ in batch]), reply)
        return
    for position, (repository, oids) in enumerate(grouped):
        answered = dig(reply.data, f"r{position}")
        if answered is None:
            repository.compared_failed = True
            report(state.problems, cfg, _unreleased_what([repository]), reply)
            continue
        commits = [dig(answered, f"c{place}") for place in range(len(oids))]
        if any(commit is None for commit in commits):
            repository.compared_failed = True
            report(state.problems, cfg, _unreleased_what([repository]), reply)
            continue
        found = repository.merged if repository.merged is not None else {}
        found.update(facts.merged_pull_requests(commits))
        repository.merged = found


async def _files(cfg: Config, reader: Reader, state: FullState) -> None:
    """Whether any unreleased pull request changes the documentation, the files under `docs/` and
    `site/` (R5). A repository with no unreleased pull request carries no mark, which is a fact
    gathered and false."""
    waiting = [
        (repository, number)
        for repository in state.repositories
        if repository.merged
        for number in sorted(repository.merged)
    ]
    if not waiting:
        return
    batches = groups(waiting, queries.PULL_REQUEST_GROUP)
    async with asyncio.TaskGroup() as group:
        for index, batch in enumerate(batches, start=1):
            what = _files_what([repository for repository, _ in batch])
            group.create_task(
                guard(state.problems, what, _files_group(cfg, reader, state, batch, index, len(batches)))
            )


def _files_what(repositories: Sequence[RepositoryState]) -> str:
    names = problems.listed(sorted({repository.name for repository in repositories}))
    return f"whether the unreleased work of {names} changes the documentation"


async def _files_group(
    cfg: Config,
    reader: Reader,
    state: FullState,
    batch: Sequence[tuple[RepositoryState, int]],
    index: int,
    batches: int,
) -> None:
    call = problems.group(problems.FILES, index, batches)
    document = queries.files([queries.PullRequestTarget(r.repository, number) for r, number in batch])
    reply = await reader.graphql(
        call, queries.FILES_OPERATION, document, {"owner": cfg.github_org, "files": queries.FILES_PAGE}
    )
    if reply.data is None:
        for repository, _ in batch:
            repository.documentation_failed = True
        report(state.problems, cfg, _files_what([repository for repository, _ in batch]), reply)
        return
    for position, (repository, number) in enumerate(batch):
        connection = dig(reply.data, f"f{position}", "pullRequest", "files")
        if connection is None:
            repository.documentation_failed = True
            report(state.problems, cfg, _files_what([repository]), reply)
            continue
        if _read_files(repository, connection):
            continue
        cursor = page_cursor(connection)
        if cursor:
            await _more_files(cfg, reader, state, repository, number, cursor)


def _read_files(repository: RepositoryState, connection: Any) -> bool:
    """The paths of one page of a pull request's files; true where the documentation mark is
    settled, after which the rest of that pull request's files need not be read."""
    if facts.documentation(dig(entry, "path") for entry in nodes(connection)):
        repository.documentation_found = True
    return repository.documentation_found


async def _more_files(
    cfg: Config, reader: Reader, state: FullState, repository: RepositoryState, number: int, cursor: str
) -> None:
    """The rest of one pull request's files, where it changes more than one page of them and none
    of that page was documentation."""
    call = problems.of_repository(f"the files of pull request {number}", repository.name)
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
        if connection is None:
            repository.documentation_failed = True
            report(state.problems, cfg, _files_what([repository]), reply)
            return
        if _read_files(repository, connection):
            return
        next_cursor = page_cursor(connection)
        if next_cursor is None:
            return


async def _dev_releases(cfg: Config, reader: Reader, state: FullState) -> None:
    """The dev releases, from GHCR alone (R9): the organisation's container packages, then the
    versions of each, among which a version tagged `dev` carries its dev version in the tag
    beside it (R3). A package belongs to the repository its `repository.full_name` names."""
    packages, failure = await reader.rest_list(
        problems.PACKAGES, f"/orgs/{cfg.github_org}/packages", {"package_type": "container"}
    )
    if failure is not None:
        state.problems.append(problems.from_failure("the dev releases", failure, cfg.time_zone))
        return
    state.dev_versions = {}
    async with asyncio.TaskGroup() as group:
        for package in packages:
            name, repository = facts.package_name(package), facts.repository_of(package)
            if name is None or repository is None:
                logger.warning("a container package names no repository and belongs to none")
                continue
            what = f"the dev release of {repository}"
            group.create_task(
                guard(state.problems, what, _package_versions(cfg, reader, state, name, repository))
            )


async def _package_versions(
    cfg: Config, reader: Reader, state: FullState, package: str, repository: str
) -> None:
    path = f"/orgs/{cfg.github_org}/packages/container/{quote(package, safe='')}/versions"
    call = f"the versions of the package {package}"
    versions, failure = await reader.rest_list(call, path)
    if failure is not None:
        state.dev_failures.add(repository)
        state.problems.append(
            problems.from_failure(f"the dev release of {repository}", failure, cfg.time_zone)
        )
        return
    published = [version for entry in versions for version in facts.dev_versions(facts.container_tags(entry))]
    if state.dev_versions is None:
        state.dev_versions = {}
    state.dev_versions.setdefault(repository, []).extend(published)
