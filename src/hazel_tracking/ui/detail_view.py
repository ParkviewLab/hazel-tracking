# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""The detail: one table, a row per repository in name order, as wide as the window.

The ten columns of docs/what-it-shows.md, "The detail", in that order. The table
is rendered as markup rather than built from elements: a row holds ten cells and
several of them hold a line apiece for every branch and every pull request, so
one string per gather is both the cheapest thing to draw and the easiest to read
in a test. It scrolls vertically within its tab; nothing is truncated or hidden.

Two of the columns, the unreleased work and the release indicator, hold the longest
words and may wrap, so that a browser narrows them before the table grows wider than
the window; the rest stand on one line.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from hazel_tracking.model import Repository, Snapshot
from hazel_tracking.ui import cells

COLUMNS = (
    "Repository",
    "Last push",
    "Issues",
    "Tag / Release",
    "Dev",
    "Unreleased",
    "Release",
    "Checks",
    "Branches",
    "Pull requests",
)


def row(repo: Repository, now: datetime, zone: ZoneInfo) -> str:
    return (
        "<tr>"
        f'<td class="repo">{cells.repository_cell(repo.name)}</td>'
        f"<td>{cells.last_push_cell(repo, now, zone)}</td>"
        f"<td>{cells.issues_cell(repo)}</td>"
        f"<td>{cells.tag_release_cell(repo)}</td>"
        f"<td>{cells.dev_cell(repo)}</td>"
        f'<td class="wrap">{cells.unreleased_cell(repo)}</td>'
        f'<td class="wrap">{cells.readiness_cell(repo)}</td>'
        f"<td>{cells.checks_cell(repo)}</td>"
        f"<td>{cells.branches_cell(repo)}</td>"
        f"<td>{cells.pull_requests_cell(repo)}</td>"
        "</tr>"
    )


def render(snapshot: Snapshot, now: datetime, zone: ZoneInfo) -> str:
    """The whole table. With no repository gathered it is the columns and no rows (R11)."""
    head = "".join(f"<th>{cells.escape(name)}</th>" for name in COLUMNS)
    body = "".join(row(repo, now, zone) for repo in sorted(snapshot.repositories, key=lambda r: r.name))
    return f'<table class="sheet"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'
