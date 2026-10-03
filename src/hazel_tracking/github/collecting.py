# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""What both gathers do the same way: the wait that bounds them, the guard that keeps one
failure from taking the rest with it, and the grouping of targets into one call.

The wait is the gather's one deadline (D7): the work runs under it, and what the
tasks had written into their state when it ran out is what the page shows, marked
incomplete (R11). Because the state is written as each answer arrives, and not
assembled at the end, a gather cut short keeps every fact that did arrive.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Coroutine, Sequence
from typing import Any

from hazel_tracking.config import Config
from hazel_tracking.github import problems
from hazel_tracking.github.calls import Failure, Reply
from hazel_tracking.model import Problem

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
