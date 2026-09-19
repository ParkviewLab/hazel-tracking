# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""The configuration: every variable of the README's Configuration table, its default and its refusal,
and the version, which has one source of truth (pyproject.toml) and is derived at runtime."""

from __future__ import annotations

import tomllib
from importlib.metadata import version
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

import hazel_tracking
from hazel_tracking.config import (
    GATHER_INTERVAL_SECONDS,
    RETRY_INTERVAL_SECONDS,
    TOKEN_VARIABLE,
    VERSION,
    Config,
    load_config,
)

ROOT = Path(__file__).resolve().parent.parent

VARIABLES = (
    "HOST",
    "PORT",
    TOKEN_VARIABLE,
    "HAZEL_TRACKING_GITHUB_ORG",
    "HAZEL_TRACKING_GITHUB_API_URL",
    "HAZEL_TRACKING_WAIT_SECONDS",
    "TZ",
)


@pytest.fixture
def environment(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """The environment with none of the service's variables set."""
    for name in VARIABLES:
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def test_the_defaults(environment: pytest.MonkeyPatch) -> None:
    cfg = load_config()
    assert cfg.host == "127.0.0.1"
    assert cfg.port == 35850
    assert cfg.github_token is None
    assert cfg.github_org == "ParkviewLab"
    assert cfg.github_api_url == "https://api.github.com"
    assert cfg.wait_seconds == 15
    assert cfg.time_zone == ZoneInfo("UTC")
    assert cfg.gather_interval_seconds == 600
    assert cfg.retry_interval_seconds == 60


def test_every_variable_is_read(environment: pytest.MonkeyPatch) -> None:
    environment.setenv("HOST", "0.0.0.0")
    environment.setenv("PORT", "35851")
    environment.setenv(TOKEN_VARIABLE, " a-token ")
    environment.setenv("HAZEL_TRACKING_GITHUB_ORG", "ExampleOrg")
    environment.setenv("HAZEL_TRACKING_GITHUB_API_URL", "http://127.0.0.1:9/")
    environment.setenv("HAZEL_TRACKING_WAIT_SECONDS", "2.5")
    environment.setenv("TZ", "America/Los_Angeles")
    cfg = load_config()
    assert cfg.host == "0.0.0.0"
    assert cfg.port == 35851
    assert cfg.github_token == "a-token"
    assert cfg.github_org == "ExampleOrg"
    assert cfg.github_api_url == "http://127.0.0.1:9"
    assert cfg.wait_seconds == 2.5
    assert cfg.time_zone == ZoneInfo("America/Los_Angeles")


def test_an_empty_value_counts_as_unset(environment: pytest.MonkeyPatch) -> None:
    for name in VARIABLES:
        environment.setenv(name, "  ")
    assert load_config() == Config()


def test_the_interval_and_the_retry_are_ruled_not_read(environment: pytest.MonkeyPatch) -> None:
    environment.setenv("HAZEL_TRACKING_GATHER_INTERVAL_SECONDS", "5")
    environment.setenv("HAZEL_TRACKING_RETRY_INTERVAL_SECONDS", "5")
    cfg = load_config()
    assert (cfg.gather_interval_seconds, cfg.retry_interval_seconds) == (
        GATHER_INTERVAL_SECONDS,
        RETRY_INTERVAL_SECONDS,
    )


@pytest.mark.parametrize(("name", "value"), [("PORT", "http"), ("PORT", "0"), ("PORT", "70000")])
def test_a_port_that_cannot_serve_is_refused(environment: pytest.MonkeyPatch, name: str, value: str) -> None:
    environment.setenv(name, value)
    with pytest.raises(ValueError, match="PORT"):
        load_config()


@pytest.mark.parametrize("value", ["soon", "0", "-1", "nan", "inf"])
def test_a_wait_that_is_not_a_positive_number_of_seconds_is_refused(
    environment: pytest.MonkeyPatch, value: str
) -> None:
    environment.setenv("HAZEL_TRACKING_WAIT_SECONDS", value)
    with pytest.raises(ValueError, match="HAZEL_TRACKING_WAIT_SECONDS"):
        load_config()


@pytest.mark.parametrize("value", ["Mars/Olympus_Mons", "../UTC"])
def test_a_time_zone_that_is_not_an_iana_zone_is_refused(environment: pytest.MonkeyPatch, value: str) -> None:
    environment.setenv("TZ", value)
    with pytest.raises(ValueError, match="TZ"):
        load_config()


def test_shortened_intervals_are_accepted_and_nonpositive_ones_refused() -> None:
    assert Config(gather_interval_seconds=0.5, retry_interval_seconds=0.1).retry_interval_seconds == 0.1
    with pytest.raises(ValueError, match="interval"):
        Config(retry_interval_seconds=0)


def test_the_token_is_not_in_the_configuration_s_repr(sentinel_token: str) -> None:
    assert sentinel_token not in repr(Config(github_token=sentinel_token))


def test_the_version_is_read_from_package_metadata() -> None:
    assert version("hazel-tracking") == VERSION
    assert hazel_tracking.__version__ == VERSION


def test_the_version_matches_pyproject() -> None:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert data["project"]["version"] == VERSION


def test_no_literal_copy_of_the_version_in_the_source() -> None:
    """Nothing in src/ hard-codes the version string; only the metadata lookup carries it."""
    literal = VERSION.split("+")[0]
    for path in (ROOT / "src").rglob("*.py"):
        assert f'"{literal}"' not in path.read_text(), path
