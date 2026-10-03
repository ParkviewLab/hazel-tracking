# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""The page's words and its clocks: the formatting every view shares.

Pure functions, each given the moment it is to reckon against, so that a test
fixes time rather than waiting for it. Every clock reads in the lab's zone,
which `Config.time_zone` carries (docs/what-it-shows.md, "When the page
gathers").

The marks beside the state words are the shapes that carry state without
colour (R10): a filled circle for passing and ready, a half circle for running
and pending, a cross for failing and conflicts.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from hazel_tracking.model import CheckState, PullRequestStatus

# The shapes that carry state without colour (R10), and the class that carries its colour.
MARK_GOOD = "●"  # a filled circle
MARK_PENDING = "◐"  # a half circle
MARK_BAD = "✕"  # a cross

GOOD = (MARK_GOOD, "sage")
PENDING = (MARK_PENDING, "yellow")
BAD = (MARK_BAD, "red")
PLAIN = ("", "")

CHECK_STATE_STYLE: dict[CheckState, tuple[str, str]] = {
    CheckState.PASSING: GOOD,
    CheckState.FAILING: BAD,
    CheckState.RUNNING: PENDING,
    CheckState.NONE: PLAIN,
}

PULL_REQUEST_STYLE: dict[PullRequestStatus, tuple[str, str]] = {
    PullRequestStatus.DRAFT: PLAIN,
    PullRequestStatus.CONFLICTS: BAD,
    PullRequestStatus.CHECKS_FAILING: BAD,
    PullRequestStatus.CHECKS_RUNNING: PENDING,
    PullRequestStatus.BEHIND: PENDING,
    PullRequestStatus.READY: GOOD,
}

# The value shown for a fact that was not gathered and has no number and no yes-or-no (R7).
ZEROED_VALUE = "—"

# Beyond this the last push is shown as a date rather than as a time since it.
RELATIVE_LIMIT_HOURS = 36


def plural(count: int, singular: str, many: str | None = None) -> str:
    """ "1 pull request", "3 pull requests"."""
    word = singular if count == 1 else (many if many is not None else f"{singular}s")
    return f"{count} {word}"


def clock(moment: datetime, zone: ZoneInfo) -> str:
    """ "14:03:12" in the lab's zone."""
    return moment.astimezone(zone).strftime("%H:%M:%S")


def clock_to_the_minute(moment: datetime, zone: ZoneInfo) -> str:
    """ "14:47" in the lab's zone."""
    return moment.astimezone(zone).strftime("%H:%M")


def duration(seconds: float) -> str:
    """ "3.1 s"."""
    return f"{seconds:.1f} s"


def since(moment: datetime, now: datetime, zone: ZoneInfo) -> str:
    """The time since the last push, up to 36 hours, and the date after that.

    "6 min ago", "34 h ago", "30 Sep 2026" (docs/what-it-shows.md, "Last push"). The date is
    the date in the lab's zone, since a moment late in the day is a different date elsewhere.
    """
    seconds = (now - moment).total_seconds()
    if seconds < 0:
        seconds = 0.0
    if seconds < 90:
        return f"{int(seconds)} s ago"
    if seconds < 90 * 60:
        return f"{int(seconds // 60)} min ago"
    if seconds < RELATIVE_LIMIT_HOURS * 3600:
        return f"{int(seconds // 3600)} h ago"
    return moment.astimezone(zone).strftime("%-d %b %Y")


def age(seconds: float) -> str:
    """How old the data is, in minutes and seconds, for the clock that advances each second."""
    whole = int(max(seconds, 0))
    if whole < 60:
        return f"{whole} s"
    if whole < 3600:
        return f"{whole // 60} min {whole % 60:02d} s"
    return f"{whole // 3600} h {(whole % 3600) // 60:02d} min"


def days_until(moment: datetime, now: datetime) -> int:
    """Whole days from `now` to `moment`, rounded down; negative once it has passed."""
    return int((moment - now).total_seconds() // 86400)


def expiry_sentence(moment: datetime, now: datetime) -> str:
    """When the GitHub token expires, named in general terms and never with its value."""
    days = days_until(moment, now)
    if days < 0:
        return "the GitHub token has expired"
    if days == 0:
        return "the GitHub token expires today"
    return f"the GitHub token expires in {plural(days, 'day')}"
