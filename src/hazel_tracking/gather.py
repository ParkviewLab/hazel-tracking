# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""The gathering, from GitHub: the full snapshot of every repository of the organisation,
and the open pull requests alone.

`gather` and `gather_pull_requests` are the two entry points, and the only code
that names GitHub's calls; each reads through the client it is given and returns
the contract of `model.py`, per docs/what-it-shows.md. In this version both are
stubs that raise, and the page does not call them.
"""

from __future__ import annotations

import httpx

from hazel_tracking.config import Config
from hazel_tracking.model import PullRequestsSnapshot, Snapshot


async def gather(cfg: Config, client: httpx.AsyncClient) -> Snapshot:
    """Gather one snapshot of the organisation `cfg.github_org` through `client`, within `cfg.wait_seconds`."""
    raise NotImplementedError("the gathering is not part of this version")


async def gather_pull_requests(cfg: Config, client: httpx.AsyncClient) -> PullRequestsSnapshot:
    """Gather the open pull requests of `cfg.github_org` alone through `client`, within `cfg.wait_seconds`."""
    raise NotImplementedError("the gathering is not part of this version")
