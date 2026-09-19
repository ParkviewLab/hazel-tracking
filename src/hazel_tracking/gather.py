# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""The gathering: one snapshot of every repository of the organisation, from GitHub.

`gather` is the one entry point, and the only code that names GitHub's calls; it
reads through the client it is given and returns the contract of `model.py`,
per docs/what-it-shows.md. In this version it is a stub that raises, and the
page does not call it.
"""

from __future__ import annotations

import httpx

from hazel_tracking.config import Config
from hazel_tracking.model import Snapshot


async def gather(cfg: Config, client: httpx.AsyncClient) -> Snapshot:
    """Gather one snapshot of the organisation `cfg.github_org` through `client`, within `cfg.wait_seconds`."""
    raise NotImplementedError("the gathering is not part of this version")
