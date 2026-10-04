# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""The entry point refuses to start without the token: exit status 2 and one line saying why."""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

from hazel_tracking.__main__ import main
from hazel_tracking.config import TOKEN_VARIABLE


@pytest.mark.parametrize("value", [None, "", "   "])
def test_main_refuses_to_start_without_the_token(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], value: str | None
) -> None:
    if value is None:
        monkeypatch.delenv(TOKEN_VARIABLE, raising=False)
    else:
        monkeypatch.setenv(TOKEN_VARIABLE, value)
    with pytest.raises(SystemExit) as stopped:
        main()
    assert stopped.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.count("\n") == 1
    assert TOKEN_VARIABLE in captured.err
    assert "refusing to start" in captured.err


def test_the_module_refuses_to_start_without_the_token() -> None:
    """`python -m hazel_tracking` as the image runs it, in a process of its own."""
    env = {name: value for name, value in os.environ.items() if name != TOKEN_VARIABLE}
    done = subprocess.run(
        [sys.executable, "-m", "hazel_tracking"], env=env, capture_output=True, text=True, timeout=120
    )
    assert done.returncode == 2
    assert done.stdout == ""
    assert done.stderr.count("\n") == 1
    assert TOKEN_VARIABLE in done.stderr
