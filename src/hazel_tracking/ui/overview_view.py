# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""The overview: one screen, a repository a line, distilled from the full gather.

Four columns (docs/what-it-shows.md, "The overview"): the repository; its release
state, the newest final version with the dev version beside it where that is
newer; its readiness, as the detail's Release column reads it, with the count of
unreleased pull requests and the documentation note; and what waits on the
reader. A repository with nothing waiting is shown quietly, its line dimmed, so
that the eye goes to those that need something; a fact that could not be
gathered counts as waiting and is greyed where it stands (R7).

Readiness is named once. "A release ready to cut" and "a pending back-merge" are
both things that wait on the reader and the readiness indicator's own words, so
the Waiting column leaves them to the Readiness column beside it and the line's
not being quiet is what marks the repository as waiting.

`overview.overview(snapshot)` makes the rows; this module only shows them.
"""

from __future__ import annotations

from hazel_tracking.model import Gathered, PullRequestStatus, Snapshot
from hazel_tracking.overview import OverviewRow, overview
from hazel_tracking.ui import cells, text

COLUMNS = ("Repository", "Release state", "Readiness", "Waiting on you")

# Each status that calls for the reader, with the style its count is shown in.
STATUS_STYLE = {
    PullRequestStatus.READY: text.GOOD,
    PullRequestStatus.CONFLICTS: text.BAD,
    PullRequestStatus.CHECKS_FAILING: text.BAD,
    PullRequestStatus.BEHIND: text.PENDING,
}


def release_state_cell(row: OverviewRow) -> str:
    """The newest final version, with the dev version beside it where that is newer."""
    if not isinstance(row.final_version, Gathered):
        final = cells.ungathered_value()
    elif row.final_version.value is None:
        final = cells.nothing()
    else:
        final = cells.span(cells.escape(row.final_version.value), "strong")
    if not isinstance(row.dev_release, Gathered):
        return final + " " + cells.span(f"dev {text.ZEROED_VALUE}", "ungathered")
    if row.dev_release.value is None:
        return final
    return final + " " + cells.span(f"dev {cells.escape(row.dev_release.value.version)}", "sub")


def waiting_cell(row: OverviewRow) -> str:
    """The trunks whose checks fail, the open pull requests counted by the statuses that call
    for the reader, and the open issues; each fact not gathered counts as waiting and is
    greyed, zeroed as R7 reads it."""
    parts: list[str] = []
    if isinstance(row.failing_trunks, Gathered):
        if row.failing_trunks.value:
            trunks = ", ".join(row.failing_trunks.value)
            parts.append(cells.state(text.BAD, f"checks failing on {trunks}"))
    else:
        parts.append(cells.ungathered(f"checks {text.ZEROED_VALUE}"))
    if isinstance(row.pull_requests_waiting, Gathered):
        for status, count in row.pull_requests_waiting.value:
            if count:
                parts.append(cells.state(STATUS_STYLE[status], f"{count} {status}"))
    else:
        parts.append(cells.ungathered("0 pull requests"))
    if isinstance(row.open_issues, Gathered):
        if row.open_issues.value:
            parts.append(cells.escape(text.plural(row.open_issues.value, "issue")))
    else:
        parts.append(cells.ungathered("0 issues"))
    return cells.chips(parts)


def line(row: OverviewRow, readiness: str) -> str:
    quiet = "" if row.waiting else ' class="quiet"'
    name = cells.repository_url(row.name)
    repository = (
        f'<a class="plain" href="{cells.escape(name)}" target="_blank" rel="noopener" '
        f'title="{cells.escape(row.name)}">{cells.escape(cells.short_name(row.name))}</a>'
    )
    return (
        f"<tr{quiet}>"
        f'<td class="repo">{repository}</td>'
        f"<td>{release_state_cell(row)}</td>"
        f"<td>{readiness}</td>"
        f"<td>{waiting_cell(row)}</td>"
        "</tr>"
    )


def render(snapshot: Snapshot) -> str:
    """The overview's table, its rows distilled by `overview.overview` and its readiness
    indicator read from the repository itself, with the count the overview needs."""
    repositories = {repo.name: repo for repo in snapshot.repositories}
    rows = sorted(overview(snapshot), key=lambda r: r.name)
    head = "".join(f"<th>{cells.escape(name)}</th>" for name in COLUMNS)
    body = "".join(line(row, cells.readiness_cell(repositories[row.name], with_count=True)) for row in rows)
    return f'<table class="sheet"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'
