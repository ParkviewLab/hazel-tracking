# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""The gathering, from GitHub: the full snapshot of every repository of the organisation,
and the open pull requests alone.

`gather` and `gather_pull_requests` are the two entry points the page awaits; each
reads through the client it is given and returns the contract of `model.py`, per
docs/what-it-shows.md. The calls themselves, their words and the readings they
follow are in `hazel_tracking.github`, which is the only code that names GitHub's
interfaces; what is here is what both gathers share: the wait that bounds them
(D7), the assembly of the snapshot from what arrived, and the one problem a gather
not complete within the wait carries, naming each call still outstanding (R11).

Neither gather raises for a source that fails: a call that fails costs the facts it
feeds and no others, which the snapshot carries as not gathered beside a problem
naming them, and the rest of the page stands (R7, axiom 8). The token travels in
the client's `Authorization` header alone and appears in no problem, no log record
and no exception message.
"""

from __future__ import annotations

import time
from datetime import datetime

import httpx

from hazel_tracking.config import Config
from hazel_tracking.github import full, problems, pull_requests
from hazel_tracking.github.calls import Reader
from hazel_tracking.github.collecting import within_the_wait
from hazel_tracking.model import NOT_GATHERED, Gathered, PullRequestsSnapshot, Snapshot

# The sources this version asks, in the page's words (northstar: later phases add others).
SOURCES = ("GitHub",)


async def gather(cfg: Config, client: httpx.AsyncClient) -> Snapshot:
    """Gather one snapshot of the organisation `cfg.github_org` through `client`, within `cfg.wait_seconds`."""
    began_at = datetime.now(cfg.time_zone)
    started = time.monotonic()
    reader = Reader(cfg=cfg, client=client)
    state = full.FullState()
    completed = await within_the_wait(cfg, full.collect(cfg, reader, state))
    duration = time.monotonic() - started
    found = list(state.problems)
    if not completed:
        found.append(problems.timed_out(cfg.wait_seconds, reader.outstanding))
    return Snapshot(
        began_at=began_at,
        duration_seconds=duration,
        completed=completed,
        sources=SOURCES,
        repositories=state.to_model(),
        archived=state.archived,
        problems=tuple(found),
        rate_limit=reader.rate_limit,
        credential_expires_at=reader.credential_expires_at,
    )


async def gather_pull_requests(cfg: Config, client: httpx.AsyncClient) -> PullRequestsSnapshot:
    """Gather the open pull requests of `cfg.github_org` alone through `client`, within `cfg.wait_seconds`."""
    began_at = datetime.now(cfg.time_zone)
    started = time.monotonic()
    reader = Reader(cfg=cfg, client=client)
    state = pull_requests.PullRequestsState()
    completed = await within_the_wait(cfg, pull_requests.collect(cfg, reader, state))
    duration = time.monotonic() - started
    found = list(state.problems)
    if not completed:
        found.append(problems.timed_out(cfg.wait_seconds, reader.outstanding))
    return PullRequestsSnapshot(
        began_at=began_at,
        duration_seconds=duration,
        completed=completed,
        # The list the search answered stands even where the gather was cut short afterwards: R11
        # shows the facts that did arrive, and what did not is greyed beside them.
        pull_requests=NOT_GATHERED if state.pull_requests is None else Gathered(state.to_model()),
        problems=tuple(found),
        rate_limit=reader.rate_limit,
    )
