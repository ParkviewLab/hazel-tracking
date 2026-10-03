<!--
SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Deployment

How to run hazel-tracking, with `docker compose` or as a Portainer stack, and how to try a dev build before a release. It is written for any reader of the public repository and names no private host or secret: `<host>` stands for the name or address at which the development network reaches the Docker host, and `<stack>` for the compose project or Portainer stack; substitute your own. How the service is put together is [`architecture.md`](architecture.md), and every setting with its default is in the README's [Configuration](../README.md#configuration) table.

The deployment model, stated plainly (the README says the same): the development network, plain HTTP and no login. Any device on the network can open the page; it is not for the public internet, and its port is not to be exposed to it. The page shows no secret, and the service writes to nothing, GitHub included.

## The image

`ghcr.io/parkviewlab/hazel-tracking`, for amd64 and arm64, built from the repository's `Dockerfile` on the uv Python 3.13 slim image. A release publishes it tagged with its version (`X.Y.Z`), its major and minor (`X.Y`) and `latest`; a dev build, cut only on request, publishes it tagged `dev`, with its dev version (`X.Y.Z.devN`) and with `sha-<commit>`, and never `latest`. There is no other publication: no PyPI package and no installer (D6).

The image runs `python -m hazel_tracking` as one process, with `HOST=0.0.0.0` and `PORT=35850` set, and listens on 35850 inside the container as outside it. Its health check requests `/health` on that port every 15 s, after a start period of 15 s. The service stores nothing, so the image declares no volume and the stack mounts none.

To build it from a checkout, for instance before the first release exists:

```bash
docker build -t ghcr.io/parkviewlab/hazel-tracking:latest .
```

## The compose file

[`docker-compose.yml`](../docker-compose.yml) is the stack: one service, `hazel-tracking`, with the image at `latest`, restarted unless stopped, port 35850 published as 35850, and no volume. It reads three settings from `${...}` variables, so that the same file works from a `.env` beside it and from Portainer's stack environment:

| Variable | In the compose file | What it is |
|---|---|---|
| `GITHUB_TOKEN_HAZEL_TRACKING` | required, no default; compose refuses to start the stack without it | the GitHub token (below) |
| `HAZEL_TRACKING_WAIT_SECONDS` | `15` | how long a gather waits for GitHub, in seconds (below) |
| `TZ` | `UTC` | the IANA time zone in which the page shows times, such as `America/Los_Angeles` |

The organisation and GitHub's API address keep the service's defaults (`ParkviewLab`, `https://api.github.com`); to change either, add `HAZEL_TRACKING_GITHUB_ORG` or `HAZEL_TRACKING_GITHUB_API_URL` to the service's `environment`.

To pin a version rather than follow `latest`, edit the `image:` line to the release's tag, `ghcr.io/parkviewlab/hazel-tracking:X.Y.Z`.

## The token

The service reads GitHub with one credential, in the environment variable `GITHUB_TOKEN_HAZEL_TRACKING` (D10). It is a classic personal access token with the `read:packages` scope and no other: a classic token because GitHub's Packages API, from which the dev releases are read, accepts no other kind, and `read:packages` because it is the one scope the Dashboard needs. A classic token reads public repositories without any scope, and every repository of the organisation is public, so with `read:packages` alone the token reads every repository and every container package of the organisation, and can write nothing. A private repository would be absent from the page without notice, since the token cannot read it ([`what-it-shows.md`](what-it-shows.md#scope)).

The token has no `repo` scope, by D10, and so GraphQL refuses it the fields that compare two branches; the service reads the comparisons over REST instead, which serves it ([`architecture.md`](architecture.md#each-facts-call)).

Create it in GitHub's settings under Developer settings, Personal access tokens, Tokens (classic), with `read:packages` ticked and nothing else, and with an expiry. The status bar shows when it expires, as GitHub reports it, in yellow within 30 days of the expiry. To replace it, create a new token the same way, set the stack's variable to it, and redeploy the stack; nothing else holds it. Keep it in the stack's environment or a `.env` that is not committed, never in the compose file.

## The wait

How long a gather waits for GitHub is `HAZEL_TRACKING_WAIT_SECONDS`, 15 s by default, a setting of the stack (D7): set it in `.env` or in the stack's environment, not in the image. It may be a whole number of seconds or not, and must be greater than 0. A gather not complete within the wait shows what had arrived and greys the rest, and the status bar says so and when the page tries again ([`what-it-shows.md`](what-it-shows.md#the-wait)). A full gather of the organisation took 5.4 s and 7.4 s when measured on 2026-10-03, so the default leaves room for a slow answer without a long wait when GitHub is in trouble.

## Running with docker compose

From a directory holding `docker-compose.yml` and `.env.example`:

```bash
cp .env.example .env          # set GITHUB_TOKEN_HAZEL_TRACKING, and TZ to the lab's zone
docker compose up -d
docker compose ps             # "health: starting" for about six seconds, then "healthy"
curl http://127.0.0.1:35850/health
```

`/health` answers `{"ok": true, "version": "X.Y.Z", "uptime_seconds": ...}`, and `/admin/version` the name, the version and every setting except the token, which is how to confirm the wait and the time zone the service is running with. Then open `http://<host>:35850/`. To upgrade, `docker compose pull && docker compose up -d`; to stop, `docker compose down`. There is nothing to back up: the stack holds no data.

## Running in Portainer

The compose file is written for Portainer's stacks: it has no build step and no host path, and reads every setting from the environment.

Create the stack, named for instance `hazel-tracking`, in one of two ways. From the web editor, paste `docker-compose.yml` as it is, editing the `image:` line to a version tag if the stack is to be pinned. From the repository, give `https://github.com/ParkviewLab/hazel-tracking`, the reference of a release tag (`refs/tags/vX.Y.Z`) and the compose path `docker-compose.yml`; the file at that tag names `latest`, so such a stack follows the newest release at each redeploy.

Enter the variables as the stack's environment variables: `GITHUB_TOKEN_HAZEL_TRACKING`, and, where the defaults do not serve, `HAZEL_TRACKING_WAIT_SECONDS` and `TZ`. The token stays in the stack's environment and appears nowhere in the repository.

Deploy. The container `hazel-tracking` appears under the stack and turns healthy after its first health check. Its log records, at the warning level, each call to GitHub that gave no answer or could not be read, named in the page's words and never with the token. To update, change the image tag in the stack's editor (or keep `latest`) and update the stack with the option that pulls the image again.

## Trying a dev build

A dev build is cut only when one is asked for, to try a candidate on the development server before a release (D5). It is dispatched on `develop`:

```sh
gh workflow run dev-release.yml --repo ParkviewLab/hazel-tracking --ref develop -f kind=patch   # or minor, or major
```

The workflow commits nothing; it computes the dev version in its own workspace and publishes the image tagged `dev`, with that version and with `sha-<commit>`, never `latest` (the README's [Dev builds](../README.md#dev-builds) gives the version's rule). To try it, point the stack's `image:` line at the dev version's tag, `ghcr.io/parkviewlab/hazel-tracking:X.Y.Z.devN`, rather than at `dev`, so that the stack names the exact build it runs, and update the stack with the option that pulls the image again. `/health` then reports the dev version. Once a release has followed, move the stack to the release's own tag.

## Troubleshooting

- Compose refuses to start the stack, saying that `GITHUB_TOKEN_HAZEL_TRACKING` must be set: the variable is missing from `.env` or the stack's environment. Set it.
- The container exits at once with status 2 and the line `hazel-tracking: GITHUB_TOKEN_HAZEL_TRACKING is not set; refusing to start.`: it was started outside the compose file without the token. Set it.
- The container exits at start with an error naming `PORT`, `HAZEL_TRACKING_WAIT_SECONDS` or `TZ`: the value is not an integer port between 1 and 65535, not a number of seconds greater than 0, or not an IANA time zone. Correct it and redeploy.
- The status bar says that the GitHub token was refused, and every fact is greyed: the token has expired or been revoked. Replace it as described under The token.
- The status bar says that GitHub's rate limit is spent, with the time the budget resets: the token's hourly budget is used up, by this service's open pages or by anything else using the same token. The page tries again on its schedule; [`architecture.md`](architecture.md#githubs-rate-limits-and-a-gathers-cost) gives what each gather costs.
- The status bar says that GitHub did not answer within the wait: GitHub was slow or unreachable from the container. The dialog behind the information icon names each call still outstanding; the page tries again after 1 minute, then at the growing intervals of its retries. A wait too short for the organisation's size shows this on every gather; raise `HAZEL_TRACKING_WAIT_SECONDS`.
- The status bar says that the token lacks a scope it would need: a call reached a field the token's scopes do not cover. The dialog carries GitHub's message; the token is to keep `read:packages` alone (D10), so this is a defect to report, not a scope to add.
- The dev releases alone are greyed, with GitHub refusing the organisation's container packages: the token lacks `read:packages`, or is not a classic token.

---
<sub>© 2026 Gary Frattarola · Licensed under [MIT](../LICENSE-MIT) OR [Apache-2.0](../LICENSE-APACHE) · part of [ParkviewLab](https://github.com/ParkviewLab)</sub>
