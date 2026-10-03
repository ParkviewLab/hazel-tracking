# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""The page at `/` (docs/what-it-shows.md): the chrome above three tabs, the overview,
the detail and the pull requests.

`register()` binds the page to its path with `ui.page`, so that it is built
afresh inside that function for every browser that connects, and nothing per
browser lives at module level. It takes everything it needs from `cfg` and the
snapshots `gather` and `gather_pull_requests` return, and nothing else.

The page is drawn first, with its chrome and the busy spinner, and filled in
place when the gathers return, so it does not await a gather before it returns
and keeps NiceGUI's default `response_timeout`. Opening the page and the chrome's
Refresh run both gathers; the pull-requests tab's own Refresh and its Watch run
the gather of the open pull requests alone; switching tabs gathers nothing.

Every timer belongs to the browser's connection: the automatic full gather
(`ui.schedule`), the watch (`ui.watch`) and the clock that ages the data all stop
when the page is closed, and no two browsers share one.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime

from nicegui import ui

from hazel_tracking.config import DISPLAY_NAME, VERSION, Config
from hazel_tracking.model import (
    NOT_GATHERED,
    Gather,
    GatherPullRequests,
    Problem,
    ProblemDetail,
    PullRequestsSnapshot,
    Snapshot,
)
from hazel_tracking.ui import (
    cells,
    detail_view,
    overview_view,
    pull_requests_view,
    status_bar,
    text,
    theme,
)
from hazel_tracking.ui.schedule import GatherSchedule
from hazel_tracking.ui.watch import Stop, StopReason, Watch

PATH = "/"

OVERVIEW = "Overview"
DETAIL = "Detail"
PULL_REQUESTS = "Pull requests"
REFRESH = "Refresh"

GATHERING = "gathering…"
AGE_PREFIX = "gathered"
PROBLEM_TITLE = "What could not be gathered"
CLOSE = "Close"

# What the page says when a gather raised before it finished; no traceback and no value reaches
# the page, and the credential is named in general terms alone (axiom 6).
GATHER_FAILED = "the gather failed"
GATHER_FAILED_WHY = "the gathering stopped with an error before it finished"
PULL_REQUESTS_FAILED = "the open pull requests could not be gathered"


def failed_snapshot(began_at: datetime, duration_seconds: float, error: Exception) -> Snapshot:
    """A full gather that raised, read as a gather that did not complete (D7, R11)."""
    detail = ProblemDetail(
        call="the full gather", status=None, message=f"the error was a {type(error).__name__}"
    )
    return Snapshot(
        began_at=began_at,
        duration_seconds=duration_seconds,
        completed=False,
        sources=("GitHub",),
        repositories=(),
        archived=None,
        problems=(Problem(what=GATHER_FAILED, why=GATHER_FAILED_WHY, details=(detail,)),),
        rate_limit=None,
        credential_expires_at=None,
    )


def failed_pull_requests(
    began_at: datetime, duration_seconds: float, error: Exception
) -> PullRequestsSnapshot:
    """A gather of the open pull requests that raised, read as one that did not complete."""
    detail = ProblemDetail(
        call="the open pull requests", status=None, message=f"the error was a {type(error).__name__}"
    )
    return PullRequestsSnapshot(
        began_at=began_at,
        duration_seconds=duration_seconds,
        completed=False,
        pull_requests=NOT_GATHERED,
        problems=(Problem(what=PULL_REQUESTS_FAILED, why=GATHER_FAILED_WHY, details=(detail,)),),
        rate_limit=None,
    )


class Dashboard:
    """One browser's page: its elements, its two snapshots, its schedule and its watch."""

    def __init__(self, cfg: Config, gather: Gather, gather_pull_requests: GatherPullRequests) -> None:
        self._cfg = cfg
        self._gather = gather
        self._gather_pull_requests = gather_pull_requests
        self._snapshot: Snapshot | None = None
        self._pull_requests: PullRequestsSnapshot | None = None
        self._failed = False
        self._busy = 0
        self._stop: Stop | None = None

    # The page, drawn before anything is gathered.

    def build(self) -> None:
        ui.add_head_html(theme.head_html())
        ui.dark_mode().enable()
        ui.colors(primary=theme.TEAL_DEEP, secondary=theme.SAGE, accent=theme.TEAL)
        ui.page_title(DISPLAY_NAME)
        with ui.column().classes("w-full no-wrap gap-0").style("height:100vh") as root:
            self._root = root
            self._chrome()
            self._tabs()
            self._status()
        self._overlay()
        self._dialog_element()
        self._schedule = GatherSchedule(self._cfg, self._automatic_gather, self._root)
        self._watch = Watch(
            self._cfg,
            self._gather_pull_requests,
            self._root,
            on_gather=self._show_pull_requests,
            on_stop=self._watch_stopped,
        )
        # The tabs are listened to only once the watch exists, since leaving a tab stops it.
        self._tab_bar.on_value_change(self._tab_changed)
        with self._root:
            ui.timer(1.0, self._show_age)
            ui.timer(0, self._opened, once=True)

    def _chrome(self) -> None:
        with ui.row().classes("chrome w-full items-center no-wrap gap-4").style("padding:6px 14px"):
            ui.html(theme.logo_svg(), sanitize=False).classes("shrink-0").mark("brand-logo")
            ui.html(theme.brand_label_html(DISPLAY_NAME, VERSION), sanitize=False).classes(
                "shrink-0 text-white"
            ).mark("chrome-name")
            ui.space()
            self._age = ui.label(GATHERING).classes("sub shrink-0").mark("chrome-age")
            self._refresh = (
                ui.button(REFRESH, on_click=self._refreshed)
                .props("dense no-caps outline color=white")
                .mark("refresh")
            )

    def _tabs(self) -> None:
        with ui.tabs().props("dense no-caps align=left").classes("w-full tabbar") as tabs:
            self._overview_tab = ui.tab(OVERVIEW)
            self._detail_tab = ui.tab(DETAIL)
            self._pull_requests_tab = ui.tab(PULL_REQUESTS)
        self._tab_bar = tabs
        tabs.set_value(OVERVIEW)
        with ui.tab_panels(tabs, value=self._overview_tab).classes("w-full flex-1 min-h-0"):
            with ui.tab_panel(self._overview_tab):
                self._overview = ui.html("", sanitize=False).classes("w-full").mark("overview")
            with ui.tab_panel(self._detail_tab):
                self._detail = ui.html("", sanitize=False).classes("w-full").mark("detail")
            with ui.tab_panel(self._pull_requests_tab):
                self._pull_requests_panel()

    def _pull_requests_panel(self) -> None:
        with ui.column().classes("w-full no-wrap gap-0"):
            with ui.row().classes("w-full items-center no-wrap gap-3").style("padding:6px 10px"):
                self._pull_requests_time = ui.label(GATHERING).classes("sub").mark("pull-requests-time")
                self._watch_result = ui.html("", sanitize=False).classes("sub").mark("watch-result")
                ui.space()
                self._pull_requests_refresh = (
                    ui.button(REFRESH, on_click=self._refreshed_pull_requests)
                    .props("dense no-caps outline")
                    .mark("pull-requests-refresh")
                )
                self._watch_button = (
                    ui.button(pull_requests_view.WATCH, on_click=self._watch_pressed)
                    .props("dense no-caps outline")
                    .mark("watch")
                )
            container = ui.column().classes("w-full no-wrap gap-0")
        self._list = pull_requests_view.PullRequestsList(container, self._watch_row)

    def _status(self) -> None:
        with (
            ui.row()
            .classes("w-full items-center no-wrap gap-2 statusbar")
            .style("padding:4px 12px; border-top:1px solid " + theme.LINE)
        ):
            self._sentence = (
                ui.html(status_bar.GATHERING, sanitize=False).classes("statusbar").mark("status-sentence")
            )
            self._icon = (
                ui.button(icon="info", on_click=self._open_dialog)
                .props("flat dense round size=sm")
                .mark("status-icon")
            )
            self._icon.set_visibility(False)

    def _overlay(self) -> None:
        self._spinner = ui.element("div").classes("busy fixed inset-0 z-50 flex items-center justify-center")
        self._spinner.mark("spinner")
        with self._spinner:
            ui.spinner(size="6em", color=theme.TEAL)
        self._spinner.set_visibility(False)

    def _dialog_element(self) -> None:
        with (
            ui.dialog() as dialog,
            ui.card().classes("gap-2").style(f"background:{theme.PANEL}; max-width:760px"),
        ):
            ui.label(PROBLEM_TITLE).classes("text-lg")
            self._dialog_body = ui.html("", sanitize=False).mark("status-dialog")
            with ui.row().classes("justify-end w-full"):
                ui.button(CLOSE, on_click=dialog.close).props("flat no-caps")
        self._dialog = dialog

    # What the elements show.

    def _now(self) -> datetime:
        return datetime.now(self._cfg.time_zone)

    def _show_age(self) -> None:
        if self._snapshot is None:
            self._age.set_text(GATHERING)
            return
        seconds = (self._now() - self._snapshot.began_at).total_seconds()
        self._age.set_text(f"{AGE_PREFIX} {text.age(seconds)} ago")

    def _show_snapshot(self) -> None:
        if self._snapshot is None:
            return
        self._overview.set_content(overview_view.render(self._snapshot))
        # The times in the table are reckoned from the gather, not from the clock: the facts are
        # what the source said at the moment the chrome names (axiom 2).
        self._detail.set_content(detail_view.render(self._snapshot, self._snapshot.began_at))
        self._show_status()

    def _show_status(self) -> None:
        # The sentence describes the gather, so what it reckons (the token's expiry) is reckoned
        # from the moment that gather began; the chrome alone says how long ago that was.
        reckoned_from = self._snapshot.began_at if self._snapshot is not None else self._now()
        self._sentence.set_content(
            status_bar.sentence(
                self._cfg,
                self._snapshot,
                reckoned_from,
                self._schedule.next_at,
                failed=self._failed,
            )
        )
        problems = self._problems()
        self._icon.set_visibility(bool(problems))
        self._dialog_body.set_content(status_bar.dialog_html(problems))

    def _problems(self) -> tuple[Problem, ...]:
        """Every problem the page knows of: the full gather's, and the open pull requests' own."""
        full = self._snapshot.problems if self._snapshot is not None else ()
        tab = self._pull_requests.problems if self._pull_requests is not None else ()
        return full + tab

    def _show_pull_requests(self, snapshot: PullRequestsSnapshot) -> None:
        self._pull_requests = snapshot
        self._pull_requests_time.set_text(
            f"gathered at {text.clock(snapshot.began_at, self._cfg.time_zone)} "
            f"in {text.duration(snapshot.duration_seconds)}"
        )
        self._list.show(snapshot, watching=self._watch.target)
        self._show_status()

    def _show_watch(self) -> None:
        self._watch_button.set_text(
            pull_requests_view.WATCHING if self._watch.watching else pull_requests_view.WATCH
        )
        self._list.show(self._pull_requests, watching=self._watch.target)

    # The gathers.

    def _set_busy(self, busy: bool) -> None:
        self._busy = max(self._busy + (1 if busy else -1), 0)
        self._spinner.set_visibility(self._busy > 0)
        self._refresh.set_enabled(self._busy == 0)
        self._pull_requests_refresh.set_enabled(self._busy == 0)

    async def _full_gather(self) -> None:
        """One full gather, with the automatic one cancelled around it and set again after it."""
        self._schedule.cancel()
        began_at = self._now()
        started = time.monotonic()
        try:
            snapshot = await self._gather()
            self._failed = False
        # A gather that raised is read as one that did not complete; no traceback reaches the page.
        except Exception as error:
            snapshot = failed_snapshot(began_at, time.monotonic() - started, error)
            self._failed = True
        self._snapshot = snapshot
        self._schedule.set_after(
            wholly_successful=status_bar.wholly_successful(snapshot) and not self._failed,
            elapsed_seconds=time.monotonic() - started,
        )
        self._show_snapshot()
        self._show_age()

    async def _pull_requests_gather(self) -> None:
        began_at = self._now()
        started = time.monotonic()
        try:
            snapshot = await self._gather_pull_requests()
        except Exception as error:
            snapshot = failed_pull_requests(began_at, time.monotonic() - started, error)
        self._show_pull_requests(snapshot)

    async def _both(self) -> None:
        """Opening the page and the chrome's Refresh run both gathers, under the busy spinner."""
        self._set_busy(True)
        try:
            await asyncio.gather(self._full_gather(), self._pull_requests_gather())
        finally:
            self._set_busy(False)

    async def _opened(self) -> None:
        await self._both()

    async def _refreshed(self) -> None:
        ui.page_title(DISPLAY_NAME)
        self._watch_result.set_content("")
        await self._both()

    async def _automatic_gather(self) -> None:
        """The 30-minute cycle's own gather: the full gather alone, and no spinner (D's ruling
        names the page's opening, Refresh and the tab's Refresh, and no other occasion)."""
        await self._full_gather()

    async def _refreshed_pull_requests(self) -> None:
        self._watch.cancel(quietly=True)
        self._show_watch()
        self._set_busy(True)
        try:
            await self._pull_requests_gather()
        finally:
            self._set_busy(False)

    # The watch.

    def _watch_pressed(self) -> None:
        if self._watch.watching:
            self._watch.cancel()
            return
        self._begin_watch(None)

    def _watch_row(self, key: tuple[str, int]) -> None:
        if self._watch.watching and self._watch.target == key:
            self._watch.cancel()
            return
        self._begin_watch(key)

    def _begin_watch(self, key: tuple[str, int] | None) -> None:
        if self._pull_requests is None:
            return
        ui.page_title(DISPLAY_NAME)
        self._watch_result.set_content("")
        self._watch.start(self._pull_requests, key)
        self._show_watch()

    def _watch_stopped(self, stop: Stop) -> None:
        self._stop = stop
        if stop.on_a_change and stop.title_mark:
            ui.page_title(f"{stop.title_mark} · {DISPLAY_NAME}")
        shown = stop.detail if stop.on_a_change else str(stop.reason)
        self._watch_result.set_content(cells.span(cells.escape(shown or str(stop.reason)), "sub"))
        self._show_watch()

    def _tab_changed(self) -> None:
        """Switching tabs gathers nothing; leaving the pull requests stops their watch."""
        if self._current_tab() != PULL_REQUESTS and self._watch.watching:
            self._watch.cancel(reason=StopReason.LEFT_TAB)
            self._show_watch()

    def _current_tab(self) -> str:
        """The tab the reader is on; the value is a `ui.tab` when the page set it and the tab's
        name when the browser did."""
        value = self._tab_bar.value
        return str(value.props["name"]) if isinstance(value, ui.tab) else str(value)

    def _open_dialog(self) -> None:
        self._dialog.open()


def register(cfg: Config, gather: Gather, gather_pull_requests: GatherPullRequests) -> None:
    """Register the page at `/` on NiceGUI's app."""

    @ui.page(PATH, title=DISPLAY_NAME)
    async def dashboard() -> None:
        Dashboard(cfg, gather, gather_pull_requests).build()
