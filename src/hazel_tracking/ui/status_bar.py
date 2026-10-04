# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""The status bar's one sentence, and the dialog behind its information icon.

The sentence states the health of the last full gather, with GitHub's rate limit
remaining and when it resets, the number of archived repositories not shown, and
when the GitHub token expires, yellow within `TOKEN_EXPIRY_WARNING_DAYS` of it
(docs/what-it-shows.md, "Data not gathered and the status bar"). When something
went wrong it says what and why, and the icon opens a dialog with the detail of
every problem, which for a gather not complete within the wait names each call
still outstanding (R11).

Nothing here ever shows a secret: the credential is named in general terms, and
a problem's words are the gathering's own, which the contract holds to the same
rule.
"""

from __future__ import annotations

from datetime import datetime

from hazel_tracking.config import TOKEN_EXPIRY_WARNING_DAYS, Config
from hazel_tracking.model import Problem, Snapshot
from hazel_tracking.ui import cells, text

GATHERING = "Gathering from GitHub…"
# Beyond this many problems the sentence counts them instead of naming each; the dialog has them all.
NAMED_PROBLEMS = 2


def seconds(value: float) -> str:
    """ "15 s" for a whole number of seconds, "7.5 s" otherwise."""
    return f"{value:g} s"


def health(cfg: Config, snapshot: Snapshot, *, failed: bool = False) -> str:
    """How the gather itself went: its clock and its length, that GitHub did not answer within
    the wait, or, where the gathering raised before it finished, that the gather failed."""
    if failed:
        return f"The gather failed at {text.clock(snapshot.began_at, cfg.time_zone)}"
    if snapshot.completed:
        return (
            f"Gathered from GitHub at {text.clock(snapshot.began_at, cfg.time_zone)} "
            f"in {text.duration(snapshot.duration_seconds)}"
        )
    return (
        f"GitHub did not answer within the {seconds(cfg.wait_seconds)} wait, "
        f"so this is what had arrived at {text.clock(snapshot.began_at, cfg.time_zone)}"
    )


def problems_phrase(problems: tuple[Problem, ...]) -> str:
    """What went wrong and why, named while they are few and counted when they are many."""
    if not problems:
        return ""
    if len(problems) <= NAMED_PROBLEMS:
        return ", ".join(f"{cells.escape(p.what)} ({cells.escape(p.why)})" for p in problems)
    return cells.escape(f"{text.plural(len(problems), 'fact')} could not be gathered")


def expiry_phrase(moment: datetime, now: datetime) -> str:
    """When the token expires, in yellow within `TOKEN_EXPIRY_WARNING_DAYS` of it."""
    phrase = cells.escape(text.expiry_sentence(moment, now))
    if text.days_until(moment, now) <= TOKEN_EXPIRY_WARNING_DAYS:
        return cells.span(phrase, "yellow")
    return phrase


def sentence(
    cfg: Config,
    snapshot: Snapshot | None,
    now: datetime,
    next_gather_at: datetime | None = None,
    *,
    failed: bool = False,
    also: tuple[Problem, ...] = (),
) -> str:
    """The whole sentence, as markup; `None` while the first gather is still running.

    `failed` says that the gathering raised before it finished, which the page reads as a
    gather that did not complete and names as a failure rather than as a wait run out. `also`
    holds the problems of the other gather, the open pull requests' own, which the sentence
    names beside the full gather's: the icon opens them all, so the sentence states them all.
    """
    if snapshot is None:
        return GATHERING
    parts = [health(cfg, snapshot, failed=failed)]
    trouble = problems_phrase(snapshot.problems + also)
    if trouble:
        parts.append(cells.span(trouble, "red"))
    if next_gather_at is not None and not wholly_successful(snapshot):
        parts.append(f"the page tries again at {text.clock(next_gather_at, cfg.time_zone)}")
    if snapshot.rate_limit is not None:
        parts.append(
            f"{cells.escape(text.plural(snapshot.rate_limit.remaining, 'point'))} left, resetting at "
            f"{text.clock_to_the_minute(snapshot.rate_limit.resets_at, cfg.time_zone)}"
        )
    if snapshot.archived:
        counted = text.plural(snapshot.archived, "archived repository", "archived repositories")
        parts.append(cells.escape(f"{counted} not shown"))
    if snapshot.credential_expires_at is not None:
        parts.append(expiry_phrase(snapshot.credential_expires_at, now))
    return "; ".join(parts) + "."


def wholly_successful(snapshot: Snapshot) -> bool:
    """A gather is wholly successful when it completed within the wait and no problem was reported."""
    return snapshot.completed and not snapshot.problems


def problem_html(problem: Problem) -> str:
    detail_lines = []
    for detail in problem.details:
        pieces = [cells.escape(detail.call)]
        if detail.status is not None:
            pieces.append(cells.escape(f"HTTP {detail.status}"))
        if detail.message:
            pieces.append(cells.escape(detail.message))
        joined = " \u00b7 ".join(pieces)
        detail_lines.append(f'<div class="problem-detail">{joined}</div>')
    return (
        f'<div class="problem"><div class="problem-what">{cells.escape(problem.what)}</div>'
        f'<div class="problem-why">{cells.escape(problem.why)}</div>'
        f"{''.join(detail_lines)}</div>"
    )


def dialog_html(problems: tuple[Problem, ...]) -> str:
    """Every problem's detail, as the information icon's dialog lists them."""
    if not problems:
        return '<div class="problem-why">Nothing went wrong in the last gather.</div>'
    return "".join(problem_html(p) for p in problems)
