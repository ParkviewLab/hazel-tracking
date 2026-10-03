# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""When the page gathers by itself: the 30-minute cycle and the retries behind it.

The rule is docs/what-it-shows.md, "When the page gathers". The automatic full
gather runs `cfg.gather_interval_seconds` after the last full gather began,
whatever started it. After a full gather that is not wholly successful the page
tries again after each of `cfg.retry_delays_seconds` in turn, measured likewise
from when that gather began; after the last of them the cycle resumes. Any
wholly successful full gather, the Refresh button's or a page load's included,
ends the retries and restarts the cycle.

It is a one-shot timer, cancelled at the start of every full gather and set when
that gather ends, rather than a repeating one, which would keep its own schedule
whatever Refresh did. The timer belongs to the browser's connection, so the
cycle stops when the page is closed and no two browsers share one.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta

from nicegui import ui

from hazel_tracking.config import Config


class GatherSchedule:
    """The automatic full gather for one browser, as a one-shot timer that is re-set each time."""

    def __init__(self, cfg: Config, run: Callable[[], Awaitable[None]], parent: ui.element) -> None:
        self._cfg = cfg
        self._run = run
        self._parent = parent
        self._timer: ui.timer | None = None
        self._attempt = 0
        self._next_at: datetime | None = None

    @property
    def next_at(self) -> datetime | None:
        """When the page next gathers by itself, `None` while a gather is running."""
        return self._next_at

    @property
    def attempt(self) -> int:
        """How many retries have been set since the last wholly successful gather."""
        return self._attempt

    def cancel(self) -> None:
        """Drop the pending timer; done at the start of every full gather."""
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        self._next_at = None

    def delay_after(self, *, wholly_successful: bool) -> float:
        """How long after a gather began the next one falls due, and advance the retries."""
        if wholly_successful:
            self._attempt = 0
            return self._cfg.gather_interval_seconds
        if self._attempt < len(self._cfg.retry_delays_seconds):
            delay = self._cfg.retry_delays_seconds[self._attempt]
            self._attempt += 1
            return delay
        self._attempt = 0
        return self._cfg.gather_interval_seconds

    def set_after(self, *, wholly_successful: bool, elapsed_seconds: float) -> None:
        """Set the timer for the next gather, `elapsed_seconds` after the one that just ended began."""
        self.cancel()
        delay = max(self.delay_after(wholly_successful=wholly_successful) - elapsed_seconds, 0.0)
        self._next_at = datetime.now(self._cfg.time_zone) + timedelta(seconds=delay)
        with self._parent:
            self._timer = ui.timer(delay, self._fire, once=True)

    async def _fire(self) -> None:
        self._timer = None
        self._next_at = None
        await self._run()
