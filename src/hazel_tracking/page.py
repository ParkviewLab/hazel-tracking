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

Every gather shows a spinner over a dimmed ground. A full gather, whatever
started it, shows the large spinner over the whole page; a gather of the open
pull requests alone shows a spinner filling the pull-requests tab's frame, so
that the chrome and the tabs stay usable and the reader can leave for another
view. The tab's scrim takes no pointer, so the tab's own controls stay within
reach during the watch's gathers.

Every timer belongs to the browser's connection: the automatic full gather, the
watch and the clock that ages the data all stop when the page is closed, and no
two browsers share one. A gather that was running when the browser went is
dropped on its return, and so is one whose result a newer gather has overtaken.
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
PULL_REQUESTS = "Pull Requests"
REFRESH_ALL = "Refresh All"
REFRESH_PULL_REQUESTS = "Refresh PRs"

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
        self._full_busy = 0
        self._tab_busy = 0
        # Which full gather is the newest: a result from an older one is dropped, so that two
        # gathers cannot overwrite one another and the retries cannot skip a step.
        self._generation = 0

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
            self._gather_open_pull_requests,
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
        with ui.row().classes("chrome w-full items-center no-wrap gap-4").style("padding:18px 24px 16px"):
            ui.html(theme.logo_svg(), sanitize=False).classes("shrink-0").mark("brand-logo")
            # The name and the version, centred together between the logo and the data's age.
            ui.space()
            with ui.row().classes("shrink-0 items-baseline no-wrap").style("gap:.6em"):
                ui.html(theme.brand_name_html(DISPLAY_NAME), sanitize=False).style(
                    f"color:{theme.TEXT}"
                ).mark("chrome-name")
                ui.html(theme.brand_version_html(VERSION), sanitize=False).mark("chrome-version")
            ui.space()
            self._age = ui.label(GATHERING).classes("sub shrink-0").mark("chrome-age")
            self._refresh = (
                ui.button(REFRESH_ALL, on_click=self._refreshed)
                .props("dense no-caps outline color=accent")
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
            with ui.tab_panel(self._pull_requests_tab).classes("framed"):
                self._pull_requests_panel()

    def _pull_requests_panel(self) -> None:
        """The tab's own frame: what it shows, and the spinner that fills the frame while the open
        pull requests are gathered, the frame dimmed beneath it and the chrome untouched."""
        with ui.column().classes("framed-scroll w-full no-wrap gap-0"):
            with ui.row().classes("w-full items-center no-wrap gap-3").style("padding:6px 10px"):
                self._pull_requests_time = ui.label(GATHERING).classes("sub").mark("pull-requests-time")
                self._watch_result = ui.html("", sanitize=False).classes("sub").mark("watch-result")
                ui.space()
                self._pull_requests_refresh = (
                    ui.button(REFRESH_PULL_REQUESTS, on_click=self._refreshed_pull_requests)
                    .props("dense no-caps outline color=accent")
                    .mark("pull-requests-refresh")
                )
                self._watch_button = (
                    ui.button(pull_requests_view.WATCH, on_click=self._watch_pressed)
                    .props("dense no-caps outline color=accent")
                    .mark("watch")
                )
            container = ui.column().classes("w-full no-wrap gap-0")
        self._tab_spinner = ui.element("div").classes(
            "busy scrim absolute inset-0 z-40 flex items-center justify-center"
        )
        self._tab_spinner.mark("tab-spinner")
        with self._tab_spinner:
            ui.spinner("box", size="6em", color=theme.TEAL)
        self._tab_spinner.set_visibility(False)
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
                .props("flat dense round size=sm color=accent")
                .mark("status-icon")
            )
            self._icon.set_visibility(False)

    def _overlay(self) -> None:
        """The large spinner, over the whole page, for every full gather."""
        self._spinner = ui.element("div").classes("busy fixed inset-0 z-50 flex items-center justify-center")
        self._spinner.mark("spinner")
        with self._spinner:
            ui.spinner("box", size="9em", color=theme.TEAL)
        # The page is drawn with the spinner already over it, since the gathers its opening runs
        # begin as soon as the browser has connected and it is covered until they return.

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

    def _gone(self) -> bool:
        """Whether the browser has gone, so that nothing is to be drawn or timed for it."""
        return self._root.is_deleted

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
        self._detail.set_content(
            detail_view.render(self._snapshot, self._snapshot.began_at, self._cfg.time_zone)
        )
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
                also=self._tab_problems(),
            )
        )
        problems = self._problems()
        self._icon.set_visibility(bool(problems))
        self._dialog_body.set_content(status_bar.dialog_html(problems))

    def _tab_problems(self) -> tuple[Problem, ...]:
        return self._pull_requests.problems if self._pull_requests is not None else ()

    def _problems(self) -> tuple[Problem, ...]:
        """Every problem the page knows of: the full gather's, and the open pull requests' own."""
        full = self._snapshot.problems if self._snapshot is not None else ()
        return full + self._tab_problems()

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

    def _set_full_busy(self, busy: bool) -> None:
        """The large spinner over the whole page, for a full gather however it was started."""
        self._full_busy = max(self._full_busy + (1 if busy else -1), 0)
        if self._gone():
            return
        self._spinner.set_visibility(self._full_busy > 0)
        self._refresh.set_enabled(self._full_busy == 0)

    def _set_tab_busy(self, busy: bool) -> None:
        """The spinner filling the pull-requests tab's frame, for a gather of those alone."""
        self._tab_busy = max(self._tab_busy + (1 if busy else -1), 0)
        if self._gone():
            return
        self._tab_spinner.set_visibility(self._tab_busy > 0)

    async def _full_gather(self) -> None:
        """One full gather, with the automatic one cancelled around it and set again after it.

        Its result is applied only where it is still the newest and the browser is still there:
        a Refresh that overtakes an automatic gather leaves that one with nothing to say.
        """
        self._schedule.cancel()
        self._generation += 1
        mine = self._generation
        began_at = self._now()
        started = time.monotonic()
        self._set_full_busy(True)
        try:
            try:
                snapshot = await self._gather()
                failed = False
            # A gather that raised is read as one that did not complete; no traceback reaches the page.
            except Exception as error:
                snapshot = failed_snapshot(began_at, time.monotonic() - started, error)
                failed = True
        finally:
            self._set_full_busy(False)
        if self._gone() or mine != self._generation:
            return
        self._snapshot = snapshot
        self._failed = failed
        self._schedule.set_after(
            wholly_successful=status_bar.wholly_successful(snapshot),
            elapsed_seconds=time.monotonic() - started,
        )
        self._show_snapshot()
        self._show_age()

    async def _gather_open_pull_requests(self) -> PullRequestsSnapshot:
        """One gather of the open pull requests alone, under the tab's own spinner.

        It never raises: a gather that failed is read as one that did not complete, so that the
        watch's tick sees it as the tab's Refresh does and the tab says what went wrong.
        """
        began_at = self._now()
        started = time.monotonic()
        self._set_tab_busy(True)
        try:
            return await self._gather_pull_requests()
        except Exception as error:
            return failed_pull_requests(began_at, time.monotonic() - started, error)
        finally:
            self._set_tab_busy(False)

    async def _pull_requests_gather(self) -> None:
        snapshot = await self._gather_open_pull_requests()
        if self._gone():
            return
        self._show_pull_requests(snapshot)

    async def _both(self) -> None:
        """Opening the page and the chrome's Refresh run both gathers, each under its own spinner."""
        await asyncio.gather(self._full_gather(), self._pull_requests_gather())

    async def _opened(self) -> None:
        await self._both()

    async def _refreshed(self) -> None:
        ui.page_title(DISPLAY_NAME)
        self._watch_result.set_content("")
        await self._both()

    async def _automatic_gather(self) -> None:
        """The cycle's own gather: the full gather alone, under the large spinner as any other."""
        await self._full_gather()

    async def _refreshed_pull_requests(self) -> None:
        """The tab's own Refresh gathers the open pull requests alone. It does not stop a watch,
        which stops only by the rules that govern it; the watch keeps comparing against the set
        it was started on."""
        await self._pull_requests_gather()

    # The watch.

    def _watch_pressed(self) -> None:
        """The tab's own Watch, pressed again, cancels the watch it started; pressed while a
        line's Watch is running it takes the watch to the whole set, which is what asking for
        the whole set means."""
        if self._watch.watching and self._watch.target is None:
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
        if stop.on_a_change and stop.title_mark:
            ui.page_title(f"{stop.title_mark} \u00b7 {DISPLAY_NAME}")
        shown = stop.detail if stop.on_a_change else str(stop.reason)
        self._watch_result.set_content(cells.span(cells.escape(shown or str(stop.reason)), "sub"))
        self._show_watch()

    def _tab_changed(self) -> None:
        """Switching tabs gathers nothing; leaving the pull requests stops their watch, whose own
        stopping draws the list afresh."""
        if self._current_tab() != PULL_REQUESTS and self._watch.watching:
            self._watch.cancel(reason=StopReason.LEFT_TAB)

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
