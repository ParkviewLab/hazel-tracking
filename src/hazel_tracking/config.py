# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""The configuration, read from the environment, and the one place the version is derived.

A leaf module: it imports nothing from the package. The version has one source
of truth, `pyproject.toml`; `VERSION` is read from the installed package
metadata (the handbook's releases.md), never from a literal. Every variable is
documented in the README's Configuration table.

The token has no default and may be absent here: `__main__` refuses to start
without it, and a test builds a `Config` with a token of its own or none.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError, version
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

try:
    VERSION: str = version("hazel-tracking")
except PackageNotFoundError:  # a checkout that is not installed
    VERSION = "0.0.0+local"

NAME = "hazel-tracking"
DISPLAY_NAME = "ParkviewLab Engineering Dashboard"

# The variable that holds the GitHub token (docs/decisions.md, D10).
TOKEN_VARIABLE = "GITHUB_TOKEN_HAZEL_TRACKING"

# The bind address defaults to loopback in code; the image sets HOST=0.0.0.0.
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 35850  # D2
DEFAULT_GITHUB_ORG = "ParkviewLab"
DEFAULT_GITHUB_API_URL = "https://api.github.com"
DEFAULT_WAIT_SECONDS = 15.0  # D7
DEFAULT_TIME_ZONE = "UTC"

# Ruled, not settings (docs/what-it-shows.md, R8): the automatic gather runs every 30
# minutes; after a gather that is not wholly successful, retries follow 1, 2, 4, 8 and
# 16 minutes after each attempt, and then the 30-minute cycle resumes.
GATHER_INTERVAL_SECONDS = 1800.0
RETRY_DELAYS_SECONDS = (60.0, 120.0, 240.0, 480.0, 960.0)
# The pull-requests tab's watch: a gather of the open pull requests every 10 s, for
# at most 10 minutes (docs/what-it-shows.md, "The pull requests").
WATCH_INTERVAL_SECONDS = 10.0
WATCH_LIMIT_SECONDS = 600.0


@dataclass(frozen=True)
class Config:
    """The runtime configuration: built once at startup by `load_config`, or directly by a test."""

    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    github_token: str | None = field(default=None, repr=False)
    github_org: str = DEFAULT_GITHUB_ORG
    github_api_url: str = DEFAULT_GITHUB_API_URL
    wait_seconds: float = DEFAULT_WAIT_SECONDS
    time_zone: ZoneInfo = field(default_factory=lambda: ZoneInfo(DEFAULT_TIME_ZONE))
    gather_interval_seconds: float = GATHER_INTERVAL_SECONDS
    retry_delays_seconds: tuple[float, ...] = RETRY_DELAYS_SECONDS
    watch_interval_seconds: float = WATCH_INTERVAL_SECONDS
    watch_limit_seconds: float = WATCH_LIMIT_SECONDS

    def __post_init__(self) -> None:
        """Refuse, at start, a configuration the service could not run under."""
        if not 1 <= self.port <= 65535:
            raise ValueError(f"PORT must be between 1 and 65535, got {self.port}")
        if not _positive(self.wait_seconds):
            raise ValueError(f"HAZEL_TRACKING_WAIT_SECONDS must be greater than 0, got {self.wait_seconds}")
        intervals = (
            self.gather_interval_seconds,
            *self.retry_delays_seconds,
            self.watch_interval_seconds,
            self.watch_limit_seconds,
        )
        if not all(_positive(s) for s in intervals):
            raise ValueError(
                "the gather interval, the retry delays and the watch's intervals must be greater than 0"
            )


def _positive(seconds: float) -> bool:
    return math.isfinite(seconds) and seconds > 0


def _str_env(name: str, default: str) -> str:
    """A string variable; an empty value counts as unset."""
    raw = os.environ.get(name)
    return default if raw is None or raw.strip() == "" else raw.strip()


def _optional_env(name: str) -> str | None:
    """A string variable that may be absent; an empty value counts as unset."""
    raw = os.environ.get(name)
    return None if raw is None or raw.strip() == "" else raw.strip()


def _int_env(name: str, default: int) -> int:
    """An integer variable. A value that is not an integer is a configuration error and raises."""
    raw = _optional_env(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as e:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from e


def _seconds_env(name: str, default: float) -> float:
    """A number of seconds, whole or not. A value that is not a number raises."""
    raw = _optional_env(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError as e:
        raise ValueError(f"{name} must be a number of seconds, got {raw!r}") from e


def _zone_env(name: str, default: str) -> ZoneInfo:
    """An IANA time zone such as `America/Los_Angeles`. An unknown zone raises."""
    key = _str_env(name, default)
    try:
        return ZoneInfo(key)
    except (ZoneInfoNotFoundError, ValueError) as e:
        raise ValueError(f"{name} must name an IANA time zone, got {key!r}") from e


def load_config() -> Config:
    """The configuration from the environment; see the README's Configuration table."""
    return Config(
        host=_str_env("HOST", DEFAULT_HOST),
        port=_int_env("PORT", DEFAULT_PORT),
        github_token=_optional_env(TOKEN_VARIABLE),
        github_org=_str_env("HAZEL_TRACKING_GITHUB_ORG", DEFAULT_GITHUB_ORG),
        github_api_url=_str_env("HAZEL_TRACKING_GITHUB_API_URL", DEFAULT_GITHUB_API_URL).rstrip("/"),
        wait_seconds=_seconds_env("HAZEL_TRACKING_WAIT_SECONDS", DEFAULT_WAIT_SECONDS),
        time_zone=_zone_env("TZ", DEFAULT_TIME_ZONE),
    )
