# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""The gather of the open pull requests alone, for the pull-requests tab and its watch.

One search, `org:<org> is:pr is:open archived:false`, answers it: it cost 1 point
when it was measured on 2026-10-03, against 51 for the same facts read repository by
repository, which is what makes the tab's own Refresh and its watch cheap enough to
repeat every 10 seconds (northstar, intent 3).

What the search returns is filtered here, not by GitHub, because neither condition
is a search term: a pull request is kept when its base is its repository's
integration trunk, which is the default branch (R1), and when its head branch does
not begin `back-merge-`, the branch `git back-merge` opens at the end of every
release. Dependabot's are kept, as every other author's are. A status GitHub had not
computed is read once more, as R4 requires of a status anywhere.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from dataclasses import dataclass, field, replace

from hazel_tracking.config import Config
from hazel_tracking.github import facts, problems, queries
from hazel_tracking.github.calls import PAGE_LIMIT, Reader, dig, nodes, page_cursor
from hazel_tracking.github.collecting import groups, guard, report
from hazel_tracking.model import (
    NOT_GATHERED,
    Gathered,
    NotGathered,
    OpenPullRequest,
    Problem,
    PullRequest,
    PullRequestStatus,
)

logger = logging.getLogger(__name__)


@dataclass
class PullRequestsState:
    """What the gather of the open pull requests has collected.

    `pull_requests` is `None` until the search answers, and stays `None` where it could not be
    read to its end: which pull requests are open is a fact of the whole list.
    """

    pull_requests: list[OpenPullRequest] | None = None
    uncomputed: set[tuple[str, int]] = field(default_factory=set)
    problems: list[Problem] = field(default_factory=list)

    def to_model(self) -> tuple[OpenPullRequest, ...]:
        """The open pull requests in the order of their repositories and numbers."""
        found = self.pull_requests or []
        return tuple(
            sorted(found, key=lambda open_pull: (open_pull.repository, open_pull.pull_request.number))
        )


async def collect(cfg: Config, reader: Reader, state: PullRequestsState) -> None:
    """Send the search, and the second read of any status it answered as uncomputed."""
    await guard(state.problems, "the open pull requests", _search(cfg, reader, state))
    if state.pull_requests is None or not state.uncomputed:
        return
    await guard(
        state.problems,
        "the status of each pull request GitHub had not computed",
        _second_read(cfg, reader, state),
    )


async def _search(cfg: Config, reader: Reader, state: PullRequestsState) -> None:
    cursor: str | None = None
    found: list[OpenPullRequest] = []
    for number in range(1, PAGE_LIMIT + 1):
        reply = await reader.graphql(
            problems.page(problems.SEARCH, number),
            queries.OPEN_PULL_REQUESTS_OPERATION,
            queries.OPEN_PULL_REQUESTS,
            {"query": queries.search_query(cfg.github_org), "cursor": cursor, "pulls": queries.SEARCH_PAGE},
        )
        connection = dig(reply.data, "search")
        if connection is None:
            state.pull_requests = None
            state.uncomputed.clear()
            report(state.problems, cfg, "the open pull requests", reply)
            return
        for node in nodes(connection):
            kept = _open_pull_request(node)
            if kept is not None:
                found.append(kept)
                if isinstance(kept.pull_request.status, NotGathered):
                    state.uncomputed.add((kept.repository, kept.pull_request.number))
        state.pull_requests = list(found)
        cursor = page_cursor(connection)
        if cursor is None:
            return


def _open_pull_request(node: object) -> OpenPullRequest | None:
    """One pull request of the search, or `None` where it is not one the tab lists."""
    repository = dig(node, "repository", "nameWithOwner")
    number, url, title = dig(node, "number"), dig(node, "url"), dig(node, "title")
    base, head = dig(node, "baseRefName"), dig(node, "headRefName")
    if not isinstance(repository, str) or not isinstance(number, int):
        return None
    integration = facts.default_branch(dig(node, "repository"))
    if not isinstance(base, str) or base != integration:
        return None
    if isinstance(head, str) and head.startswith(facts.BACK_MERGE_PREFIX):
        return None
    status = facts.pull_request_status(node)
    return OpenPullRequest(
        repository=repository,
        title=title if isinstance(title, str) else "",
        pull_request=PullRequest(
            number=number,
            url=url if isinstance(url, str) else "",
            status=NOT_GATHERED if status is None else Gathered(status),
        ),
    )


async def _second_read(cfg: Config, reader: Reader, state: PullRequestsState) -> None:
    """R4's second read, for the statuses the search answered as uncomputed."""
    waiting = sorted(state.uncomputed)
    batches = groups(waiting, queries.PULL_REQUEST_GROUP)
    async with asyncio.TaskGroup() as group:
        for index, batch in enumerate(batches, start=1):
            what = "the status of " + problems.listed([f"{name}#{number}" for name, number in batch])
            group.create_task(
                guard(state.problems, what, _statuses(cfg, reader, state, batch, index, len(batches)))
            )


async def _statuses(
    cfg: Config,
    reader: Reader,
    state: PullRequestsState,
    batch: Sequence[tuple[str, int]],
    index: int,
    batches: int,
) -> None:
    call = problems.group(problems.STATUSES, index, batches)
    targets = [queries.PullRequestTarget(name.rpartition("/")[2], number) for name, number in batch]
    reply = await reader.graphql(
        call, queries.STATUSES_OPERATION, queries.statuses(targets), {"owner": cfg.github_org}
    )
    if reply.data is None:
        what = "the status of " + problems.listed([f"{name}#{number}" for name, number in batch])
        report(state.problems, cfg, what, reply)
        return
    for position, (name, number) in enumerate(batch):
        pull = dig(reply.data, f"s{position}", "pullRequest")
        status = facts.pull_request_status(pull) if pull is not None else None
        if status is not None:
            _set_status(state, name, number, status)
        elif pull is None:
            report(state.problems, cfg, f"the status of {name}#{number}", reply)


def _set_status(state: PullRequestsState, repository: str, number: int, status: PullRequestStatus) -> None:
    if state.pull_requests is None:
        return
    state.pull_requests = [
        replace(open_pull, pull_request=replace(open_pull.pull_request, status=Gathered(status)))
        if open_pull.repository == repository and open_pull.pull_request.number == number
        else open_pull
        for open_pull in state.pull_requests
    ]
