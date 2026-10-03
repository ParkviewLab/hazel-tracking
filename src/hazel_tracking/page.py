# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""The page at `/` (docs/what-it-shows.md).

`register()` binds the page to its path with `ui.page`, so that it is built
afresh inside that function for every browser that connects, and nothing per
browser lives at module level. It takes everything it needs from `cfg` and the
snapshots `gather` returns, and nothing else. In this version the page shows
the display name alone and does not call `gather`.

The page awaits a gather before it returns, and a gather may run for the whole
configured wait, so NiceGUI's `response_timeout` (3 s by default) is set to the
wait and 5 s more.
"""

from __future__ import annotations

from nicegui import ui

from hazel_tracking.config import DISPLAY_NAME, Config
from hazel_tracking.model import Gather

PATH = "/"

# The margin past the wait within which the page is rendered and returned.
RESPONSE_MARGIN_SECONDS = 5.0


def response_timeout(cfg: Config) -> float:
    """How long NiceGUI allows the page to build: the configured wait, and a margin."""
    return cfg.wait_seconds + RESPONSE_MARGIN_SECONDS


def register(cfg: Config, gather: Gather) -> None:
    """Register the page at `/` on NiceGUI's app."""

    @ui.page(PATH, title=DISPLAY_NAME, response_timeout=response_timeout(cfg))
    async def dashboard() -> None:
        ui.label(DISPLAY_NAME)
