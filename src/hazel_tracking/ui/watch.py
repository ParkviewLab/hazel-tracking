# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""The pull-requests tab's Watch: what it compares, and every rule by which it stops.

The rule is docs/what-it-shows.md, "The pull requests". The watch gathers the
open pull requests alone every `cfg.watch_interval_seconds` and stops when the
set of open pull requests changes, a pull request by repository and number
appearing or disappearing; after `cfg.watch_limit_seconds`; when the reader
leaves the tab; and when the page is closed. Started from one pull request's
row, it also stops when that pull request's status changes. Moving to another
browser tab or another application does not stop it: the watch counts time, not
attention.

A gather of its own that could not read the pull requests stops nothing and
compares nothing: an unanswered search is not a pull request disappearing (R7,
axiom 8).

The comparison and the words it yields are pure functions of two snapshots, so
every stopping rule can be read in a test without a clock.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum

from nicegui import ui

from hazel_tracking.config import Config
from hazel_tracking.model import (
    Gathered,
    GatherPullRequests,
    OpenPullRequest,
    PullRequestsSnapshot,
    PullRequestStatus,
)
from hazel_tracking.ui import text

type Key = tuple[str, int]


class StopReason(StrEnum):
    """Why a watch stopped. Only a change marks the browser tab's title."""

    SET_CHANGED = "the open pull requests changed"
    STATUS_CHANGED = "the pull request's status changed"
    LIMIT = "the watch's time ran out"
    LEFT_TAB = "the reader left the tab"
    CANCELLED = "the reader stopped the watch"


@dataclass(frozen=True)
class Stop:
    """How a watch ended: why, the mark for the browser tab's title where it stopped on a
    change, and the line the tab shows naming what changed."""

    reason: StopReason
    title_mark: str | None = None
    detail: str | None = None

    @property
    def on_a_change(self) -> bool:
        return self.reason in (StopReason.SET_CHANGED, StopReason.STATUS_CHANGED)


def keys(snapshot: PullRequestsSnapshot) -> frozenset[Key] | None:
    """Every open pull request by repository and number, or `None` where the search did not answer."""
    if not isinstance(snapshot.pull_requests, Gathered):
        return None
    return frozenset((p.repository, p.pull_request.number) for p in snapshot.pull_requests.value)


def by_key(snapshot: PullRequestsSnapshot) -> dict[Key, OpenPullRequest]:
    if not isinstance(snapshot.pull_requests, Gathered):
        return {}
    return {(p.repository, p.pull_request.number): p for p in snapshot.pull_requests.value}


def named(key: Key) -> str:
    repository, number = key
    return f"{repository.split('/')[-1]} #{number}"


def set_change(before: PullRequestsSnapshot, after: PullRequestsSnapshot) -> Stop | None:
    """The stop for a change in the set of open pull requests, or `None` where it is unchanged."""
    was, now = keys(before), keys(after)
    if was is None or now is None or was == now:
        return None
    arrived = sorted(now - was)
    left = sorted(was - now)
    marks = []
    if arrived:
        marks.append(text.plural(len(arrived), "new pull request"))
    if left:
        closed = text.plural(len(left), "pull request")
        marks.append(f"{len(left)} closed" if arrived else f"{closed} closed")
    detail = ", ".join(
        [f"{named(k)} arrived" for k in arrived] + [f"{named(k)} is no longer open" for k in left]
    )
    return Stop(StopReason.SET_CHANGED, ", ".join(marks), detail)


def status_of(snapshot: PullRequestsSnapshot, key: Key) -> PullRequestStatus | None:
    found = by_key(snapshot).get(key)
    if found is None or not isinstance(found.pull_request.status, Gathered):
        return None
    return found.pull_request.status.value


def status_change(before: PullRequestsSnapshot, after: PullRequestsSnapshot, key: Key) -> Stop | None:
    """The stop for a change in the status of the pull request the watch was started from."""
    was, now = status_of(before, key), status_of(after, key)
    if was is None or now is None or was == now:
        return None
    _, number = key
    return Stop(StopReason.STATUS_CHANGED, f"#{number} {now}", f"{named(key)} is now {now}")


class Watch:
    """One browser's watch: the timer, the baseline it compares against, and the target."""

    def __init__(
        self,
        cfg: Config,
        gather_pull_requests: GatherPullRequests,
        parent: ui.element,
        *,
        on_gather: Callable[[PullRequestsSnapshot], None],
        on_stop: Callable[[Stop], None],
        on_error: Callable[[Exception], Awaitable[None] | None] | None = None,
    ) -> None:
        self._cfg = cfg
        self._gather = gather_pull_requests
        self._parent = parent
        self._on_gather = on_gather
        self._on_stop = on_stop
        self._on_error = on_error
        self._timer: ui.timer | None = None
        self._baseline: PullRequestsSnapshot | None = None
        self._target: Key | None = None
        self._deadline = 0.0

    @property
    def watching(self) -> bool:
        return self._timer is not None

    @property
    def target(self) -> Key | None:
        """The pull request the watch waits for, `None` where it watches the whole set."""
        return self._target

    def start(self, baseline: PullRequestsSnapshot, target: Key | None = None) -> None:
        """Begin watching, comparing every gather against `baseline`."""
        self.cancel(quietly=True)
        self._baseline = baseline
        self._target = target
        self._deadline = time.monotonic() + self._cfg.watch_limit_seconds
        with self._parent:
            self._timer = ui.timer(self._cfg.watch_interval_seconds, self._tick, immediate=False)

    def cancel(self, *, quietly: bool = False, reason: StopReason = StopReason.CANCELLED) -> None:
        """Stop the watch without a change: the reader's doing, or the tab being left."""
        watching = self.watching
        self._halt()
        if watching and not quietly:
            self._on_stop(Stop(reason))

    def _halt(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        self._baseline = None
        self._target = None

    async def _tick(self) -> None:
        if not self.watching:
            return
        if time.monotonic() >= self._deadline:
            self._halt()
            self._on_stop(Stop(StopReason.LIMIT))
            return
        try:
            snapshot = await self._gather()
        # A gather that raised stops nothing and compares nothing; the page reports it.
        except Exception as error:
            if self._on_error is not None:
                result = self._on_error(error)
                if result is not None:
                    await result
            return
        if not self.watching:
            return
        self._on_gather(snapshot)
        baseline = self._baseline
        if baseline is None:
            return
        stop = set_change(baseline, snapshot)
        if stop is None and self._target is not None:
            stop = status_change(baseline, snapshot, self._target)
        if stop is not None:
            self._halt()
            self._on_stop(stop)
