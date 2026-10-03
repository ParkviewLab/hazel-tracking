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
place when the gather returns, so it does not await a gather before it returns
and keeps NiceGUI's default `response_timeout`. In this version the page shows
the display name alone and calls neither gather.
"""

from __future__ import annotations

from nicegui import ui

from hazel_tracking.config import DISPLAY_NAME, Config
from hazel_tracking.model import Gather, GatherPullRequests

PATH = "/"


def register(cfg: Config, gather: Gather, gather_pull_requests: GatherPullRequests) -> None:
    """Register the page at `/` on NiceGUI's app."""

    @ui.page(PATH, title=DISPLAY_NAME)
    async def dashboard() -> None:
        ui.label(DISPLAY_NAME)
