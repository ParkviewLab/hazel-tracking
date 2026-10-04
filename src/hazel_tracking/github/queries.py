# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""The GraphQL documents the gathering sends, and the sizes of the lists they ask for.

There is no comparison here: GraphQL's `Ref.compare` refuses `aheadBy`, `behindBy`
and `status` to a token without the `repo` scope, which this token does not have and
by ruling D10 must not have, so the comparisons are read over REST (`full.py`) and
what the compared commits belong to is read here, by commit, with the oids REST gave.

Three documents name several targets at once, by alias, because one query for sixteen
repositories costs what sixteen cost separately and takes one round trip instead of
sixteen: the pull requests of the compared commits, the files of the unreleased pull
requests, and the second read of a status GitHub had not computed (R4). Each writes
one target to a line, in a fixed shape, which is also how the tests' fake GitHub
reads its aliases back. Everything else travels as a variable, so that no value this
module did not write reaches a document.

The sizes below keep every query inside GitHub's limit of 500,000 nodes, and its cost
within reason, a query's points being its nodes by the hundred: the repositories
query asks for about 7,000 nodes a page, the commits' pull requests about 11 a
commit, and the files 101 a pull request, which is why the files are asked for once
for each unreleased pull request and not once for each commit of one. Every list a
definition needs whole is read to its end, by the cursor its answer carries;
`associatedPullRequests` is the one list asked for at a size rather than paged, since
a commit belongs to its own pull request and, after a release, to the back-merge's,
never to ten.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass

# How many of each list one answer carries.
REPOSITORIES_PAGE = 25
REFS_PAGE = 100
PULL_REQUESTS_PAGE = 50
HISTORY_DEPTH = 10  # commits of a trunk, newest first, in which R2 looks for the checks
ASSOCIATED_PULL_REQUESTS = 10
FILES_PAGE = 100
SEARCH_PAGE = 100

# How many targets one aliased query names.
COMMIT_GROUP = 50
PULL_REQUEST_GROUP = 20

_RATE_LIMIT = "  rateLimit { cost remaining resetAt }"

_TRUNK_HISTORY = """fragment TrunkHistory on Ref {
  name
  target {
    ... on Commit {
      history(first: $history) { nodes { oid statusCheckRollup { state } } }
    }
  }
}"""

_PULL_REQUEST_FACTS = """fragment PullRequestFacts on PullRequest {
  number
  url
  isDraft
  mergeable
  mergeStateStatus
  baseRefName
  headRefName
  headRepository { nameWithOwner }
  commits(last: 1) { nodes { commit { statusCheckRollup { state } } } }
}"""

_COMMIT_PULL_REQUESTS = """fragment CommitPullRequests on Commit {
  oid
  associatedPullRequests(first: $associated) { nodes { number headRefName merged } }
}"""


def _document(*parts: str) -> str:
    return "\n".join(parts)


def _literal(value: str) -> str:
    """A string as a GraphQL literal. Branch and repository names are GitHub's, not ours, so
    every one of them is quoted rather than pasted."""
    return json.dumps(value)


REPOSITORIES_OPERATION = "Repositories"
REPOSITORIES = _document(
    """query Repositories($org: String!, $cursor: String, $repositories: Int!, $refs: Int!, $pulls: Int!, $history: Int!) {""",
    _RATE_LIMIT,
    """  organization(login: $org) {
    repositories(first: $repositories, after: $cursor, orderBy: {field: NAME, direction: ASC}) {
      pageInfo { hasNextPage endCursor }
      nodes {
        nameWithOwner
        isArchived
        pushedAt
        issues(states: OPEN) { totalCount }
        latestRelease { tagName }
        defaultBranchRef { ...TrunkHistory }
        mainTrunk: ref(qualifiedName: "refs/heads/main") { ...TrunkHistory }
        liveTrunk: ref(qualifiedName: "refs/heads/live") { ...TrunkHistory }
        tags: refs(refPrefix: "refs/tags/", first: $refs) { pageInfo { hasNextPage endCursor } nodes { name } }
        branches: refs(refPrefix: "refs/heads/", first: $refs) { pageInfo { hasNextPage endCursor } nodes { name } }
        pullRequests(states: OPEN, first: $pulls) {
          pageInfo { hasNextPage endCursor }
          nodes { ...PullRequestFacts }
        }
      }
    }
  }
}""",
    _TRUNK_HISTORY,
    _PULL_REQUEST_FACTS,
)

REFS_OPERATION = "RepositoryRefs"
REFS = _document(
    """query RepositoryRefs($owner: String!, $name: String!, $prefix: String!, $cursor: String, $refs: Int!) {""",
    _RATE_LIMIT,
    """  repository(owner: $owner, name: $name) {
    refs(refPrefix: $prefix, first: $refs, after: $cursor) {
      pageInfo { hasNextPage endCursor }
      nodes { name }
    }
  }
}""",
)

REPOSITORY_PULL_REQUESTS_OPERATION = "RepositoryPullRequests"
REPOSITORY_PULL_REQUESTS = _document(
    """query RepositoryPullRequests($owner: String!, $name: String!, $cursor: String, $pulls: Int!) {""",
    _RATE_LIMIT,
    """  repository(owner: $owner, name: $name) {
    pullRequests(states: OPEN, first: $pulls, after: $cursor) {
      pageInfo { hasNextPage endCursor }
      nodes { ...PullRequestFacts }
    }
  }
}""",
    _PULL_REQUEST_FACTS,
)

FILES_PAGE_OPERATION = "PullRequestFilesPage"
FILES_PAGE_QUERY = _document(
    """query PullRequestFilesPage($owner: String!, $name: String!, $number: Int!, $cursor: String, $files: Int!) {""",
    _RATE_LIMIT,
    """  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      files(first: $files, after: $cursor) {
        pageInfo { hasNextPage endCursor }
        nodes { path }
      }
    }
  }
}""",
)

OPEN_PULL_REQUESTS_OPERATION = "OpenPullRequests"
OPEN_PULL_REQUESTS = _document(
    """query OpenPullRequests($query: String!, $cursor: String, $pulls: Int!) {""",
    _RATE_LIMIT,
    """  search(query: $query, type: ISSUE, first: $pulls, after: $cursor) {
      pageInfo { hasNextPage endCursor }
      nodes {
        ... on PullRequest {
          title
          repository { nameWithOwner defaultBranchRef { name } }
          ...PullRequestFacts
        }
      }
  }
}""",
    _PULL_REQUEST_FACTS,
)

COMMIT_PULL_REQUESTS_OPERATION = "CommitPullRequests"
FILES_OPERATION = "PullRequestFiles"
STATUSES_OPERATION = "PullRequestStatuses"


@dataclass(frozen=True)
class CommitTarget:
    """The compared commits of one repository, by the oids REST's comparison gave."""

    repository: str
    oids: Sequence[str]


def commit_pull_requests(targets: Sequence[CommitTarget]) -> str:
    """The aliased query for what the compared commits belong to: `r<i>` for each repository and
    `c<j>` for each of its commits, one to a line.

    GitHub resolves a commit by its oid through `object`, which answers any git object, so the
    fragment names the kind it wants. A commit the repository does not hold answers as a null,
    which the reading reports rather than reads as "no pull request" (R5).
    """
    lines = [
        "query CommitPullRequests($owner: String!, $associated: Int!) {",
        _RATE_LIMIT,
    ]
    for index, target in enumerate(targets):
        lines.append(f"  r{index}: repository(owner: $owner, name: {_literal(target.repository)}) {{")
        for position, oid in enumerate(target.oids):
            lines.append(f"    c{position}: object(oid: {_literal(oid)}) {{ ...CommitPullRequests }}")
        lines.append("  }")
    lines.append("}")
    return _document(*lines, _COMMIT_PULL_REQUESTS)


@dataclass(frozen=True)
class PullRequestTarget:
    """One pull request of one repository, named for a second read of its status (R4) or for its
    changed files (R5)."""

    repository: str
    number: int


def files(targets: Sequence[PullRequestTarget]) -> str:
    """The aliased query for the changed files of these pull requests, `f<i>` one to a line."""
    lines = ["query PullRequestFiles($owner: String!, $files: Int!) {", _RATE_LIMIT]
    for index, target in enumerate(targets):
        lines.append(
            f"  f{index}: repository(owner: $owner, name: {_literal(target.repository)}) "
            f"{{ pullRequest(number: {target.number}) "
            "{ files(first: $files) { pageInfo { hasNextPage endCursor } nodes { path } } } }"
        )
    lines.append("}")
    return _document(*lines)


def statuses(targets: Sequence[PullRequestTarget]) -> str:
    """The aliased query that reads these pull requests once more, for R4's second read, `s<i>`
    one to a line."""
    lines = ["query PullRequestStatuses($owner: String!) {", _RATE_LIMIT]
    for index, target in enumerate(targets):
        lines.append(
            f"  s{index}: repository(owner: $owner, name: {_literal(target.repository)}) "
            f"{{ pullRequest(number: {target.number}) {{ ...PullRequestFacts }} }}"
        )
    lines.append("}")
    return _document(*lines, _PULL_REQUEST_FACTS)


def search_query(org: str) -> str:
    """The one search the gather of the open pull requests alone sends, which cost 1 point when
    it was measured on 2026-10-03."""
    return f"org:{org} is:pr is:open archived:false"
