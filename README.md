<!--
SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# hazel-tracking

The ParkviewLab Engineering Dashboard: one page, served on the development network, showing the present state of every ParkviewLab repository in three tabs (an overview, the detail and the open pull requests), gathered from GitHub each time it is opened or refreshed and stored nowhere.

## Status

Phase 1 is built: the page at `/` with its three tabs, gathered from GitHub alone for the repositories of the ParkviewLab organisation. Its releases are listed on the repository's [releases page](https://github.com/ParkviewLab/hazel-tracking/releases). The overview shows on one screen each repository's release state, its readiness to cut a release and what waits on the reader; the detail shows every fact for every repository in one table of ten columns; and the pull-requests tab lists every open pull request into the integration trunks, with its own Refresh and a Watch. The page gathers when it is opened and on Refresh, and by itself every 30 minutes while it is open, with retries after a gather that is not wholly successful ([`docs/what-it-shows.md`](docs/what-it-shows.md#when-the-page-gathers)). The lab's services, its development machines and BookStack are later phases ([`docs/in-flight_ideas.md`](docs/in-flight_ideas.md)).

What the page shows is specified in [`docs/what-it-shows.md`](docs/what-it-shows.md), the repository's authority for it. How the software is put together, each fact's call to GitHub included, is [`docs/architecture.md`](docs/architecture.md); how it is deployed is [`docs/deployment.md`](docs/deployment.md). The record of decisions is [`docs/decisions.md`](docs/decisions.md), and the intent [`docs/northstar.md`](docs/northstar.md).

## Run

hazel-tracking runs in Docker, with `docker compose` or as a Portainer stack; there is no PyPI package. The image is `ghcr.io/parkviewlab/hazel-tracking`, for amd64 and arm64, published by each release; it may also be built from a checkout, with `docker build -t ghcr.io/parkviewlab/hazel-tracking:latest .`.

```bash
cp .env.example .env          # set GITHUB_TOKEN_HAZEL_TRACKING, and TZ to the lab's zone
docker compose up -d
docker compose ps             # "health: starting" for about six seconds, then "healthy"
curl http://127.0.0.1:35850/health
```

The six seconds hold on Docker Engine 25 and later, where the health check runs every 5 s during its start period. Then open `http://<host>:35850/`, where `<host>` is the Docker host as the development network reaches it. For Portainer, paste [`docker-compose.yml`](docker-compose.yml) into the stack's web editor and enter the same variables as the stack's environment variables. [`docs/deployment.md`](docs/deployment.md) covers both in full, with the token, the wait, a dev build and troubleshooting.

The service reads GitHub with one token; its kind, what it can read and its expiry are in [`docs/deployment.md`](docs/deployment.md#the-token). The service stores nothing, so the stack has no volume.

The deployment assumes the development network, plain HTTP and no login: any device on the network can open the page, and it is not for the public internet. The page never shows the token or any other secret.

## Endpoints

Port 35850, inside the container and outside it:

- `GET /`: the page, with its three tabs. It is drawn at once and filled when its gathers return; it has no API of its own.
- `GET /health`: `{ok, version, uptime_seconds}`, which the image's health check requests.
- `GET /admin/version`: `{name, version, host, port, github_org, github_api_url, wait_seconds, time_zone}`, the name, the version and every setting below except the token.

## Configuration

Every variable is read from the environment at startup. The image sets `HOST` and `PORT`, and the compose file sets the token, the wait and the time zone.

| Variable | Default | Purpose |
|---|---|---|
| `HOST` | `127.0.0.1` (image: `0.0.0.0`) | bind address |
| `PORT` | `35850` | listen port |
| `GITHUB_TOKEN_HAZEL_TRACKING` | unset, required | the GitHub token ([`docs/deployment.md`](docs/deployment.md#the-token)); it has no default, and the service refuses to start without it, with exit status 2 |
| `HAZEL_TRACKING_GITHUB_ORG` | `ParkviewLab` | the organisation whose repositories the page shows |
| `HAZEL_TRACKING_GITHUB_API_URL` | `https://api.github.com` | the GitHub API the service reads |
| `HAZEL_TRACKING_WAIT_SECONDS` | `15` | how long a gather waits for GitHub, in seconds, whole or not ([`docs/what-it-shows.md`](docs/what-it-shows.md#the-wait)) |
| `TZ` | `UTC` | the IANA time zone in which the page shows times, such as `America/Los_Angeles` |

An unset or empty variable takes its default, except the token, which has none: without it the service stops at start with exit status 2. A value that cannot be read (a port that is not an integer between 1 and 65535, a wait that is not a number of seconds greater than 0, a zone that is not an IANA time zone) stops the service at start with an error naming the variable. The schedule is ruled, not configured: the automatic gather every 30 minutes, the retries after 1, 2, 4, 8 and 16 minutes, and the watch's gather every 10 seconds for at most 10 minutes are constants in [`src/hazel_tracking/config.py`](src/hazel_tracking/config.py), as [`docs/what-it-shows.md`](docs/what-it-shows.md) rules them under "When the page gathers" and "The pull requests".

## Releasing

Tag-driven via the `Release` workflow on push of a `v*` tag. Use the [`ParkviewLab/dev-tools`](https://github.com/ParkviewLab/dev-tools) helpers; `pyproject.toml` is the only place the version lives, and the workflow's gate refuses a tag that does not match it. A release runs from the `hazel-tracking-main` worktree, in the handbook's flow:

```sh
git pull --ff-only                                # sync main
git -C ../hazel-tracking-develop pull --ff-only   # sync develop: the merge below takes the local branch
git merge --no-ff develop                         # promote develop to main; the merge commit is the release ledger entry
git bump <patch|minor|major|release>              # bumps pyproject.toml and commits "release vX.Y.Z"
git release                                       # annotated tag vX.Y.Z from pyproject.toml
git push --follow-tags                            # the tag push fires the workflow
```

A first release has no `git bump`: `pyproject.toml` already declares the first version, where the templates start, so `git release` tags it as it stands.

The release's last step is `git back-merge`, which builds the branch `back-merge-<tag>` from `develop` and `main`, adds to it the commit that opens the next development cycle (`X.Y.(Z+1).dev0` in `pyproject.toml`), opens a pull request from it into `develop`, and merges it once `develop`'s required checks, the version guard's back-merge mode among them, have passed. See the handbook's [`releases.md`](https://github.com/ParkviewLab/handbook/blob/main/docs/releases.md#the-releases-last-step-the-back-merge-pull-request).

The workflow runs a gate (the tag equals the version, which carries no dev marker; the tagged commit is reachable from `main`; the version is greater than the previous tag), then a `docker` job that builds and pushes the image for amd64 and arm64 with the `X.Y.Z`, `X.Y` and `latest` tags, then a `changelog` job that writes the new section of `CHANGELOG.md`, which the first release creates (an LLM-written Highlights paragraph and dev-tools' [`generate-changelog`](https://github.com/ParkviewLab/dev-tools)'s categorized list of merged pull requests), commits it to `main`, and creates the GitHub Release. There is no PyPI publish.

### Dev builds

A dev build is dispatched on `develop`, with `git dev-release <kind>` or:

```sh
gh workflow run dev-release.yml --repo ParkviewLab/hazel-tracking --ref develop -f kind=patch   # or minor, or major
```

When to cut one, its version, its tags and how to try it are in [`docs/deployment.md`](docs/deployment.md#trying-a-dev-build).

### Commit message convention

Because a PR is merged with a merge commit titled `<PR title> (#N)`, the PR title carries the [Conventional Commit](https://www.conventionalcommits.org/) prefix that the changelog generator reads; see the handbook's [`commits-and-changelogs.md`](https://github.com/ParkviewLab/handbook/blob/main/docs/commits-and-changelogs.md#conventional-commit-prefixes) for the groups a title's type is sorted into and what an unrecognised or missing type gets. See [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md).

## License

Licensed under either of

- Apache License, Version 2.0 ([LICENSE-APACHE](LICENSE-APACHE) or <http://www.apache.org/licenses/LICENSE-2.0>), or
- MIT license ([LICENSE-MIT](LICENSE-MIT) or <http://opensource.org/licenses/MIT>)

at your option. In SPDX terms: `MIT OR Apache-2.0`.

Unless you explicitly state otherwise, any contribution intentionally submitted for inclusion in this work by you shall be dual-licensed as above, without any additional terms or conditions. See [LICENSING.md](LICENSING.md).

---
<sub>© 2026 Gary Frattarola · Licensed under [MIT](LICENSE-MIT) OR [Apache-2.0](LICENSE-APACHE) · part of [ParkviewLab](https://github.com/ParkviewLab)</sub>
