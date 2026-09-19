<!--
SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# hazel-tracking: decisions

This is the record of hazel-tracking's decisions: dated entries that describe what was decided and why, kept as history. Entries stand in the order they were made, newest last, and an entry is not rewritten when a later decision changes it; the later entry records the change. Each entry names the decision, the reason as it was recorded, and the alternatives set aside; where the record gives no reason or names no alternative, the entry says so rather than supplying one.

The entries from the first to the open-issue count record the rulings on the Dashboard's requirements and design that Phase 1 embodies. D1 to D10 record the rulings on the decisions of the Phase 1 plan, with R12 and R13, the plan's readings of the dev builds; the readings R1 to R11 are in [`what-it-shows.md`](what-it-shows.md), which specifies the page. Questions still open are in [`in-flight_ideas.md`](in-flight_ideas.md).

## 2026-09-17: a service that stores nothing and gathers on request

Decided: the Dashboard stores and manages no data of its own. Each time the page is requested, it gathers what it shows from its sources, so what it shows is current as of that request. Reason: the page is to be current as of each request, the answer given that day to the question how current it must be. Set aside, as the design records them: polling on a timer and keeping a cache, since the Dashboard stores nothing; a page served by paper-boxing whose script fetches the data, since a script in a web page can read only GitHub today and can never read a machine's own files; and the Mac pushing its facts to the Dashboard, which would do work while nobody is looking, which is nearly all the time.

## 2026-09-17: three colours, with shape carrying the rest

Decided: three colours, with shape carrying the rest. Reason: the page is to read correctly without colour and from across the room; the requirement behind the ruling is that the page can be read without relying on colour alone. Set aside: a fourth hue for what is unknown, which the same ruling showed by a hollow ring instead. Data not gathered has since been ruled to show zeroed and greyed out (the entry of 18 September 2026 below), and R10 reads that grey as outside the three colours.

## 2026-09-18: the name and the repository

Decided: the service shows "ParkviewLab Engineering Dashboard" as its display name in the top chrome of its page, and its repository is `ParkviewLab/hazel-tracking`. Reason: the repository's name is in the house naming style of a pigment and a gerund. Set aside: none recorded.

## 2026-09-18: the phases, and the scope of Phase 1

Decided: the Dashboard is built in phases, one data source at a time, each phase adding one source to a service that already runs. Phase 1 shows only what GitHub supplies, and only for the repositories of the ParkviewLab organisation; `garycoding/Development-Lab` joins in a later phase. It is a NiceGUI app in a Docker stack on trixie, whose only credential is a read-only GitHub token covering the organisation, including read access to its packages, since dev releases are read from GHCR. Phase 1 covers these requirements: whether there are working branches on the remote; whether there are open pull requests; the version of the latest dev release and of the latest final release; the status of each open pull request; from what is waiting on the reader, a release ready to cut, a branch pushed with no pull request and a back-merge not completed; whether the checks on the trunks pass; how far `develop` is ahead of `main`, and how far each working branch is behind `develop`; unreleased work, and whether any of it changes the documentation; when anything last happened, as far as GitHub records it; and the number of open issues. Reason: not recorded beyond the decision. Set aside: none recorded. The order of the later phases is not ruled.

## 2026-09-18: gathering on load, on Refresh and every ten minutes, with the data's age

Decided: nothing is pushed to the Dashboard and nothing polls. When a browser requests the page, the Dashboard asks all its sources at once, renders when the answers are in, and returns the page. The chrome carries a Refresh button that gathers fresh data on demand; the page also gathers by itself every ten minutes, only while a browser is showing it; and the chrome shows one clock for the whole page, counting in minutes and seconds how old the data on the page is. The page is not interactive, except for the Refresh button and an information icon in the status bar. Reason: the page shows how current its information is, so that a stale view cannot pass for a current one, the suggested requirement accepted in the form of the clock. Set aside: polling on a timer and keeping a cache, as in the entry of 17 September 2026.

## 2026-09-18: data not gathered, and the status bar

Decided: data the Dashboard could not gather is shown zeroed and greyed out. A status bar across the bottom of the page states the health of the last refresh: when something went wrong, it says in one brief sentence what and why, and an information icon beside it opens a dialog with the detail. Reason: when a fact cannot be determined because a source is unreachable, the page says so rather than showing "no"; this is the form in which that suggested requirement was answered. Set aside: the suggested requirement's own form, in which such a fact says, in place of its value, that it could not be determined.

## 2026-09-18: no secret shown

Decided: nothing on the page, the status bar and its dialog included, ever shows a token, a password or any other secret value; a credential may be named in general terms, such as "the GitHub token was refused". This also settles whether a token's name counts as a secret's name: the page names a credential only in general terms. Reason: not recorded beyond the decision. Set aside: the suggested requirement's form, which barred a secret's name as well as its value.

## 2026-09-18: the home network, with no login

Decided: any device on the home network can open the page, with no login, and nothing outside the network can reach it, like the lab's other services. Reason: it is treated as the lab's other services are. Set aside: a page readable from the Mac alone.

## 2026-09-18: the definitions settled for Phase 1

Decided, each with the question of definition it settles:

- Archived repositories do not appear (question 24, its archived-repository part). Reason: not recorded. Set aside: showing them; none existed when the question was asked.
- A working branch is every branch other than the repository's trunks, whoever made it: bots' branches count, and so do branches with nothing on them that `develop` lacks. The trunks are `main` and `develop`, and in the two website repositories, parkviewlab.ai and zoestum.ai, `live` and `staging` (question 3). Reason: not recorded. Set aside: leaving out a bot's branch, such as the Dependabot branch in deco-assaying, and a legacy branch identical to `develop`, such as `claude` in pvl-dotview.
- Pull requests opened by bots count as open pull requests (question 7). Reason: not recorded. Set aside: leaving them out.
- The latest final release is shown both ways: the newest version tag and the newest GitHub Release, the page highlighting a difference between them, as when a tag was pushed but its Release never created (question 8). Reason: the two differed in dev-tools and pvl-dotview when the question was asked. Set aside: the tag alone, or the Release alone.
- The latest dev release is shown only when it is newer than the latest final release, and otherwise none is shown; an Electron app's dev build still counts once its downloadable files have expired, marked as expired; work in a dev build still counts as unreleased until a final release carries it (question 9). Reason: not recorded. Set aside: showing a dev release that predates the final release, as smalt-mcp's 1.3.3.dev1 did beside 1.3.3; leaving out a build whose files have expired; and counting the work in a dev build as released.
- An open pull request shows its status as GitHub reports it: a draft, checks running, checks failing, conflicts, behind its base, or ready to merge. The page does not say whose turn it is. Only open pull requests are listed: merged and closed ones are not, and merged ones appear only in the count of unreleased work (question 10). Reason: GitHub records no field for whose action is pending. Set aside: a single mark for a pull request whose checks have passed and that awaits a merge, inferred from one that is not a draft and whose merge state is clean.
- "Ready to cut a release" is a single indicator for each repository that releases from `develop` to `main`, ready when at least one merged pull request is not in the latest final release (documentation-only work counts, and the indicator notes when documentation is included), the checks on `develop` pass on its latest commit that ran checks, and the previous release's back-merge is complete; when a condition fails, the indicator names it; it does not appear for the two website repositories (question 11). Reason: the handbook does not define it. Set aside: making the release preflight's documentation currency check and its release-blocker condition part of it, since no system records either.
- How far `develop` is ahead of `main` is measured in merged pull requests, and how far a working branch is behind `develop` in commits, those on `develop` that the branch lacks (question 13). Reason: measured so, the first is the same number as the unreleased work, and the two are shown as one line. Set aside: commits, which count the back-merge and version-bump commits, so that a repository reads one or two ahead with nothing unreleased; and files changed.
- Documentation means the files the repository's documentation site is built from, those under `docs/` and `site/`; the README does not count (question 14). Reason: GitHub shows the README from `develop` as soon as a pull request merges, so the documentation mark means that the published documentation site is behind `develop`. Set aside: `docs/` and the README alone.
- When anything last happened is shown as the time of the last push to any branch, labelled as the last push (question 16, its GitHub part). Reason: not recorded. Set aside: counting pull-request comments, reviews and issues as well.

## 2026-09-18: the open-issue count

Decided: each repository shows the number of its open issues, counting issues only; GitHub's own figure for open issues also includes open pull requests, which are listed separately. Reason: not recorded beyond the decision. Set aside: GitHub's own figure.

## 2026-09-18: D1, the licence

Decided: `MIT OR Apache-2.0`, uniformly, as paper-boxing and deco-assaying are licensed. Reason: paper-boxing's licensing files, SPDX headers and `REUSE.toml` carry over unchanged, and `license-check.yml` keeps copyleft dependencies out. Set aside: none recorded.

## 2026-09-18: D2, the port

Decided: 35850; the Dashboard serves at http://trixie.local:35850/. Reason: the port is free on trixie, in the 358xx block kept for the lab's own services, and the first of an unused decade, as paper-boxing's 35840 was. Set aside: none recorded.

## 2026-09-18: D3, a northstar

Decided: the repository has a northstar, `docs/northstar.md`: the draft approved on 18 September 2026, placed verbatim with the SPDX header and the copyright footer the handbook requires. Its designed HTML twin, `docs/northstar.html`, is authored with the other documents before the first release. Reason: not recorded for the northstar itself; the twin is authored because the documentation site (D4) opens its index with the northstar, which would otherwise be a Markdown link shown as source. Set aside: a northstar written with the scaffold, in place of the approved draft.

## 2026-09-18: D4, a documentation site

Decided: `docs/` is published at https://parkviewlab.github.io/hazel-tracking/, built with the other documents before the first release, so that v0.1.0 publishes it; the README's `Documentation:` line follows that release in its own pull request. Reason: not recorded beyond the decision. Set aside: no documentation site, which the plan had recommended.

## 2026-09-18: D5, dev releases

Decided: dev builds are adopted. `dev-release.yml` publishes only what hazel-tracking publishes: a GHCR image tagged `dev` and with its dev version, never `latest`, with no PyPI or TestPyPI job. A dev build is cut only when one is asked for, for instance to try a deployment on trixie before a final release; before v0.1.0, one is cut and deployed to trixie through the Portainer stack, with the token from Infisical, the release follows once that deployment is proven, and the stack then moves to the pinned release image. The dev version follows the real-merges build's rulings where they are settled (its decision 5 (b): set in the build's workspace from the newest tag, a `kind` input and the run number, with nothing committed), and R12 where they are silent; the workflow is adjusted when that build is released. Reason: a candidate is tried on trixie before a final release. Set aside: no dev builds, which the plan had recommended.

R12. While the repository has no `v*` tag, a dev build's target is the version `pyproject.toml` declares without its `.devN` (0.1.0 from 0.1.0.dev0), whatever the `kind` input, since there is no tag to count from and dev-tools' `sot_compute_next` would give 0.1.1. N is the run number alone, the real-merges ruling's term: a re-run republishes the same version from the same commit, which GHCR accepts. Both give way to the real-merges build's rule when that build is released.

R13. The dev image is also tagged `sha-<commit>`, as the handbook's dev `docker` part tags it and the organisation's dev images are tagged. The tag is kept: it publishes nothing beyond the one image and names the commit the image was built from.

Where `dev-release.yml` differs from the dev parts of handbook v0.25.0, and why. The file is assembled from the dev `head`, `gate` and `docker` parts, and differs from them only in the changes decision 5 (b) makes, since v0.25.0's dev gate still reads the version committed in `pyproject.toml` and the real-merges build, which carries decision 5 into the parts, is not yet released:

- The head declares the `workflow_dispatch` input `kind` (`patch`, `minor` or `major`, default `patch`), and its comment says to run the workflow with `gh workflow run dev-release.yml --ref develop -f kind=<kind>` rather than `git dev-release`, since dev-tools v1.1.0's `git dev-release` commits the dev version to `develop` and pushes it. A comment names this slot.
- The gate checks out every tag (`fetch-depth: 0`), and in place of the check that the committed version carries a dev marker, it computes the dev version: the newest `v*` tag in version order raised by `kind` as `sot_compute_next` raises a plain version, or R12's target while there is no `v*` tag, with N the run number, giving `X.Y.Z.devN`. It refuses a `kind` other than the three.
- The `docker` job installs uv and sets that version in its own workspace with `uv version "$VERSION" --no-sync` before the build, which rewrites `pyproject.toml` and `uv.lock` together, so that the image reports the dev version; nothing is committed.

The file is re-assembled from the dev parts once a handbook release carries decision 5 in them.

## 2026-09-18: D6, publishing

Decided: the image on GHCR only, `ghcr.io/parkviewlab/hazel-tracking`, tagged with the version, the major and minor, and `latest`, for amd64 and arm64; no PyPI or npm package and no installers. `release.yml` carries only the jobs for the image: the gate, `docker` and `changelog`. The README has a section on running the image with Docker and Portainer in place of the five-ways table. Reason: the design rules a Docker stack on trixie, and a PyPI package would add a trusted publisher and a publishing job for a service with one deployment, as was ruled for paper-boxing on 2026-09-15. Set aside: a package on PyPI.

## 2026-09-18: D7, the wait

Decided: a gather waits 15 s for GitHub, set by `HAZEL_TRACKING_WAIT_SECONDS`, a setting of the stack. A gather not complete within the wait shows the facts that did arrive and zeroes and greys the rest, the status bar says why, and the Dashboard tries again every minute until a gather succeeds, after which the ten-minute cycle resumes; a gather complete in time that misses some facts likewise greys only those, as the requirements rule (R8, R11). Amended the same day, with the reading R11: as first ruled, a gather not complete within the wait showed the whole page zeroed and greyed out. Reason: the design proposed a fixed wait so that one slow or unreachable source cannot hold the whole page back, whatever has not answered by then being treated as not gathered. Set aside: 20 s, which the plan had recommended.

## 2026-09-18: D8, the page

Decided: the layout the plan specifies, fitting 1470 by 800 CSS pixels (the Mac's built-in display at its current scaling, less the menu bar and a browser's toolbar) with no type smaller than 12 CSS pixels. The first pass is built with all the information and shown as it is, scrolling if it must; if it does not fit, work on the fit stops there until its solution is ruled. Nothing is dropped, shrunk or hidden to make it fit without a ruling. Reason: not recorded beyond the decision. Set aside: none recorded.

## 2026-09-18: D9, the handbook release

Decided: hazel-tracking is built on the handbook release that carries the fix choosing release and dev-release jobs by publish target, which is v0.25.0, and its templates come from that release rather than from v0.24.0. Whichever of the one-changelog-generator and real-merges builds that release carries is included, and hazel-tracking joins the repository list of any it does not; v0.25.0 carries neither, so hazel-tracking takes `cliff.toml` and `scripts/generate_changelog.py` from its templates and switches with the other repositories when each build lands. Reason: not recorded beyond the decision. Set aside: scaffolding from v0.24.0, which the plan had recommended.

## 2026-09-18: D10, the token

Decided: a classic GitHub token with `read:packages` alone, the only kind GitHub's Packages API accepts, created and stored on 18 September 2026 in Infisical (project trixie, environment Production, folder `/hazel-tracking`) as `GITHUB_TOKEN_HAZEL_TRACKING`; the service reads the environment variable of that name. It was verified that day without being displayed: its scopes are `read:packages` only; it expires on 2027-09-18; it reads the organisation's 16 repositories and its 9 container packages; a write is refused. Reason: every repository of the organisation is public, so the token reads every repository, as the scope requires, and it is read-only, as the design rules; a private repository would be absent without notice, a limit [`what-it-shows.md`](what-it-shows.md#scope) states. Set aside: none recorded.

---
<sub>© 2026 Gary Frattarola · Licensed under [MIT](../LICENSE-MIT) OR [Apache-2.0](../LICENSE-APACHE) · part of [ParkviewLab](https://github.com/ParkviewLab)</sub>
