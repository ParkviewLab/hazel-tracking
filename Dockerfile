# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

# The hazel-tracking image: the uv python3.13 slim image, the dependencies installed
# before the source so that their layer caches across source changes, and
# `python -m hazel_tracking`. No volume: the service stores nothing.
#
#   docker build -t ghcr.io/parkviewlab/hazel-tracking:latest .

FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0

# Dependency manifests first, so the dependency layer caches across source changes.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

# README.md and the licence files are package metadata (pyproject.toml -> readme,
# license-files); the second sync installs the project itself and reads them.
COPY README.md LICENSE-MIT LICENSE-APACHE ./
COPY src/ src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

ENV PORT=35850

EXPOSE 35850
HEALTHCHECK --interval=15s --timeout=3s --start-period=15s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:35850/health', timeout=2)"]

CMD ["uv", "run", "--no-sync", "python", "-m", "hazel_tracking"]
