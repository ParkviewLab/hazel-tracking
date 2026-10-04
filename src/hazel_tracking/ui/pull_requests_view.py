# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""The pull-requests tab's list: every open pull request across the organisation.

Each line carries its repository, its number and title linked to it, its status
as R4 reads it, and a Watch of its own, which waits for that pull request and
stops also when its status changes (docs/what-it-shows.md, "The pull requests").

This view is built from elements rather than from markup, because every line
carries a button; the detail and the overview, which carry none, are markup. It
is the same table all the same, with the same stylesheet, so that its columns
align down the list as the detail's do and the Watch of every line stands in one
column at the right: the cells are built as elements, and a fragment of markup
and a button stand side by side within them. The table is as wide as the tab and
its columns are fixed, so that a long title wraps within its own column rather
than pushing the ones beside it. It is rebuilt in place on every gather, the
watch's included.

Every fragment is put on the page unsanitised, every value in it having been
escaped in `cells`, because the sanitiser drops the `target` of a link: with it,
following a pull request would replace the Dashboard in the browser rather than
opening beside it, and would end a watch.
"""

from __future__ import annotations

from collections.abc import Callable

from nicegui import ui

from hazel_tracking.model import Gathered, OpenPullRequest, PullRequestsSnapshot
from hazel_tracking.ui import cells, text

type Key = tuple[str, int]

COLUMNS = (("Repository", "repo"), ("Pull request", "title"), ("Status", "status"), ("", "watch"))
TABLE_CLASSES = "sheet prlist"
WATCH = "Watch"
WATCHING = "Watching"
GATHERING = "Gathering from GitHub…"
NONE_OPEN = "No pull request is open."
NOT_GATHERED = "The open pull requests could not be gathered"


def key_of(open_pull_request: OpenPullRequest) -> Key:
    return (open_pull_request.repository, open_pull_request.pull_request.number)


def title_html(open_pull_request: OpenPullRequest) -> str:
    """The number and the title, linked to the pull request."""
    number = open_pull_request.pull_request.number
    return cells.link(
        open_pull_request.pull_request.url, f"#{number} {cells.escape(open_pull_request.title)}"
    )


def status_html(open_pull_request: OpenPullRequest) -> str:
    status = open_pull_request.pull_request.status
    if not isinstance(status, Gathered):
        return cells.ungathered_value()
    return cells.state(text.PULL_REQUEST_STYLE[status.value], str(status.value))


class PullRequestsList:
    """The list inside the tab, rebuilt in place on every gather of the open pull requests."""

    def __init__(self, container: ui.element, on_watch: Callable[[Key], None]) -> None:
        self._container = container
        self._on_watch = on_watch

    def show(self, snapshot: PullRequestsSnapshot | None, *, watching: Key | None = None) -> None:
        self._container.clear()
        with self._container:
            if snapshot is None:
                ui.label(GATHERING).classes("sub").style("padding:8px 10px")
                return
            if not isinstance(snapshot.pull_requests, Gathered):
                ui.html(cells.ungathered(NOT_GATHERED), sanitize=False).style("padding:8px 10px").mark(
                    "pull-requests-empty"
                )
                return
            if not snapshot.pull_requests.value:
                ui.label(NONE_OPEN).classes("sub").style("padding:8px 10px").mark("pull-requests-empty")
                return
            with ui.element("table").classes(TABLE_CLASSES).mark("pull-requests-table"):
                self._header()
                with ui.element("tbody"):
                    for open_pull_request in snapshot.pull_requests.value:
                        self._row(open_pull_request, watching)

    def _header(self) -> None:
        with ui.element("thead"), ui.element("tr"):
            for name, column in COLUMNS:
                with ui.element("th").classes(f"prcol-{column}"):
                    ui.html(cells.escape(name), sanitize=False)

    def _row(self, open_pull_request: OpenPullRequest, watching: Key | None) -> None:
        key = key_of(open_pull_request)
        with ui.element("tr"):
            with ui.element("td").classes("prcol-repo"):
                ui.html(cells.escape(cells.short_name(open_pull_request.repository)), sanitize=False).classes(
                    "sub"
                )
            with ui.element("td").classes("prcol-title"):
                ui.html(title_html(open_pull_request), sanitize=False)
            with ui.element("td").classes("prcol-status"):
                ui.html(status_html(open_pull_request), sanitize=False)
            with ui.element("td").classes("prcol-watch"):
                ui.button(
                    WATCHING if watching == key else WATCH,
                    on_click=lambda _=None, chosen=key: self._on_watch(chosen),
                ).props("flat dense no-caps color=accent").mark(f"watch-{key[0]}-{key[1]}")
