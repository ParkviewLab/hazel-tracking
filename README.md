<!--
SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# hazel-tracking

The ParkviewLab Engineering Dashboard: one page, served on the home network, showing the present state of every ParkviewLab repository, gathered from GitHub each time it is shown and stored nowhere.

## Status

Unreleased; `develop` carries 0.1.0.dev0. This version is the scaffold: the package, the contract between the gathering and the page ([`src/hazel_tracking/model.py`](src/hazel_tracking/model.py)), the image, the stack and the workflows. Its page at `/` shows the display name alone and gathers nothing.

What the page shows is specified in [`docs/what-it-shows.md`](docs/what-it-shows.md), the repository's authority for it. The record of decisions is [`docs/decisions.md`](docs/decisions.md), and the intent [`docs/northstar.md`](docs/northstar.md).

## Run

hazel-tracking runs in Docker, with `docker compose` or as a Portainer stack; there is no PyPI package. The image is `ghcr.io/parkviewlab/hazel-tracking`, for amd64 and arm64, published by each release. No release exists yet, so from a checkout, build the image first with `docker build -t ghcr.io/parkviewlab/hazel-tracking:latest .`.

```bash
cp .env.example .env          # set GITHUB_TOKEN_HAZEL_TRACKING, and TZ to the lab's zone
docker compose up -d
docker compose ps             # "health: starting" for about six seconds, then "healthy"
curl http://127.0.0.1:35850/health
```

Then open `http://<host>:35850/`. For Portainer, paste [`docker-compose.yml`](docker-compose.yml) into the stack's web editor and enter the same variables as the stack's environment variables.

The token is a classic GitHub token with `read:packages` alone, the only kind GitHub's Packages API accepts: it reads the organisation's public repositories and its container packages, and it can write nothing. The service stores nothing, so the stack has no volume.

The deployment assumes the home network, plain HTTP and no login: any device on the network can open the page, and it is not for the public internet. The page never shows the token or any other secret.

## Endpoints

Port 35850: the page at `/`; `GET /health`, which returns `{ok, version, uptime_seconds}`; and `GET /admin/version`, which returns the name, the version and every setting below except the token.

## Configuration

Every variable is read from the environment at startup. The image sets `HOST` and `PORT`, and the compose file sets the token, the wait and the time zone.

| Variable | Default | Purpose |
|---|---|---|
| `HOST` | `127.0.0.1` (image: `0.0.0.0`) | bind address |
| `PORT` | `35850` | listen port |
| `GITHUB_TOKEN_HAZEL_TRACKING` | unset, required | the GitHub token, a classic token with `read:packages` alone; the service refuses to start without it, with exit status 2 |
| `HAZEL_TRACKING_GITHUB_ORG` | `ParkviewLab` | the organisation whose repositories the page shows |
| `HAZEL_TRACKING_GITHUB_API_URL` | `https://api.github.com` | the GitHub API the service reads |
| `HAZEL_TRACKING_WAIT_SECONDS` | `15` | how long a gather waits for GitHub, in seconds, whole or not ([`docs/what-it-shows.md`](docs/what-it-shows.md#the-wait)) |
| `TZ` | `UTC` | the IANA time zone in which the page shows times, such as `America/Los_Angeles` |

## Releasing

Tag-driven via the `Release` workflow on push of a `v*` tag. Use the [`ParkviewLab/dev-tools`](https://github.com/ParkviewLab/dev-tools) helpers; `pyproject.toml` is the only place the version lives, and the workflow's gate refuses a tag that does not match it. A release runs from the `hazel-tracking-main` worktree, in the handbook's flow:

```sh
git pull --ff-only                                # sync main
git -C ../hazel-tracking-develop pull --ff-only   # sync develop: the merge below takes the local branch
git merge --no-ff develop                         # promote develop to main; the merge commit is the release ledger entry
git bump <patch|minor|major|release>              # sets the version in pyproject.toml and commits "release vX.Y.Z"
git release                                       # annotated tag vX.Y.Z from pyproject.toml
git push --follow-tags                            # the tag push fires the workflow
```

`git bump release` sets the version to the one `develop` declares, without its dev marker: 0.1.0 from 0.1.0.dev0. Once the workflow is green, the back-merge cascade brings `main`'s release and changelog commits down: `main` into `develop` with `--no-ff`, then `develop` into each open working branch, and `develop` opens the next development cycle (`X.Y.(Z+1).dev0` in `pyproject.toml`).

The workflow runs a gate (the tag equals the version, which carries no dev marker; the tagged commit is reachable from `main`; the version is greater than the previous tag), then a `docker` job that builds and pushes the image for amd64 and arm64 with the `X.Y.Z`, `X.Y` and `latest` tags, then a `changelog` job that writes the new section of `CHANGELOG.md` (an LLM-written Highlights paragraph and [`git-cliff`](https://git-cliff.org/)'s categorized list), commits it to `main`, and creates the GitHub Release. There is no PyPI publish.

### Dev builds

A dev build is cut only when one is asked for, for instance to try a deployment on trixie before a release. It is dispatched on `develop`:

```sh
gh workflow run dev-release.yml --repo ParkviewLab/hazel-tracking --ref develop -f kind=patch   # or minor, or major
```

The `Dev release` workflow computes the dev version in its own workspace and commits nothing: the newest `v*` tag raised by `kind`, with the run's number as N (`X.Y.Z.devN`), or, while there is no `v*` tag, the version `pyproject.toml` declares without its dev marker (`0.1.0.devN`). It pushes the image tagged `dev`, with that version and with `sha-<commit>`, never `latest`. dev-tools' `git dev-release` is not used, since its v1.1.0 commits the dev version to `develop`. [`docs/decisions.md`](docs/decisions.md) records why the workflow differs from the handbook's dev parts.

### Commit message convention

PRs are squash-merged with the PR title as the commit subject, so the PR title carries the [Conventional Commit](https://www.conventionalcommits.org/) prefix that [`cliff.toml`](cliff.toml) reads: `feat:`, `fix:` and `perf:` are user-visible sections, `refactor:`, `docs:` and `test:` have their own, and `chore:`, `ci:`, `build:` and `style:` are dropped from the changelog but stay in history; merge commits are dropped as well, and a `Revert` commit goes to a Reverts section. See [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md).

## License

Licensed under either of

- Apache License, Version 2.0 ([LICENSE-APACHE](LICENSE-APACHE) or <http://www.apache.org/licenses/LICENSE-2.0>), or
- MIT license ([LICENSE-MIT](LICENSE-MIT) or <http://opensource.org/licenses/MIT>)

at your option. In SPDX terms: `MIT OR Apache-2.0`.

Unless you explicitly state otherwise, any contribution intentionally submitted for inclusion in this work by you shall be dual-licensed as above, without any additional terms or conditions. See [LICENSING.md](LICENSING.md).

---
<sub>© 2026 Gary Frattarola · Licensed under [MIT](LICENSE-MIT) OR [Apache-2.0](LICENSE-APACHE) · part of [ParkviewLab](https://github.com/ParkviewLab)</sub>
