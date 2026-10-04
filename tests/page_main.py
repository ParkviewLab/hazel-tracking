# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""The NiceGUI main file of the page's tests (`main_file` in pyproject.toml), which
`nicegui.testing`'s `user` fixture executes afresh for each test that uses it.

It installs the application exactly as `__main__` does, under
`tests.page_fixtures.PAGE_CONFIG`, with the two gathers stubbed: each reads the
plan the test loaded (`tests.page_fixtures.PLAN`) when the page calls it, and
counts the call, so that a test can see which gathers a page load, a Refresh or
the watch ran. Nothing here reaches GitHub.
"""

from __future__ import annotations

from hazel_tracking.app import install, run
from hazel_tracking.model import PullRequestsSnapshot, Snapshot
from tests.page_fixtures import PAGE_CONFIG, PLAN


async def gather() -> Snapshot:
    return await PLAN.gather()


async def gather_pull_requests() -> PullRequestsSnapshot:
    return await PLAN.gather_pull_requests()


install(PAGE_CONFIG, gather=gather, gather_pull_requests=gather_pull_requests)
run(PAGE_CONFIG)
