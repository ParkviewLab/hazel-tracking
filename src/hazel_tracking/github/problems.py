# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""The words a problem is written in: what could not be gathered, why in one sentence, and the
call behind it.

Every problem the gathering reports is built here, so that the wording is one
thing and can be read against docs/what-it-shows.md. Two rules govern it. A
credential is named in general terms and never shown, so no sentence here holds a
value, and the one message carried from GitHub has already passed `calls.redact`.
And a problem says what the reader loses, not which interface the gather used: a
call is named in the page's words ("the organisation's container packages"), never
as a path or an address.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import datetime
from zoneinfo import ZoneInfo

from hazel_tracking.github.calls import Failure, FailureKind
from hazel_tracking.model import Problem, ProblemDetail

# The calls, as the dialog names them.
REPOSITORIES = "the organisation's repositories"
PACKAGES = "the organisation's container packages"
SEARCH = "the organisation's open pull requests"
STATUSES = "the pull requests whose status GitHub had not computed"
COMPARISON = "the comparison of the trunks"
BRANCH_COMPARISON = "the comparison of the branch"
COMMITS = "the pull requests of the compared commits"
FILES = "the files of the unreleased pull requests"


def of_repository(call: str, repository: str) -> str:
    return f"{call} of {repository}"


def page(call: str, number: int) -> str:
    return call if number == 1 else f"{call} (page {number})"


def group(call: str, index: int, groups: int) -> str:
    """One call of several of a kind, named so that the dialog tells them apart."""
    return call if groups == 1 else f"{call} ({index} of {groups})"


def listed(names: Sequence[str]) -> str:
    """Names in a sentence: "a", "a and b", "a, b and c"."""
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    return f"{', '.join(names[:-1])} and {names[-1]}"


def from_failure(what: str, failure: Failure, zone: ZoneInfo | None = None) -> Problem:
    """The problem one failed call makes: the facts it fed, why it failed, and its detail."""
    return Problem(
        what=what,
        why=why(failure, zone),
        details=(ProblemDetail(call=failure.call, status=failure.status, message=failure.message),),
    )


def unreadable(what: str, kind: str, call: str | None = None) -> Problem:
    """The problem an answer that could not be read at all makes. Only the kind of the error is
    carried, never its message, which could hold anything the answer held."""
    return Problem(
        what=what,
        why="GitHub's answer could not be read",
        details=(ProblemDetail(call=call or what, status=None, message=f"the answer raised {kind}"),),
    )


def empty(what: str, call: str) -> Problem:
    """The problem an answer that came without the fact asked for makes, as when GitHub answers a
    repository or a comparison with a null and no error of its own."""
    return Problem(
        what=what,
        why="GitHub answered without it",
        details=(ProblemDetail(call=call, status=None, message=None),),
    )


def truncated(what: str, call: str, listed: int, total: int, limit: int) -> Problem:
    """The problem a comparison GitHub will not list whole makes: its answer carries at most
    `limit` commits, however many pages are asked for, so a longer comparison cannot be counted."""
    return Problem(
        what=what,
        why=f"GitHub listed only {listed} of the {total} commits of the comparison",
        details=(
            ProblemDetail(
                call=call, status=200, message=f"GitHub's comparison lists at most {limit} commits"
            ),
        ),
    )


def uncomputed(what: str, call: str) -> Problem:
    """The problem a status GitHub had still not computed at the second read makes (R4): it is shown
    as not gathered, and a gather that holds one is not wholly successful, so the page tries again."""
    return Problem(
        what=what,
        why="GitHub had not computed it, asked a second time",
        details=(ProblemDetail(call=call, status=200, message=None),),
    )


def timed_out(wait_seconds: float, outstanding: Iterable[str]) -> Problem:
    """The problem a gather not complete within the wait makes, its detail naming each call still
    outstanding (R11)."""
    return Problem(
        what="the facts GitHub had not yet given",
        why=f"GitHub did not answer within the wait of {_seconds(wait_seconds)}",
        details=tuple(
            ProblemDetail(call=call, status=None, message="no answer within the wait") for call in outstanding
        ),
    )


def why(failure: Failure, zone: ZoneInfo | None = None) -> str:
    """Why a call failed, in one sentence, with a credential named in general terms alone."""
    if failure.kind is FailureKind.RATE_LIMITED:
        if failure.resets_at is None:
            return "GitHub's rate limit is spent"
        return f"GitHub's rate limit is spent; the budget resets at {_time(failure.resets_at, zone)}"
    if failure.kind is FailureKind.TOKEN_REFUSED:
        return "the GitHub token was refused"
    if failure.kind is FailureKind.SCOPE_REFUSED:
        return "GitHub refused the call; the GitHub token lacks the scope it would need"
    if failure.kind is FailureKind.REFUSED:
        return "GitHub refused the call; the GitHub token may not be allowed to read it"
    if failure.kind is FailureKind.NOT_FOUND:
        return "GitHub found nothing to read"
    if failure.kind is FailureKind.FAILED:
        return "GitHub failed on the call"
    if failure.kind is FailureKind.NO_ANSWER:
        return "GitHub gave no answer"
    if failure.kind is FailureKind.UNREADABLE:
        return "GitHub's answer could not be read"
    if failure.kind is FailureKind.TOO_LONG:
        return "GitHub's list is longer than one gather reads"
    return "GitHub answered with an error"


def _time(moment: datetime, zone: ZoneInfo | None) -> str:
    """An instant in the lab's time zone, as the page shows times."""
    return (moment.astimezone(zone) if zone is not None else moment).strftime("%H:%M")


def _seconds(seconds: float) -> str:
    whole = int(seconds)
    shown = str(whole) if seconds == whole else f"{seconds:g}"
    return f"{shown} second" if shown == "1" else f"{shown} seconds"
