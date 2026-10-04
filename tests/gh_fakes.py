# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""A fake GitHub: a synthetic organisation built in code, answered through an `httpx` transport.

The gathering reads through the client it is given, so a test gives it a client whose
transport is `FakeGitHub.transport()` and nothing leaves the machine. The fake
answers the calls the gathering makes, in the shapes GitHub answers them in: the
repositories query and its continuations, the comparisons, the files of a pull
request, a second read of a status, the search for the open pull requests, and over
REST the organisation's container packages and their versions.

Three things make the failures testable. `failures` forces an answer for a named
call (a status, a body, headers, and how many calls it applies to), `delays` holds
an answer back, so that a gather can be cut short by its wait, and `page_cap` caps
every page the fake gives, so that the lists are read to their end over several
calls without the production sizes having to change. `calls` records what was asked,
in order.

The aliases of the three aliased queries are read back from the document, which
`queries.py` writes one target to a line in a fixed shape.
"""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import httpx

# The calls, as `failures` and `delays` name them: the GraphQL operations by name, and the two
# REST reads by these keys.
PACKAGES = "packages"
VERSIONS = "versions"
COMPARE = "compare"

_REPOSITORY_LINE = re.compile(r'^\s*(r\d+): repository\(owner: \$owner, name: "([^"]+)"\) \{$')
_COMMIT_LINE = re.compile(r'^\s*(c\d+): object\(oid: "([^"]+)"\)')
_PULL_LINE = re.compile(
    r'^\s*([fs]\d+): repository\(owner: \$owner, name: "([^"]+)"\) \{ pullRequest\(number: (\d+)\)'
)


@dataclass(frozen=True)
class FakeAssociated:
    """A pull request a compared commit belongs to."""

    number: int
    head: str
    merged: bool = True


@dataclass(frozen=True)
class FakeCommit:
    """One commit of a trunk's history or of a comparison. `rollup` is GitHub's check rollup
    state, and `None` a commit with no checks, as a `[skip ci]` commit has none."""

    oid: str
    rollup: str | None = None
    pulls: Sequence[FakeAssociated] = ()


@dataclass(frozen=True)
class FakePullRequest:
    """An open pull request. `uncomputed_reads` is how many reads answer `UNKNOWN` before GitHub
    has computed the status, which is what R4's second read is tested against; `head_repository` is
    the repository the head branch is in, another name than the base repository's where the pull
    request comes from a fork."""

    number: int
    head: str
    title: str = "a pull request"
    base: str | None = None
    head_repository: str | None = None
    draft: bool = False
    mergeable: str = "MERGEABLE"
    state: str = "CLEAN"
    rollup: str | None = "SUCCESS"
    uncomputed_reads: int = 0


@dataclass(frozen=True)
class FakeRepository:
    """One repository of the synthetic organisation.

    `ahead` are the commits the integration trunk has and the release trunk lacks, and `behind`
    how many the release trunk has that the integration trunk lacks (a pending back-merge).
    `ahead_missing` are oids the comparison lists and the repository will not resolve, as happens
    where a branch is rewritten between the two calls. `ahead_total` is the number GitHub reports
    where it will not list them all, the 250 of its comparison: where it is set, the comparison
    says it is longer than the commits it gives; `ahead_total_absent` leaves that number out of the
    answer altogether.
    `files` are the paths each merged pull request changed. `missing` names a ref GitHub answers
    with a null, as it does for a branch deleted between two calls.
    """

    name: str
    default_branch: str | None = "develop"
    archived: bool = False
    pushed_at: str | None = "2026-10-03T11:30:00Z"
    issues: int = 0
    tags: Sequence[str] = ()
    latest_release: str | None = None
    branches: Sequence[str] = ()
    history: Mapping[str, Sequence[FakeCommit]] = field(default_factory=dict)
    pulls: Sequence[FakePullRequest] = ()
    ahead: Sequence[FakeCommit] = ()
    ahead_missing: Sequence[str] = ()
    ahead_total: int | None = None
    ahead_total_absent: bool = False
    behind: int = 0
    branch_behind: Mapping[str, int] = field(default_factory=dict)
    files: Mapping[int, Sequence[str]] = field(default_factory=dict)
    missing: frozenset[str] = frozenset()

    def trunks(self) -> tuple[str, ...]:
        release = {"develop": "main", "staging": "live"}.get(self.default_branch or "")
        return tuple(name for name in (release, self.default_branch) if name)

    def ref_names(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys((*self.trunks(), *self.branches)))


@dataclass(frozen=True)
class FakePackage:
    """A container package of the organisation. Each version carries its tags, as GHCR records
    them; `repository` is `None` for a package that names no repository."""

    name: str
    repository: str | None
    versions: Sequence[Sequence[str]] = ()


@dataclass(frozen=True)
class FakeOrganisation:
    login: str
    repositories: Sequence[FakeRepository] = ()
    packages: Sequence[FakePackage] = ()


@dataclass
class FakeAnswer:
    """An answer forced for a call: a status, a JSON body or a body that is not JSON, headers,
    and how many calls it applies to (`None` for every one of them)."""

    status: int = 500
    payload: Any = None
    text: str | None = None
    headers: Mapping[str, str] = field(default_factory=dict)
    times: int | None = None
    after: int = 0  # how many calls of that name answer normally before this one applies
    used: int = 0
    seen: int = 0

    def spent(self) -> bool:
        return self.times is not None and self.used >= self.times


def server_error() -> FakeAnswer:
    return FakeAnswer(status=500, payload={"message": "Internal Server Error"})


def unauthorised() -> FakeAnswer:
    return FakeAnswer(status=401, payload={"message": "Bad credentials"})


def forbidden() -> FakeAnswer:
    return FakeAnswer(status=403, payload={"message": "Resource not accessible by personal access token"})


def not_found() -> FakeAnswer:
    return FakeAnswer(status=404, payload={"message": "Not Found"})


def malformed() -> FakeAnswer:
    return FakeAnswer(status=200, text="{this is not json")


def rate_limited_graphql(reset: int = 1_790_000_000) -> FakeAnswer:
    """GraphQL's own refusal for the rate limit, which comes with status 200."""
    return FakeAnswer(
        status=200,
        payload={"data": None, "errors": [{"type": "RATE_LIMITED", "message": "API rate limit exceeded"}]},
        headers={"x-ratelimit-remaining": "0", "x-ratelimit-reset": str(reset)},
    )


def rate_limited_rest(status: int = 403, reset: int = 1_790_000_000) -> FakeAnswer:
    return FakeAnswer(
        status=status,
        payload={"message": "You have exceeded a secondary rate limit"},
        headers={"x-ratelimit-remaining": "0", "x-ratelimit-reset": str(reset)},
    )


def graphql_error(message: str = "Something went wrong whilst executing your query") -> FakeAnswer:
    """An answer carrying an error and no data."""
    return FakeAnswer(status=200, payload={"data": None, "errors": [{"message": message}]})


@dataclass
class FakeGitHub:
    """The fake, over one synthetic organisation."""

    organisation: FakeOrganisation
    failures: dict[str, FakeAnswer] = field(default_factory=dict)
    errors: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    refuses: set[str] = field(default_factory=set)
    delays: dict[str, float] = field(default_factory=dict)
    page_cap: int | None = None
    expiry: str | None = "2027-09-18 00:00:00 UTC"
    remaining: int = 4_990
    resets_at: str = "2026-10-03T15:00:00Z"
    calls: list[str] = field(default_factory=list)
    credentials: set[str] = field(default_factory=set)
    _reads: dict[tuple[str, int], int] = field(default_factory=dict, repr=False)

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._answer)

    def repository(self, name: str) -> FakeRepository:
        for repository in self.organisation.repositories:
            if repository.name == name:
                return repository
        raise KeyError(name)

    def asked(self, call: str) -> int:
        return self.calls.count(call)

    async def _answer(self, request: httpx.Request) -> httpx.Response:
        self.credentials.add(request.headers.get("authorization", ""))
        if request.url.path.endswith("/graphql"):
            return await self._graphql(request)
        return await self._rest(request)

    async def _graphql(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        operation = body.get("operationName") or ""
        document, variables = body.get("query") or "", body.get("variables") or {}
        self.calls.append(operation)
        await self._delay(operation)
        self._refuse(operation)
        forced = self._forced(operation)
        if forced is not None:
            return self._response(forced)
        data = self._data(operation, document, variables)
        data["rateLimit"] = {"cost": 1, "remaining": self.remaining, "resetAt": self.resets_at}
        payload: dict[str, Any] = {"data": data}
        errors = self.errors.get(operation)
        if errors:
            payload["errors"] = errors
        return self._response(FakeAnswer(status=200, payload=payload))

    def _data(self, operation: str, document: str, variables: Mapping[str, Any]) -> dict[str, Any]:
        if operation == "Repositories":
            return self._repositories(variables)
        if operation == "RepositoryRefs":
            return self._refs(variables)
        if operation == "RepositoryPullRequests":
            return self._repository_pulls(variables)
        if operation == "CommitPullRequests":
            return self._commit_pull_requests(document, variables)
        if operation == "PullRequestFiles":
            return self._files(document, variables)
        if operation == "PullRequestFilesPage":
            return self._files_page(variables)
        if operation == "PullRequestStatuses":
            return self._statuses(document)
        if operation == "OpenPullRequests":
            return self._search(variables)
        raise AssertionError(f"the fake was asked an operation it does not know: {operation!r}")

    # The repositories query and its continuations.

    def _repositories(self, variables: Mapping[str, Any]) -> dict[str, Any]:
        listed = list(self.organisation.repositories)
        page, info = self._page(listed, variables.get("cursor"), variables.get("repositories"))
        nodes = [self._repository_node(repository, variables) for repository in page]
        return {"organization": {"repositories": {"pageInfo": info, "nodes": nodes}}}

    def _repository_node(self, repository: FakeRepository, variables: Mapping[str, Any]) -> dict[str, Any]:
        trunks = repository.trunks()
        release = trunks[0] if len(trunks) == 2 else None
        tags, tags_info = self._page(list(repository.tags), None, variables.get("refs"))
        branches, branches_info = self._page(list(repository.ref_names()), None, variables.get("refs"))
        pulls, pulls_info = self._page(list(repository.pulls), None, variables.get("pulls"))
        return {
            "nameWithOwner": self._full_name(repository),
            "isArchived": repository.archived,
            "pushedAt": repository.pushed_at,
            "issues": {"totalCount": repository.issues},
            "latestRelease": {"tagName": repository.latest_release} if repository.latest_release else None,
            "defaultBranchRef": self._ref_node(repository, repository.default_branch, variables),
            "mainTrunk": self._ref_node(repository, "main" if release == "main" else None, variables),
            "liveTrunk": self._ref_node(repository, "live" if release == "live" else None, variables),
            "tags": {"pageInfo": tags_info, "nodes": [{"name": name} for name in tags]},
            "branches": {"pageInfo": branches_info, "nodes": [{"name": name} for name in branches]},
            "pullRequests": {
                "pageInfo": pulls_info,
                "nodes": [self._pull_node(repository, pull) for pull in pulls],
            },
        }

    def _ref_node(
        self, repository: FakeRepository, name: str | None, variables: Mapping[str, Any]
    ) -> dict[str, Any] | None:
        if name is None or name in repository.missing or name not in repository.ref_names():
            return None
        depth = int(variables.get("history") or 10)
        commits = list(repository.history.get(name, ()))[:depth]
        return {
            "name": name,
            "target": {"history": {"nodes": [self._commit_node(commit) for commit in commits]}},
        }

    def _commit_node(self, commit: FakeCommit, associated: int | None = None) -> dict[str, Any]:
        node: dict[str, Any] = {
            "oid": commit.oid,
            "statusCheckRollup": {"state": commit.rollup} if commit.rollup else None,
        }
        if associated is not None:
            listed = list(commit.pulls)[:associated]
            node["associatedPullRequests"] = {
                "nodes": [
                    {"number": pull.number, "headRefName": pull.head, "merged": pull.merged}
                    for pull in listed
                ]
            }
        return node

    def _pull_node(self, repository: FakeRepository, pull: FakePullRequest) -> dict[str, Any]:
        key = (repository.name, pull.number)
        self._reads[key] = self._reads.get(key, 0) + 1
        uncomputed = self._reads[key] <= pull.uncomputed_reads
        return {
            "number": pull.number,
            "url": f"{self._address(repository)}/pull/{pull.number}",
            "title": pull.title,
            "isDraft": pull.draft,
            "mergeable": "UNKNOWN" if uncomputed else pull.mergeable,
            "mergeStateStatus": "UNKNOWN" if uncomputed else pull.state,
            "baseRefName": pull.base or repository.default_branch,
            "headRefName": pull.head,
            "headRepository": {"nameWithOwner": pull.head_repository or self._full_name(repository)},
            "commits": {
                "nodes": [
                    {"commit": {"statusCheckRollup": {"state": pull.rollup} if pull.rollup else None}},
                ]
            },
            "repository": {
                "nameWithOwner": self._full_name(repository),
                "defaultBranchRef": (
                    {"name": repository.default_branch} if repository.default_branch else None
                ),
            },
        }

    def _refs(self, variables: Mapping[str, Any]) -> dict[str, Any]:
        repository = self.repository(str(variables["name"]))
        tags = str(variables["prefix"]).endswith("tags/")
        listed = list(repository.tags if tags else repository.ref_names())
        page, info = self._page(listed, variables.get("cursor"), variables.get("refs"))
        return {"repository": {"refs": {"pageInfo": info, "nodes": [{"name": name} for name in page]}}}

    def _repository_pulls(self, variables: Mapping[str, Any]) -> dict[str, Any]:
        repository = self.repository(str(variables["name"]))
        page, info = self._page(list(repository.pulls), variables.get("cursor"), variables.get("pulls"))
        return {
            "repository": {
                "pullRequests": {
                    "pageInfo": info,
                    "nodes": [self._pull_node(repository, pull) for pull in page],
                }
            }
        }

    # What the compared commits belong to, by the oids REST's comparison gave.

    def _commit_pull_requests(self, document: str, variables: Mapping[str, Any]) -> dict[str, Any]:
        data: dict[str, Any] = {}
        alias: str | None = None
        repository: FakeRepository | None = None
        for line in document.splitlines():
            found = _REPOSITORY_LINE.match(line)
            if found:
                alias, repository = found.group(1), self.repository(found.group(2))
                data[alias] = {}
                continue
            commit = _COMMIT_LINE.match(line)
            if commit and alias is not None and repository is not None:
                found_commit = self._commit(repository, commit.group(2))
                associated = int(variables.get("associated") or 10)
                data[alias][commit.group(1)] = (
                    None if found_commit is None else self._commit_node(found_commit, associated)
                )
        return data

    def _commit(self, repository: FakeRepository, oid: str) -> FakeCommit | None:
        """The commit of that oid, among the compared commits and the trunks' histories; `None`
        where the repository holds no such commit, which GitHub answers with a null."""
        for commit in (*repository.ahead, *(c for commits in repository.history.values() for c in commits)):
            if commit.oid == oid:
                return commit
        return None

    # The files of a pull request, and a second read of a status.

    def _files(self, document: str, variables: Mapping[str, Any]) -> dict[str, Any]:
        data: dict[str, Any] = {}
        for alias, repository, number in self._pull_targets(document):
            paths, info = self._page(list(repository.files.get(number, ())), None, variables.get("files"))
            data[alias] = {
                "pullRequest": {"files": {"pageInfo": info, "nodes": [{"path": path} for path in paths]}}
            }
        return data

    def _files_page(self, variables: Mapping[str, Any]) -> dict[str, Any]:
        repository = self.repository(str(variables["name"]))
        number = int(variables["number"])
        paths, info = self._page(
            list(repository.files.get(number, ())), variables.get("cursor"), variables.get("files")
        )
        return {
            "repository": {
                "pullRequest": {"files": {"pageInfo": info, "nodes": [{"path": path} for path in paths]}}
            }
        }

    def _statuses(self, document: str) -> dict[str, Any]:
        data: dict[str, Any] = {}
        for alias, repository, number in self._pull_targets(document):
            pull = next((one for one in repository.pulls if one.number == number), None)
            data[alias] = {"pullRequest": None if pull is None else self._pull_node(repository, pull)}
        return data

    def _pull_targets(self, document: str) -> list[tuple[str, FakeRepository, int]]:
        found = []
        for line in document.splitlines():
            match = _PULL_LINE.match(line)
            if match:
                found.append((match.group(1), self.repository(match.group(2)), int(match.group(3))))
        return found

    # The search for the open pull requests.

    def _search(self, variables: Mapping[str, Any]) -> dict[str, Any]:
        open_pulls = [
            (repository, pull)
            for repository in self.organisation.repositories
            if not repository.archived
            for pull in repository.pulls
        ]
        page, info = self._page(open_pulls, variables.get("cursor"), variables.get("pulls"))
        return {
            "search": {
                "pageInfo": info,
                "nodes": [self._pull_node(repository, pull) for repository, pull in page],
            }
        }

    # REST: the comparisons, the organisation's container packages and their versions.

    async def _rest(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if "/compare/" in path:
            owner, name = path.split("/repos/", 1)[1].split("/compare/", 1)[0].split("/")
            repository = self.repository(name)
            keys = (f"{COMPARE}:{name}", COMPARE)
            self.calls.append(keys[0])
            await self._delay(*keys)
            self._refuse(*keys)
            forced = self._forced(*keys)
            if forced is not None:
                return self._response(forced)
            refs = path.split("/compare/", 1)[1]
            assert owner == self.organisation.login
            return self._response(self._comparison(repository, refs, request))
        if path.endswith("/versions"):
            package = path.rsplit("/", 2)[-2]
            keys = (f"{VERSIONS}:{package}", VERSIONS)
            self.calls.append(keys[0])
            await self._delay(*keys)
            self._refuse(*keys)
            forced = self._forced(*keys)
            if forced is not None:
                return self._response(forced)
            return self._response(FakeAnswer(status=200, payload=self._versions(package, request)))
        if path.endswith("/packages"):
            self.calls.append(PACKAGES)
            await self._delay(PACKAGES)
            self._refuse(PACKAGES)
            forced = self._forced(PACKAGES)
            if forced is not None:
                return self._response(forced)
            return self._response(FakeAnswer(status=200, payload=self._packages(request)))
        raise AssertionError(f"the fake was asked a path it does not know: {path}")

    def _comparison(self, repository: FakeRepository, refs: str, request: httpx.Request) -> FakeAnswer:
        """REST's comparison of `base...head`, as GitHub answers it: the counts both ways and the
        commits of the range, a page at a time. `total_commits` is `ahead_total` where a test gives
        one, which is how GitHub reports a comparison longer than the 250 commits it will list."""
        base, _, head = refs.partition("...")
        if base in repository.missing or head in repository.missing:
            return not_found()
        if head not in repository.trunks():
            if head not in repository.ref_names():
                return not_found()
            return FakeAnswer(
                status=200,
                payload={
                    "status": "behind",
                    "ahead_by": 0,
                    "behind_by": repository.branch_behind.get(head, 0),
                    "total_commits": 0,
                    "commits": [],
                },
            )
        listed = [{"sha": commit.oid} for commit in repository.ahead]
        listed += [{"sha": oid} for oid in repository.ahead_missing]
        total = repository.ahead_total if repository.ahead_total is not None else len(listed)
        payload: dict[str, Any] = {
            "status": "ahead" if listed else "identical",
            "ahead_by": total,
            "behind_by": repository.behind,
            "total_commits": total,
            "commits": self._rest_page(listed, request),
        }
        if repository.ahead_total_absent:
            del payload["total_commits"]
        return FakeAnswer(status=200, payload=payload)

    def _packages(self, request: httpx.Request) -> list[dict[str, Any]]:
        listed = [
            {
                "name": package.name,
                "package_type": "container",
                "repository": {"full_name": package.repository} if package.repository else None,
            }
            for package in self.organisation.packages
        ]
        return self._rest_page(listed, request)

    def _versions(self, package: str, request: httpx.Request) -> list[dict[str, Any]]:
        found = next((one for one in self.organisation.packages if one.name == package), None)
        listed = [
            {"id": index, "name": f"sha256:{index:064x}", "metadata": {"container": {"tags": list(tags)}}}
            for index, tags in enumerate(found.versions if found else (), start=1)
        ]
        return self._rest_page(listed, request)

    def _rest_page(self, listed: list[dict[str, Any]], request: httpx.Request) -> list[dict[str, Any]]:
        """A REST page of exactly the size asked for, since the end of a REST list is a page
        shorter than the one asked for and not a cursor: `page_cap`, which caps a GraphQL page,
        would make every page look like the last. A REST list is read to its end by a test whose
        list runs past one page."""
        per_page = int(request.url.params.get("per_page") or 100)
        page = int(request.url.params.get("page") or 1)
        start = (page - 1) * per_page
        return listed[start : start + per_page]

    # The mechanics the fake shares.

    def _page[T](self, listed: list[T], cursor: Any, requested: Any) -> tuple[list[T], dict[str, Any]]:
        start = int(cursor) if cursor else 0
        size = self._size(requested)
        page = listed[start : start + size]
        end = start + len(page)
        return page, {"hasNextPage": end < len(listed), "endCursor": str(end)}

    def _size(self, requested: Any) -> int:
        asked = int(requested) if requested else 100
        return min(asked, self.page_cap) if self.page_cap else asked

    def _forced(self, *calls: str) -> FakeAnswer | None:
        """The answer forced for the first of these names that has one left to give."""
        for call in calls:
            answer = self.failures.get(call)
            if answer is None:
                continue
            answer.seen += 1
            if answer.seen <= answer.after or answer.spent():
                continue
            answer.used += 1
            return answer
        return None

    def _refuse(self, *calls: str) -> None:
        """A call named in `refuses` gives no answer at all, as a connection that fails gives
        none."""
        if any(call in self.refuses for call in calls):
            raise httpx.ConnectError("the connection was refused")

    async def _delay(self, *calls: str) -> None:
        seconds = next((self.delays[call] for call in calls if call in self.delays), None)
        if seconds:
            await asyncio.sleep(seconds)

    def _response(self, answer: FakeAnswer) -> httpx.Response:
        headers = dict(answer.headers)
        if self.expiry is not None:
            headers.setdefault("github-authentication-token-expiration", self.expiry)
        if answer.text is not None:
            return httpx.Response(answer.status, text=answer.text, headers=headers)
        return httpx.Response(answer.status, json=answer.payload, headers=headers)

    def _full_name(self, repository: FakeRepository) -> str:
        return f"{self.organisation.login}/{repository.name}"

    def _address(self, repository: FakeRepository) -> str:
        return f"https://github.com/{self._full_name(repository)}"
