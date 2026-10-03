# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Serve one scenario on a local port, for a person to look at and to measure.

    uv run python -m tests.page_preview live-like
    uv run python -m tests.page_preview stress --port 35851

It installs the page exactly as `__main__` does, with the two gathers answering
from `tests/page_scenarios.py` instead of from GitHub, and it binds the loopback
address alone: nothing here reaches a network, and no token is set, so the page
shows the token's expiry only where the scenario carries one.

The intervals are the ruled ones, not the tests' shortened ones, so that what is
served behaves as the service does; a scenario is gathered afresh on every
Refresh and keeps the time it was first built, which is how an age advancing on
the chrome can be watched.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from hazel_tracking.app import install, run
from hazel_tracking.config import Config
from hazel_tracking.model import PullRequestsSnapshot, Snapshot
from tests import page_scenarios as scenarios

LOOPBACK = "127.0.0.1"
DEFAULT_PORT = 35851

type Pair = tuple[Snapshot, PullRequestsSnapshot]

SCENARIOS: dict[str, Callable[[datetime], Pair]] = {
    "live-like": lambda at: (scenarios.live_like(at), scenarios.open_pull_requests(at)),
    "stress": lambda at: (scenarios.stress(at), scenarios.open_pull_requests(at)),
    "failures": lambda at: (scenarios.failures(at), scenarios.pull_requests_not_gathered(at)),
    "timed-out": lambda at: (scenarios.timed_out(at), scenarios.pull_requests_not_gathered(at)),
    "no-repositories": lambda at: (scenarios.no_repositories(at), scenarios.open_pull_requests(at)),
    "expiring-token": lambda at: (scenarios.expiring_soon(at), scenarios.open_pull_requests(at)),
}


def parse(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", choices=sorted(SCENARIOS), help="which scenario to serve")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="the port on the loopback address")
    parser.add_argument("--time-zone", default="Europe/London", help="the lab's zone, as TZ gives it")
    return parser.parse_args(argv)


def serve(scenario: str, port: int = DEFAULT_PORT, time_zone: str = "Europe/London") -> None:
    cfg = replace(
        Config(),
        host=LOOPBACK,
        port=port,
        github_token=None,
        time_zone=ZoneInfo(time_zone),
    )
    snapshot, pull_requests = SCENARIOS[scenario](datetime.now(UTC))

    async def gather() -> Snapshot:
        return snapshot

    async def gather_pull_requests() -> PullRequestsSnapshot:
        return pull_requests

    install(cfg, gather=gather, gather_pull_requests=gather_pull_requests)
    run(cfg)


def main() -> None:
    arguments = parse()
    serve(arguments.scenario, arguments.port, arguments.time_zone)


if __name__ in {"__main__", "__mp_main__"}:
    main()
