# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Entry point: `python -m hazel_tracking`, or the `hazel-tracking` script -> NiceGUI (uvicorn underneath)."""

import logging
import sys

from hazel_tracking.app import install, run
from hazel_tracking.config import NAME, TOKEN_VARIABLE, load_config


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    cfg = load_config()
    if not cfg.github_token:
        print(
            f"{NAME}: {TOKEN_VARIABLE} is not set; refusing to start. "
            "Set it to a classic GitHub token with read:packages alone.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    install(cfg)
    run(cfg)


if __name__ == "__main__":
    main()
