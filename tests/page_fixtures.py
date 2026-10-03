# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""The page's pytest fixtures, loaded as a plugin from `tests/conftest.py`.

Their names carry the prefix `page_`. The plan is the one piece of state the
page's tests share with `tests/page_main.py`, which NiceGUI's `user` fixture
executes afresh for every test that uses it: the test loads the scenarios it
wants into the plan, and the stub gathers the main file installs read the plan
when the page calls them, which is inside the test itself. The configuration the
main file installs is fixed, `PAGE_CONFIG`, with every interval shortened so that
the schedule, the retries and the watch can be seen within a test.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from html.parser import HTMLParser
from zoneinfo import ZoneInfo

import pytest
from nicegui.elements.mixins.content_element import ContentElement
from nicegui.elements.mixins.text_element import TextElement
from nicegui.testing import User

from hazel_tracking.config import Config
from hazel_tracking.model import PullRequestsSnapshot, Snapshot
from tests import page_scenarios

# The same value as `conftest.py`'s `sentinel_token`; `test_page_secrets.py` holds the two together.
SENTINEL_TOKEN = "sentinel-github-token-3f9d0c"

# Every interval shortened, so that the 30-minute cycle, its retries and the watch's ten minutes
# can be seen in a test; the wait is not 15 s, so that the status bar is shown to name the
# configured wait rather than the default.
PAGE_CONFIG = Config(
    host="127.0.0.1",
    port=35999,
    github_token=SENTINEL_TOKEN,
    github_org="ParkviewLab",
    github_api_url="https://github.invalid",
    wait_seconds=7.0,
    time_zone=ZoneInfo("Europe/London"),
    gather_interval_seconds=1.0,
    retry_delays_seconds=(0.2, 0.4, 0.8, 1.6, 3.2),
    watch_interval_seconds=0.05,
    watch_limit_seconds=0.4,
)


@dataclass
class Plan:
    """What the stub gathers answer, and what they were asked.

    Each list is consumed in order and its last entry answers every further call,
    so a watch that gathers many times keeps seeing the state the test left it in.
    """

    snapshots: list[Snapshot] = field(default_factory=list)
    pull_requests: list[PullRequestsSnapshot] = field(default_factory=list)
    full_gathers: int = 0
    pull_request_gathers: int = 0
    full_raises: Exception | None = None
    pull_requests_raise: Exception | None = None
    hold: asyncio.Event | None = None
    hold_pull_requests: asyncio.Event | None = None
    # How long each gather takes, for a test that measures when the next one falls due.
    delay: float = 0.0

    def reset(self) -> None:
        self.snapshots = []
        self.pull_requests = []
        self.full_gathers = 0
        self.pull_request_gathers = 0
        self.full_raises = None
        self.pull_requests_raise = None
        self.hold = None
        self.hold_pull_requests = None
        self.delay = 0.0

    def block(self) -> asyncio.Event:
        """Hold the full gather until the event is set, so that a test can see the page before
        anything has been gathered."""
        self.hold = asyncio.Event()
        return self.hold

    def block_pull_requests(self) -> asyncio.Event:
        """Hold the gather of the open pull requests until the event is set."""
        self.hold_pull_requests = asyncio.Event()
        return self.hold_pull_requests

    def load(
        self,
        snapshot: Snapshot | Iterable[Snapshot] | None = None,
        pull_requests: PullRequestsSnapshot | Iterable[PullRequestsSnapshot] | None = None,
    ) -> Plan:
        """What the gathers are to answer: one snapshot each, or a sequence to be answered in turn."""
        if snapshot is not None:
            self.snapshots = [snapshot] if isinstance(snapshot, Snapshot) else list(snapshot)
        if pull_requests is not None:
            self.pull_requests = (
                [pull_requests] if isinstance(pull_requests, PullRequestsSnapshot) else list(pull_requests)
            )
        return self

    async def gather(self) -> Snapshot:
        self.full_gathers += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.hold is not None:
            await self.hold.wait()
        if self.full_raises is not None:
            raise self.full_raises
        assert self.snapshots, "the plan holds no snapshot for the full gather"
        return self.snapshots.pop(0) if len(self.snapshots) > 1 else self.snapshots[0]

    async def gather_pull_requests(self) -> PullRequestsSnapshot:
        self.pull_request_gathers += 1
        if self.hold_pull_requests is not None:
            await self.hold_pull_requests.wait()
        if self.pull_requests_raise is not None:
            raise self.pull_requests_raise
        assert self.pull_requests, "the plan holds no snapshot for the open pull requests"
        return self.pull_requests.pop(0) if len(self.pull_requests) > 1 else self.pull_requests[0]


PLAN = Plan()


@pytest.fixture
def page_plan() -> Plan:
    """The plan the page's stub gathers read, emptied for each test."""
    PLAN.reset()
    return PLAN


@pytest.fixture
def page_config() -> Config:
    """The configuration `tests/page_main.py` installs the page under."""
    return PAGE_CONFIG


async def until(condition: Callable[[], bool], *, timeout: float = 3.0, step: float = 0.02) -> None:
    """Wait for something the page does on a timer, and say so plainly when it never happens."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return
        await asyncio.sleep(step)
    raise AssertionError(f"the page did not reach the expected state within {timeout} s")


@dataclass(frozen=True)
class Cell:
    """One cell of a rendered table: its words, and whether it is greyed as not gathered (R7)."""

    text: str
    ungathered: bool

    def __contains__(self, needle: str) -> bool:
        return needle in self.text


class _Sheet(HTMLParser):
    """The rows of a rendered table, by the first cell of each."""

    def __init__(self) -> None:
        super().__init__()
        self.headers: list[str] = []
        self.rows: dict[str, list[Cell]] = {}
        self.quiet: set[str] = set()
        self._row: list[Cell] | None = None
        self._row_quiet = False
        self._cell: list[str] | None = None
        self._ungathered = False
        self._depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        classes = dict(attrs).get("class") or ""
        if tag == "tr":
            self._row = []
            self._row_quiet = "quiet" in classes
        elif tag in ("td", "th"):
            self._cell = []
            self._ungathered = False
            self._depth = 0
        elif self._cell is not None and "ungathered" in classes.split():
            self._ungathered = True

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th") and self._cell is not None:
            text = " ".join("".join(self._cell).split())
            if tag == "th":
                self.headers.append(text)
            elif self._row is not None:
                self._row.append(Cell(text=text, ungathered=self._ungathered))
            self._cell = None
        elif tag == "tr" and self._row:
            name = self._row[0].text
            self.rows[name] = self._row
            if self._row_quiet:
                self.quiet.add(name)
            self._row = None


def sheet(markup: str) -> _Sheet:
    """A rendered table read back as its headers and its rows, for a test to look into."""
    parser = _Sheet()
    parser.feed(markup)
    return parser


def content_of(user: User, marker: str) -> str:
    """The markup of the one element carrying `marker`."""
    (element,) = user.find(marker=marker).elements
    assert isinstance(element, ContentElement)
    return element.content


def sheet_of(user: User, marker: str) -> _Sheet:
    return sheet(content_of(user, marker))


def everything_shown(user: User) -> str:
    """Every word the page holds, the dialog's and the chrome's included, as one string."""
    pieces: list[str] = []
    for element in user.client.layout.descendants():
        if isinstance(element, ContentElement):
            pieces.append(str(element.content))
        if isinstance(element, TextElement):
            pieces.append(str(element.text))
        pieces.extend(str(value) for value in element.props.values())
    return "\n".join(pieces)


async def open_page(
    user: User,
    plan: Plan,
    snapshot: Snapshot | Iterable[Snapshot] | None = None,
    pull_requests: PullRequestsSnapshot | Iterable[PullRequestsSnapshot] | None = None,
) -> None:
    """Load the plan, open the page, and wait until both gathers have filled it."""
    plan.load(
        snapshot if snapshot is not None else page_scenarios.live_like(),
        pull_requests if pull_requests is not None else page_scenarios.open_pull_requests(),
    )
    await user.open("/")
    await until(lambda: content_of(user, "overview") != "" and plan.pull_request_gathers >= 1)
