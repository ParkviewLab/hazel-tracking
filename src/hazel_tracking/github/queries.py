# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""The GraphQL documents the gathering sends, and the sizes of the lists they ask for.

Three of them name several targets at once, by alias, because one query for sixteen
repositories costs what sixteen queries cost and takes one round trip instead of
sixteen: the comparisons, the files of the unreleased pull requests, and the second
read of a status GitHub had not computed (R4). Each writes one target to a line, in
a fixed shape, which is also how the tests' fake GitHub reads its aliases back.
Everything else travels as a variable, so that no value this module did not write
reaches a document.

The sizes below keep every query inside GitHub's limit of 500,000 nodes: the
repositories query asks for about 7,000 nodes a page and the comparisons for about
10,000 a repository. Every list a definition needs whole is read to its end, by the
cursor its answer carries; `associatedPullRequests` is the one list asked for at a
size rather than paged, since a commit belongs to its own pull request and, after a
release, to the back-merge's, never to ten.
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
COMPARED_COMMITS_PAGE = 50
ASSOCIATED_PULL_REQUESTS = 10
FILES_PAGE = 100
SEARCH_PAGE = 100

# How many targets one aliased query names.
COMPARISON_GROUP = 8
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
  commits(last: 1) { nodes { commit { statusCheckRollup { state } } } }
}"""

_COMPARED_COMMIT = """fragment ComparedCommit on Commit {
  oid
  associatedPullRequests(first: $associated) { nodes { number headRefName merged } }
}"""

_COMPARISON = (
    "compare(headRef: %s) { aheadBy behindBy commits(first: $commits) "
    "{ pageInfo { hasNextPage endCursor } nodes { ...ComparedCommit } } }"
)


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
        url
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

COMPARED_COMMITS_OPERATION = "ComparedCommits"
COMPARED_COMMITS = _document(
    """query ComparedCommits($owner: String!, $name: String!, $base: String!, $head: String!, $cursor: String, $commits: Int!, $associated: Int!) {""",
    _RATE_LIMIT,
    """  repository(owner: $owner, name: $name) {
    ref(qualifiedName: $base) {
      compare(headRef: $head) {
        aheadBy
        behindBy
        commits(first: $commits, after: $cursor) {
          pageInfo { hasNextPage endCursor }
          nodes { ...ComparedCommit }
        }
      }
    }
  }
}""",
    _COMPARED_COMMIT,
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

COMPARISONS_OPERATION = "Comparisons"
FILES_OPERATION = "PullRequestFiles"
STATUSES_OPERATION = "PullRequestStatuses"


@dataclass(frozen=True)
class ComparisonTarget:
    """One repository's comparisons: its trunks', where it has a release trunk (R1), and one for
    each working branch, whose lag is measured against the integration trunk, the default
    branch."""

    repository: str  # the name alone, as GitHub's `name` argument takes it
    integration: str
    release: str | None
    branches: Sequence[str]


def comparisons(targets: Sequence[ComparisonTarget]) -> str:
    """The aliased comparison query for these repositories: `r<i>` for each repository, `trunks`
    for its trunks' comparison and `b<j>` for each working branch's, one to a line."""
    lines = [
        "query Comparisons($owner: String!, $commits: Int!, $associated: Int!) {",
        _RATE_LIMIT,
    ]
    for index, target in enumerate(targets):
        lines.append(f"  r{index}: repository(owner: $owner, name: {_literal(target.repository)}) {{")
        # Named in every block, so that a repository with neither a release trunk nor a working
        # branch still asks for something and the aliases keep their places.
        lines.append("    nameWithOwner")
        if target.release is not None:
            comparison = _COMPARISON % _literal(target.integration)
            lines.append(f"    trunks: {_ref(target.release)} {{ {comparison} }}")
        for branch_index, branch in enumerate(target.branches):
            behind = f"compare(headRef: {_literal(branch)}) {{ behindBy }}"
            lines.append(f"    b{branch_index}: {_ref(target.integration)} {{ {behind} }}")
        lines.append("  }")
    lines.append("}")
    return _document(*lines, _COMPARED_COMMIT)


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


def _ref(branch: str) -> str:
    return f"ref(qualifiedName: {_literal(f'refs/heads/{branch}')})"


def search_query(org: str) -> str:
    """The one search the gather of the open pull requests alone sends, which cost 1 point when
    it was measured on 2026-10-03."""
    return f"org:{org} is:pr is:open archived:false"
