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
from zoneinfo import ZoneInfo

import pytest

from hazel_tracking.config import Config
from hazel_tracking.model import PullRequestsSnapshot, Snapshot

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

    def reset(self) -> None:
        self.snapshots = []
        self.pull_requests = []
        self.full_gathers = 0
        self.pull_request_gathers = 0
        self.full_raises = None
        self.pull_requests_raise = None

    def load(
        self,
        snapshot: Snapshot | None = None,
        pull_requests: PullRequestsSnapshot | Iterable[PullRequestsSnapshot] | None = None,
    ) -> Plan:
        """What the gathers are to answer: one snapshot, and one or a sequence of the other."""
        if snapshot is not None:
            self.snapshots = [snapshot]
        if pull_requests is not None:
            self.pull_requests = (
                [pull_requests] if isinstance(pull_requests, PullRequestsSnapshot) else list(pull_requests)
            )
        return self

    def then(self, snapshot: Snapshot) -> Plan:
        """What the next full gather is to answer, after those already loaded."""
        self.snapshots.append(snapshot)
        return self

    async def gather(self) -> Snapshot:
        self.full_gathers += 1
        if self.full_raises is not None:
            raise self.full_raises
        assert self.snapshots, "the plan holds no snapshot for the full gather"
        return self.snapshots.pop(0) if len(self.snapshots) > 1 else self.snapshots[0]

    async def gather_pull_requests(self) -> PullRequestsSnapshot:
        self.pull_request_gathers += 1
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
