# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""What both gathers do the same way: the wait that bounds them, the guard that keeps one
failure from taking the rest with it, the grouping of targets into one call, the reading of
what one call for many targets lost, and R4's second read, which both gathers need.

The wait is the gather's one deadline (D7): the work runs under it, and what the
tasks had written into their state when it ran out is what the page shows, marked
incomplete (R11). A fact is pending from the moment a call feeding it is made and is
written only when every call feeding it has answered, so that a fact still being
read when the wait runs out is not gathered rather than published part-read.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Coroutine, Sequence
from typing import Any

from hazel_tracking.config import Config
from hazel_tracking.github import facts, problems, queries
from hazel_tracking.github.calls import Failure, Reader, Reply, dig
from hazel_tracking.model import Problem, PullRequestStatus

logger = logging.getLogger(__name__)


async def within_the_wait(cfg: Config, work: Coroutine[Any, Any, None]) -> bool:
    """Run `work` under the configured wait, and say whether it completed within it.

    A gather that runs out of time is cancelled where it stands, which leaves each call it had
    sent and not had answered outstanding, and those are the calls R11's problem names.
    """
    try:
        async with asyncio.timeout(cfg.wait_seconds):
            await work
    except TimeoutError:
        logger.warning("the gather did not complete within the wait of %s s", cfg.wait_seconds)
        return False
    return True


async def guard(into: list[Problem], what: str, work: Coroutine[Any, Any, None]) -> None:
    """Run `work`, and turn anything it raises unexpectedly into a problem for `what`.

    A gather reads answers whose shape is GitHub's, not ours, so one answer that is not of the
    shape its reading expects must cost the facts it feeds and nothing else (axiom 8). Only the
    kind of the error is reported: its message could hold whatever the answer held.
    """
    try:
        await work
    except asyncio.CancelledError:
        raise
    except Exception as unexpected:
        logger.warning("%s could not be read: %s", what, type(unexpected).__name__)
        into.append(problems.unreadable(what, type(unexpected).__name__))


def report(into: list[Problem], cfg: Config, what: str, reply: Reply) -> None:
    """The problem a reply that gave nothing makes, whether it failed or answered without it."""
    if reply.failure is not None:
        into.append(problems.from_failure(what, reply.failure, cfg.time_zone))
    else:
        into.append(problems.empty(what, reply.call))


def groups[T](targets: Sequence[T], size: int) -> list[Sequence[T]]:
    """`targets` in groups of at most `size`, each group one call."""
    return [targets[start : start + size] for start in range(0, len(targets), size)]


def reaches(failure: Failure | None, *aliases: str) -> bool:
    """Whether a failure reaches the target these aliases name.

    A GraphQL answer may carry data for some of a call's targets and an error for others, each error
    naming where it fell; a target is lost where an error fell at it, above it or within it. An
    answer whose errors name no path at all is read as a loss of every target of that call, since
    there is nothing to tell which of them it concerns.
    """
    if failure is None:
        return False
    if not failure.paths:
        return True
    for path in failure.paths:
        shared = min(len(path), len(aliases))
        if tuple(path[:shared]) == aliases[:shared]:
            return True
    return False


def lost(into: list[Problem], what: str, reply: Reply, answered: Any, *aliases: str) -> bool:
    """Whether one target of a call for many was lost, and the problem where it was.

    A target is lost where the answer holds nothing for it or where the errors reach it. A loss the
    errors explain is reported once for the whole call by `report`, so only a target answered with a
    bare null, which no error accounts for, is reported here.
    """
    if reaches(reply.failure, *aliases):
        return True
    if answered is None:
        into.append(problems.empty(what, reply.call))
        return True
    return False


async def second_read(
    cfg: Config,
    reader: Reader,
    into: list[Problem],
    targets: Sequence[tuple[str, int]],
    publish: Callable[[str, int, PullRequestStatus], None],
) -> None:
    """R4's second read, which both gathers need: the statuses GitHub had not computed, read once
    more, in one aliased query for every twenty of them.

    `targets` names each pull request as its repository (`owner/name`) and its number; `publish` is
    called for each status GitHub has computed by now. A status still uncomputed is left as it was,
    not gathered, with a problem of its own, so that the gather is not wholly successful and the
    page tries again (R4, R8).
    """
    ordered = sorted(set(targets))
    if not ordered:
        return
    batches = groups(ordered, queries.PULL_REQUEST_GROUP)
    async with asyncio.TaskGroup() as group:
        for index, batch in enumerate(batches, start=1):
            group.create_task(
                guard(
                    into,
                    _statuses_what(batch),
                    _statuses(cfg, reader, into, batch, index, len(batches), publish),
                )
            )


def _statuses_what(batch: Sequence[tuple[str, int]]) -> str:
    return "the status of " + problems.listed([f"{name}#{number}" for name, number in batch])


async def _statuses(
    cfg: Config,
    reader: Reader,
    into: list[Problem],
    batch: Sequence[tuple[str, int]],
    index: int,
    batches: int,
    publish: Callable[[str, int, PullRequestStatus], None],
) -> None:
    call = problems.group(problems.STATUSES, index, batches)
    targets = [queries.PullRequestTarget(name.rpartition("/")[2], number) for name, number in batch]
    reply = await reader.graphql(
        call, queries.STATUSES_OPERATION, queries.statuses(targets), {"owner": cfg.github_org}
    )
    if reply.failure is not None:
        report(into, cfg, _statuses_what(batch), reply)
    if reply.data is None:
        return
    for position, (name, number) in enumerate(batch):
        what = f"the status of {name}#{number}"
        pull = dig(reply.data, f"s{position}", "pullRequest")
        if lost(into, what, reply, pull, f"s{position}"):
            continue
        status = facts.pull_request_status(pull)
        if status is None:
            into.append(problems.uncomputed(what, call))
            continue
        publish(name, number, status)
