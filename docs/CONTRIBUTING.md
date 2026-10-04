<!--
SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Contributing

> The authoritative, org-wide version of these conventions is the [ParkviewLab handbook](https://github.com/ParkviewLab/handbook/tree/main).

This repo follows the ParkviewLab conventions. The essentials:

## Branch & PR flow

- Branch off `develop` into an ephemeral worktree named with a prefix: `feature-`, `bug-`/`fix-`, `doc-`, `test-`, `ops-`, `ci-`, `build-`, `release-` (hyphen, not slash). See the handbook's [`branching.md`](https://github.com/ParkviewLab/handbook/blob/main/docs/branching.md).
- Open a PR into `develop`. The repo is merge-commit only, so the merge button can only make a merge commit; merging is the maintainer's action.
- Releases are cut from `main` from the command line (`git merge --no-ff develop`, then bump and tag), not through a PR, and end with the back-merge pull request from `back-merge-<tag>`, which `git back-merge` opens, checks and merges. See the README's Releasing section and the handbook's [`releases.md`](https://github.com/ParkviewLab/handbook/blob/main/docs/releases.md).

## Commit / PR-title convention (this is what the changelog reads)

Because a PR is merged with a merge commit titled `<PR title> (#N)`, the PR title becomes the commit subject, and the changelog is generated from it (by dev-tools' shared `generate-changelog`, which lists every merged PR by its title, under the section its type names). Prefix every PR title with a [Conventional Commit](https://www.conventionalcommits.org/) type:

| Prefix | CHANGELOG section | Notes |
|---|---|---|
| `feat:` | Features | user-visible |
| `fix:` | Bug fixes | user-visible |
| `perf:` | Performance | user-visible |
| `refactor:` | Refactor | |
| `docs:` | Docs | |
| `test:` | Tests | |
| `revert:` | Reverts | |
| `chore:` / `ci:` / `build:` / `style:` | Maintenance | |

A `!` after the type (`feat!:`), or a `BREAKING CHANGE:` footer in the PR's description, lists the PR under Breaking changes instead. A PR title without a recognised prefix is listed whole under Other changes, which says nothing about what kind of change it is. So: prefix it. A commit that reaches a release without a PR is listed under Direct commits.

## Local checks before opening a PR

Run the same checks CI requires, so the PR is green on arrival:

```bash
uv sync
uv run ruff check src tests
uv run ruff format --check src tests
uv run ty check
uv run pytest -m "not network and not integration" -q
uvx --from "reuse[charset-normalizer]" reuse lint
```

CI also checks the licences of the dependencies (`license-check.yml`, job `licenses`); its command, with the list of licences it refuses, is in that workflow.

CI also builds and runs the image (`test.yml`, job `image`). To run the same check locally:

```bash
docker build -t hazel-tracking:ci .
docker run -d --name hazel-tracking -p 35850:35850 -e GITHUB_TOKEN_HAZEL_TRACKING=dummy-token -e HAZEL_TRACKING_GITHUB_API_URL=http://127.0.0.1:9 hazel-tracking:ci
docker inspect --format '{{.State.Health.Status}}' hazel-tracking   # "healthy" after about six seconds on Docker Engine 25 and later
curl http://127.0.0.1:35850/health                                  # the version pyproject.toml declares
curl -s http://127.0.0.1:35850/ | grep -c 'ParkviewLab Engineering Dashboard'
docker rm -f hazel-tracking
```

A PR can't be merged until the five required checks pass: `test` and `image` ([`test.yml`](../.github/workflows/test.yml)), `reuse`, `licenses` and `no-version-change`. Push after each commit. See also the handbook's [`python-tooling.md`](https://github.com/ParkviewLab/handbook/blob/main/docs/python-tooling.md) and [`testing.md`](https://github.com/ParkviewLab/handbook/blob/main/docs/testing.md).

## Versioning

The version lives in `pyproject.toml` only; never hard-code it elsewhere, and never type it on a `git tag` line. Use `git bump` / `git release` from [`dev-tools`](https://github.com/ParkviewLab/dev-tools). See the handbook's [`releases.md`](https://github.com/ParkviewLab/handbook/blob/main/docs/releases.md).

## AI contributors

Read `docs/northstar.md` first, and follow the behavioural contract in the handbook's [`ai-collaboration.md`](https://github.com/ParkviewLab/handbook/blob/main/docs/ai-collaboration.md) (notably: merging, tagging and releasing need an explicit, per-release go-ahead). The northstar leads: a change that alters intent amends it in the same PR, and an unintended disagreement between it and the code is a defect in the code.
