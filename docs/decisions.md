<!--
SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# hazel-tracking: decisions

This is the record of hazel-tracking's decisions: dated entries that describe what was decided and why, kept as history. Entries stand in the order of their dates, oldest first, and an entry is not rewritten when a later decision changes it; the later entry records the change. Each entry names the decision, the reason as it was recorded, and the alternatives set aside; where the record gives no reason or names no alternative, the entry says so rather than supplying one.

The entries from the first to the open-issue count record the rulings on the Dashboard's requirements and design that Phase 1 embodies. D1 to D10 record the rulings on the decisions of the Phase 1 plan, with R12 and R13, the plan's readings of the dev builds; the readings R1 to R11 and R14 to R22 are in [`what-it-shows.md`](what-it-shows.md), which specifies the page. The entries of 2026-10-03 record the rulings made when Phase 1 was compared with prima-dev-dashboard, a local build of Phase 1 used daily as the reference for its behaviour and its page, when the repository was brought to handbook v2.1.1, and, in the last entries, when the page and the gathering were built. Where one of them accepted a recommendation, the reason recorded is the recommendation's. Questions still open are in [`in-flight_ideas.md`](in-flight_ideas.md).

## 2026-09-17: a service that stores nothing and gathers on request

Decided: the Dashboard stores and manages no data of its own. Each time the page is requested, it gathers what it shows from its sources, so what it shows is current as of that request. Reason: the page is to be current as of each request, the answer given that day to the question how current it must be. Set aside, as the design records them: polling on a timer and keeping a cache, since the Dashboard stores nothing; a page served by paper-boxing whose script fetches the data, since a script in a web page can read only GitHub today and can never read a machine's own files; and the Mac pushing its facts to the Dashboard, which would do work while nobody is looking, which is nearly all the time.

## 2026-09-17: three colours, with shape carrying the rest

Decided: three colours, with shape carrying the rest. Reason: the page is to read correctly without colour and from across the room; the requirement behind the ruling is that the page can be read without relying on colour alone. Set aside: a fourth hue for what is unknown, which the same ruling showed by a hollow ring instead. Data not gathered has since been ruled to show zeroed and greyed out (the entry of 18 September 2026 below), and R10 reads that grey as outside the three colours.

## 2026-09-18: the name and the repository

Decided: the service shows "ParkviewLab Engineering Dashboard" as its display name in the top chrome of its page, and its repository is `ParkviewLab/hazel-tracking`. Reason: the repository's name is in the house naming style of a pigment and a gerund. Set aside: none recorded.

## 2026-09-18: the phases, and the scope of Phase 1

Decided: the Dashboard is built in phases, one data source at a time, each phase adding one source to a service that already runs. Phase 1 shows only what GitHub supplies, and only for the repositories of the ParkviewLab organisation; `garycoding/Development-Lab` joins in a later phase. It is a NiceGUI app in a Docker stack on the development server, whose only credential is a read-only GitHub token covering the organisation, including read access to its packages, since dev releases are read from GHCR. Phase 1 covers these requirements: whether there are working branches on the remote; whether there are open pull requests; the version of the latest dev release and of the latest final release; the status of each open pull request; from what is waiting on the reader, a release ready to cut, a branch pushed with no pull request and a back-merge not completed; whether the checks on the trunks pass; how far `develop` is ahead of `main`, and how far each working branch is behind `develop`; unreleased work, and whether any of it changes the documentation; when anything last happened, as far as GitHub records it; and the number of open issues. Reason: not recorded beyond the decision. Set aside: none recorded. The order of the later phases is not ruled.

## 2026-09-18: gathering on load, on Refresh and every ten minutes, with the data's age

Decided: nothing is pushed to the Dashboard and nothing polls. When a browser requests the page, the Dashboard asks all its sources at once, renders when the answers are in, and returns the page. The chrome carries a Refresh button that gathers fresh data on demand; the page also gathers by itself every ten minutes, only while a browser is showing it; and the chrome shows one clock for the whole page, counting in minutes and seconds how old the data on the page is. The page is not interactive, except for the Refresh button and an information icon in the status bar. Reason: the page shows how current its information is, so that a stale view cannot pass for a current one, the suggested requirement accepted in the form of the clock. Set aside: polling on a timer and keeping a cache, as in the entry of 17 September 2026.

## 2026-09-18: data not gathered, and the status bar

Decided: data the Dashboard could not gather is shown zeroed and greyed out. A status bar across the bottom of the page states the health of the last refresh: when something went wrong, it says in one brief sentence what and why, and an information icon beside it opens a dialog with the detail. Reason: when a fact cannot be determined because a source is unreachable, the page says so rather than showing "no"; this is the form in which that suggested requirement was answered. Set aside: the suggested requirement's own form, in which such a fact says, in place of its value, that it could not be determined.

## 2026-09-18: no secret shown

Decided: nothing on the page, the status bar and its dialog included, ever shows a token, a password or any other secret value; a credential may be named in general terms, such as "the GitHub token was refused". This also settles whether a token's name counts as a secret's name: the page names a credential only in general terms. Reason: not recorded beyond the decision. Set aside: the suggested requirement's form, which barred a secret's name as well as its value.

## 2026-09-18: the development network, with no login

Decided: any device on the development network can open the page, with no login, and nothing outside the network can reach it, like the lab's other services. Reason: it is treated as the lab's other services are. Set aside: a page readable from the Mac alone.

## 2026-09-18: the definitions settled for Phase 1

Decided, each with the question of definition it settles:

- Archived repositories do not appear (question 24, its archived-repository part). Reason: not recorded. Set aside: showing them; none existed when the question was asked.
- A working branch is every branch other than the repository's trunks, whoever made it: bots' branches count, and so do branches with nothing on them that `develop` lacks. The trunks are `main` and `develop`, and in the two website repositories, parkviewlab.ai and zoestum.ai, `live` and `staging` (question 3). Reason: not recorded. Set aside: leaving out a bot's branch, such as the Dependabot branch in deco-assaying, and a legacy branch identical to `develop`, such as `claude` in pvl-dotview.
- Pull requests opened by bots count as open pull requests (question 7). Reason: not recorded. Set aside: leaving them out.
- The latest final release is shown both ways: the newest version tag and the newest GitHub Release, the page highlighting a difference between them, as when a tag was pushed but its Release never created (question 8). Reason: the two differed in dev-tools and pvl-dotview when the question was asked. Set aside: the tag alone, or the Release alone.
- The latest dev release is shown only when it is newer than the latest final release, and otherwise none is shown; an Electron app's dev build still counts once its downloadable files have expired, marked as expired; work in a dev build still counts as unreleased until a final release carries it (question 9). Reason: not recorded. Set aside: showing a dev release that predates the final release, such as smalt-mcp's 1.3.3.dev1 beside its 1.3.3; leaving out a build whose files have expired; and counting the work in a dev build as released.
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

Decided: 35850. Reason: the port was free on the development server, in the block kept for the lab's own services. Set aside: none recorded.

## 2026-09-18: D3, a northstar

Decided: the repository has a northstar, `docs/northstar.md`: the draft approved on 18 September 2026, placed verbatim with the SPDX header and the copyright footer the handbook requires. Its designed HTML twin, `docs/northstar.html`, is authored with the other documents before the first release. Reason: not recorded for the northstar itself; the twin is authored because the documentation site (D4) opens its index with the northstar, which would otherwise be a Markdown link shown as source. Set aside: a northstar written with the scaffold, in place of the approved draft.

## 2026-09-18: D4, a documentation site

Decided: `docs/` is published at https://parkviewlab.github.io/hazel-tracking/, built with the other documents before the first release, so that v0.1.0 publishes it; the README's `Documentation:` line follows that release in its own pull request. Reason: not recorded beyond the decision. Set aside: no documentation site, which the plan had recommended.

## 2026-09-18: D5, dev releases

Decided: dev builds are adopted. `dev-release.yml` publishes only what hazel-tracking publishes: a GHCR image tagged `dev` and with its dev version, never `latest`, with no PyPI or TestPyPI job. A dev build is cut only when one is asked for, for instance to try a deployment on the development server before a final release; before v0.1.0, one is cut and deployed to the development server through the Portainer stack, with the token from the lab's secrets store, the release follows once that deployment is proven, and the stack then moves to the pinned release image. The dev version follows the real-merges build's rulings where they are settled (its decision 5 (b): set in the build's workspace from the newest tag, a `kind` input and the run number, with nothing committed), and R12 where they are silent; the workflow is adjusted when that build is released. Reason: a candidate can be tried in a deployment on the development server before a final release. Set aside: no dev builds, which the plan had recommended.

R12. While the repository has no `v*` tag, a dev build's target is the version `pyproject.toml` declares without its `.devN` (0.1.0 from 0.1.0.dev0), whatever the `kind` input, since there is no tag to count from and dev-tools' `sot_compute_next` would give 0.1.1. N is the run number alone, the real-merges ruling's term: a re-run republishes the same version from the same commit, which GHCR accepts. Both give way to the real-merges build's rule when that build is released.

R13. The dev image is also tagged `sha-<commit>`, as the handbook's dev `docker` part tags it and the organisation's dev images are tagged. The tag is kept: it publishes nothing beyond the one image and names the commit the image was built from.

Where `dev-release.yml` differs from the dev parts of handbook v0.25.0, and why. The file is assembled from the dev `head`, `gate` and `docker` parts, and differs from them only in the changes decision 5 (b) makes, since v0.25.0's dev gate still reads the version committed in `pyproject.toml` and the real-merges build, which carries decision 5 into the parts, is not yet released:

- The head declares the `workflow_dispatch` input `kind` (`patch`, `minor` or `major`, default `patch`), and its comment says to run the workflow with `gh workflow run dev-release.yml --ref develop -f kind=<kind>` rather than `git dev-release`, since dev-tools v1.1.0's `git dev-release` commits the dev version to `develop` and pushes it. A comment names this slot.
- The gate checks out every tag (`fetch-depth: 0`), and in place of the check that the committed version carries a dev marker, it computes the dev version: the newest `v*` tag in version order raised by `kind` as `sot_compute_next` raises a plain version, or R12's target while there is no `v*` tag, with N the run number, giving `X.Y.Z.devN`. It refuses a `kind` other than the three.
- The `docker` job installs uv and sets that version in its own workspace with `uv version "$VERSION" --no-sync` before the build, which rewrites `pyproject.toml` and `uv.lock` together, so that the image reports the dev version; nothing is committed.

The file is re-assembled from the dev parts once a handbook release carries decision 5 in them.

## 2026-09-18: D6, publishing

Decided: the image on GHCR only, `ghcr.io/parkviewlab/hazel-tracking`, tagged with the version, the major and minor, and `latest`, for amd64 and arm64; no PyPI or npm package and no installers. `release.yml` carries only the jobs for the image: the gate, `docker` and `changelog`. The README has a section on running the image with Docker and Portainer in place of the five-ways table. Reason: the design rules a Docker stack on the development server, and a PyPI package would add a trusted publisher and a publishing job for a service with one deployment, as was ruled for paper-boxing on 2026-09-15. Set aside: a package on PyPI.

## 2026-09-18: D7, the wait

Decided: a gather waits 15 s for GitHub, set by `HAZEL_TRACKING_WAIT_SECONDS`, a setting of the stack. A gather not complete within the wait shows the facts that did arrive and zeroes and greys the rest, the status bar says why, and the Dashboard tries again every minute until a gather succeeds, after which the ten-minute cycle resumes; a gather complete in time that misses some facts likewise greys only those, as the requirements rule (R8, R11). Amended the same day, with the reading R11: as first ruled, a gather not complete within the wait showed the whole page zeroed and greyed out. Reason: the design proposed a fixed wait so that one slow or unreachable source cannot hold the whole page back, whatever has not answered by then being treated as not gathered. Set aside: 20 s, which the plan had recommended.

## 2026-09-18: D8, the page

Decided: the layout the plan specifies, fitting 1470 by 800 CSS pixels (the Mac's built-in display at its current scaling, less the menu bar and a browser's toolbar) with no type smaller than 12 CSS pixels. The first pass is built with all the information and shown as it is, scrolling if it must; if it does not fit, work on the fit stops there until its solution is ruled. Nothing is dropped, shrunk or hidden to make it fit without a ruling. Reason: not recorded beyond the decision. Set aside: none recorded.

## 2026-09-18: D9, the handbook release

Decided: hazel-tracking is built on the handbook release that carries the fix choosing release and dev-release jobs by publish target, which is v0.25.0, and its templates come from that release rather than from v0.24.0. Whichever of the one-changelog-generator and real-merges builds that release carries is included, and hazel-tracking joins the repository list of any it does not; v0.25.0 carries neither, so hazel-tracking takes `cliff.toml` and `scripts/generate_changelog.py` from its templates and switches with the other repositories when each build lands. Reason: not recorded beyond the decision. Set aside: scaffolding from v0.24.0, which the plan had recommended.

## 2026-09-18: D10, the token

Decided: a classic GitHub token with `read:packages` alone, the only kind GitHub's Packages API accepts, created and stored on 18 September 2026 in the lab's secrets store as `GITHUB_TOKEN_HAZEL_TRACKING`; the service reads the environment variable of that name. It was verified that day without being displayed: its scopes are `read:packages` only; it expires on 2027-09-18; it reads the organisation's 16 repositories and its 9 container packages; a write is refused. Reason: every repository of the organisation is public, so the token reads every repository, as the scope requires, and it is read-only, as the design rules; a private repository would be absent without notice, a limit [`what-it-shows.md`](what-it-shows.md#scope) states. Set aside: none recorded.

## 2026-10-03: the handbook v2.1.1 conventions

Decided: the repository is brought to handbook v2.1.1 before its first pull request merges, with dev-tools v1.5.3's commands; the workflows pin dev-tools v1.5.1, the parts' own pin and the newest release that changed the scripts they run. `release.yml` and `dev-release.yml` are assembled by dev-tools' `assemble-workflows`, declared in `.github/workflows/.assembly.toml`, with no difference from the parts; the dev version is the parts' own (the newest `v*` tag raised by `kind`, or the version file's version while there is no tag, with N the run number times 100 plus its attempt), which replaces R12's N and the changes listed under D5. The version guard is the v2.1.1 template. git-cliff, `cliff.toml` and `scripts/generate_changelog.py` give way to dev-tools' shared `generate-changelog`. Pull requests are merged with merge commits, and a release ends with `git back-merge`. `pyproject.toml` declares 0.1.0, where the templates start, so that the first release is `git release` alone. Reason: D9's condition is met by the releases since v0.25.0, which carry the one-changelog-generator and real-merges builds. Set aside: discarding the scaffold and starting again, since its stack and contract match the rulings below.

## 2026-10-03: gathering on each page load, and nothing kept

Decided: each page load gathers, and nothing is kept, as the 2026-09-17 entry rules. Reason: it is the northstar's intent, and frequent fresh reads of the pull requests were wanted. Set aside: prima-dev-dashboard's single loop that gathers every 30 minutes and serves every page from the snapshot it keeps.

## 2026-10-03: GraphQL

Decided: GitHub is read through GraphQL, with REST for the container packages. Reason: about twice as fast on every page load (4 to 6 s measured on 2026-09-18, against prima-dev-dashboard's 11.1 s over REST on 2026-10-03), and it reads facts REST makes awkward. Set aside: REST alone, as prima-dev-dashboard reads, about 116 requests a gather.

## 2026-10-03: the wait stays 15 seconds

Decided: D7's wait of 15 s stands, a setting of the stack. Reason: it leaves room for a slow answer without a long wait when GitHub is in trouble. Set aside: prima-dev-dashboard's 30 s.

## 2026-10-03: the 30-minute cycle and the retries

Decided: the automatic gather runs every 30 minutes, in place of every ten minutes. After a gather that is not wholly successful (not complete within the wait, or complete with any call failed), the page tries again after 1 minute, and after each further attempt that is not wholly successful, after twice the previous delay: 1, 2, 4, 8 and 16 minutes; the 32-minute retry is not made, and the 30-minute cycle resumes. Any wholly successful gather, Refresh's or a page load's included, ends the retries and restarts the cycle. A gather not complete within the wait shows what arrived and greys the rest (R11, unchanged). This amends D7's retry every minute, the ten-minute cycle of 2026-09-18, and R8, under which a gather that completed within the wait counted as succeeded even when some of its calls failed. Reason: a fresh gather is always to hand by reloading the page or pressing Refresh. Set aside: a retry every minute until a gather completes.

## 2026-10-03: readiness leaves out back-merge pull requests

Decided: readiness and unreleased work follow R5 and R6, and a merged pull request whose branch name begins `back-merge-` is not unreleased work. Reason: every release leaves `develop` ahead of `main` by its back-merge pull request and the commit that opens the next dev cycle, so that without the exclusion every repository reads ready to cut the moment it is released; `git back-merge` always names its branch so. Set aside: prima-dev-dashboard's rule, ready whenever `develop` is ahead of `main`.

## 2026-10-03: checks on both trunks

Decided: the Checks column shows both trunks, each at its newest commit that has checks, passing over a `[skip ci]` head (R2). Reason: `main` is where releases are cut, and its head after every release is the changelog commit made with `[skip ci]`. Set aside: the default branch's head alone.

## 2026-10-03: the six pull-request statuses

Decided: R4's six statuses. Reason: GitHub's "blocked" covers both checks still running and a branch behind its base, which call for different actions. Set aside: prima-dev-dashboard's draft, conflicts, checks failing, blocked, pending, ready.

## 2026-10-03: a branch's open pull request, linked

Decided: each working branch shows its lag and, where a pull request is open from it, that pull request's number, linked to it; a branch with none carries no mark. "A branch pushed with no pull request" is no longer among what waits on the reader. Reason: branches are created on GitHub first and pushed throughout the work, so a branch with no pull request is work in progress. Set aside: marking a branch that has no open pull request, ruled earlier the same day and reversed.

## 2026-10-03: dev releases from GHCR alone

Decided: Phase 1 reads dev releases from GHCR alone; installer dev builds are an in-flight idea. Reason: the `installers` job of the present `dev-release.yml`, which conception-space and pensa-grex carry, had never run (conception-space's last installer dev build, from its earlier `dev-release-electron.yml`, ran on 2026-07-20 and is older than its release), and reading such builds is a large share of the gathering. Set aside: the plan's reading of installer dev builds from workflow runs, with their expiry.

## 2026-10-03: the status bar, the dialog and the endpoints

Decided: problems are reported by one status sentence and an information icon that opens a dialog of every problem's detail; the status bar also gives GitHub's rate limit remaining and its reset, and the count of archived repositories not shown. The endpoints are `/`, `/health` and `/admin/version`. Reason: a bad gather can yield many problems, which listed beneath the table would push it off the screen. Set aside: prima-dev-dashboard's list of problems beneath the table, and its `GET /api/state`.

## 2026-10-03: the chrome

Decided: the ParkviewLab logo at the left, "ParkviewLab Engineering Dashboard" with the service's version, and Michroma vendored in the image, never fetched; the logo and the font are vendored from the handbook's brand as paper-boxing has them, outside the repository's dual licence. Reason: the logo and the version as prima-dev-dashboard shows them, and no request outside the network on each load. Set aside: the name "Prima Dev Dashboard", and the font fetched from Google Fonts.

## 2026-10-03: two of the columns

Decided: the heading "Tag / Release" for the final release, and the last push shown as the time since it up to 36 hours and as the date after that. Reason: the cell shows the tag and the Release both, and a relative time reads faster in a column scanned for recent activity. Set aside: "Final release", and the time of the last push in the lab's time zone.

## 2026-10-03: D8 amended, the width

Decided: the page fits the width of 1470 CSS pixels with no type under 12 px; its height grows with the number of repositories, and it scrolls. Reason: the height depends on how many repositories the organisation has. Set aside: the whole page within 1470 by 800.

## 2026-10-03: three tabs

Decided: the page has three tabs, Overview, Detail and Pull requests, under one chrome; switching tabs gathers nothing; the overview is distilled from the detail's gather; Refresh sits above the tabs. The overview fits one screen and shows per repository the release state, readiness and what waits on the reader; the detail scrolls within its tab. The northstar is amended the same day to three intents, one per tab. Reason: two needs pull in different directions, one screen of what needs attention and every fact for every repository, and the open pull requests are watched on their own. Set aside: three separate addresses, each gathering what it shows.

## 2026-10-03: the pull-requests tab, its Refresh and its Watch

Decided: the tab lists every open pull request into a repository's integration trunk except those from `back-merge-` branches, Dependabot's included. It is gathered by one GraphQL search, which cost 1 point and took 0.6 to 0.7 s when measured on 2026-10-03 (the same facts read repository by repository cost 51 points). The tab has its own Refresh and a Watch that gathers every 10 seconds and stops on a new or closed pull request, after 10 minutes, on leaving the tab or on closing the page, marking the browser tab's title when it stops on a change. Reason: prima-dev-dashboard's PRs button was pressed often while an agent was about to open a pull request; a cheap gather keeps that within GitHub's hourly budget. Set aside: the PRs button on the main table, a refresh every 30 seconds while the tab is shown (too slow), and one every 10 seconds at all times (too costly).

## 2026-10-03: the busy spinner

Decided: a large busy spinner is overlaid on the page while any gather runs; the page is drawn first and filled when the gather returns. Reason: each page load waits for a gather. Set aside: holding the response until the gather returns.

## 2026-10-03: the port inside the container

Decided: 35850 inside the container as well as outside. Reason: the port in a health check, a log line or `/admin/version` is the one opened in the browser. Set aside: prima-dev-dashboard's 8000 inside, published as 35850.

## 2026-10-03: the deployment

Decided: a Portainer stack on the development server, with a dev build tried there first (D5); prima-dev-dashboard keeps running until the release there is verified. Reason: the development server is where the lab's services run, backed up and documented, reachable from any machine on the development network. Set aside: Docker on the Mac, as prima-dev-dashboard runs.

## 2026-10-03: the northstar's three intents

Decided: the northstar is amended to three intents, one per tab (the overview, the detail, the pull requests), with the trade-off between the overview and the detail stated; the former intents "True as of now" and "Private and read-only" become axioms 2 and 7, and once the Atlas generator groups the repositories, the overview gives one screen per grouping. Reason: the two needs and the third view, as the entry on the three tabs records. Set aside: the single intent "Everything at once", as first amended the same day for a page that grows in height.

## 2026-10-03: links, and the elements one can use

Decided: each repository's name and each pull request's number link to it on GitHub, as prima-dev-dashboard links them, and the interactive elements are the Refresh button, the three tabs, the pull-requests tab's Refresh and Watch, the information icon, and those links. This amends the 2026-09-18 entry under which the page was not interactive except for the Refresh button and the information icon. The pull-requests tab carries the time of its own gather beside the chrome's age of the full gather. Reason: the columns were taken as prima-dev-dashboard has them, and the pull-requests tab is gathered on its own. Set aside: none recorded.

## 2026-10-03: which gathers run, and the spinner

Decided: opening the page and the chrome's Refresh run both gathers, the full gather and the gather of the open pull requests; switching tabs gathers nothing. The 30-minute cycle and its retries apply to the full gather alone, and the pull-requests tab's own Refresh and Watch leave that cycle alone. The spinner covers the page while it is opened, while Refresh runs and while the tab's own Refresh runs, and not during the Watch's gathers, whose button shows that it is watching. Reason: the pull-requests tab must hold its data before it is first shown, and a spinner every 10 seconds would cover the page for up to 10 minutes. Set aside: the pull-requests tab gathering when first selected.

## 2026-10-03: what waits on the reader, on the overview

Decided: on the overview, what waits on the reader is a release ready to cut, a pending back-merge, checks failing on either trunk, open pull requests that are ready to merge, in conflict, failing their checks or behind their base, and open issues. A repository with none of these is shown quietly, with its release state and its readiness; a fact not gathered counts as waiting. Reason: cutting a release needs the reader's ask and an incomplete back-merge needs attention, as the requirements of 2026-09-18 list them. Set aside: readiness shown apart from what waits.

## 2026-10-03: the northstar's fourth intent, its sources, and an eighth axiom

Decided: the northstar gains a fourth intent, "Safe to leave open" (every view read-only and private, serving the development network alone and showing no secret), from which axioms 6 and 7 follow; the overview's and the detail's intents are worded by source rather than by repository, so that a later phase extends them rather than rewriting them; an eighth axiom rules that one source's failure never hides another's. "Not a monitoring system" becomes "Not an alerting system", since the reader monitors the work with the page. Reason: the axioms on secrets and the network followed from none of the three intents, and the later phases add sources (services, development machines) that fail independently. Set aside: none recorded.

## 2026-10-03: the token's expiry, and a watch on one pull request

Decided: the status bar shows when the GitHub token expires, as GitHub's answers report it, in yellow within 30 days of its expiry; and a watch may be started from one pull request's row, stopping also when that pull request's status changes. Reason: an expired token would leave the whole page ungathered, and waiting for a pull request's checks is as common as waiting for a new pull request. Set aside: none recorded.

## 2026-10-03: a spinner for every gather, and the readings the built page settled

Decided, when the page was built and reviewed: every gather shows a spinner over a scrim, a translucent dimming of what lies beneath it and not the grey that marks data not gathered. A full gather, whatever started it, the automatic gather and its retries included, shows the large spinner over the whole page; a gather of the open pull requests alone, the tab's own Refresh and each of the Watch's gathers, shows a spinner filling the pull-requests tab's frame alone, so that the chrome and the tabs stay usable and the reader can leave for another view. This amends the entry of 2026-10-03 on the busy spinner, under which the automatic gather and the Watch's gathers showed none. Reason: a gather that shows nothing cannot be told from a page that has stopped, and the Watch's gather is cheap enough to leave the rest of the page alone while it runs. Set aside: no spinner for the automatic gather and the Watch, as first ruled.

Ruled with it, as the readings R14 to R20 of [`what-it-shows.md`](what-it-shows.md): readiness fails on the checks only where the newest commit whose checks have finished failed them, so checks still running are passed over (R14); a trunk's history is read ten commits deep, so a trunk whose last ten commits all lack checks reads none (R15); the dev release is read against the final release, so where the final release was not gathered the dev release is not gathered either (R16); the rate limit in the status bar is GraphQL's own budget, not the budget of the REST calls that read the container packages (R17); a repository whose default branch could not be read shows "none" for its trunk rather than an empty name (R18); on the overview a release ready to cut and a pending back-merge are the readiness indicator's own words and are shown once, in readiness, the line's not being quiet marking the repository as waiting (R19); and the pull-requests tab's own Refresh does not stop a running watch, which stops only by the rules the specification gives and goes on comparing against the set it was started on (R20). The Constraints list of interactive elements gains the Watch on each pull request's row and the dialog's Close. Reason: each was a question the page's building reached and the specification had left open. Set aside: none recorded.

## 2026-10-03: the comparisons are read over REST

Decided: the trunk comparison of each repository and the lag of each working branch are read over REST's comparison of two commits, `GET /repos/{owner}/{repo}/compare/{base}...{head}`, and not over GraphQL's `Ref.compare`; what the compared commits belong to is still read over GraphQL, by the oids REST gives. Reason: GraphQL refuses `aheadBy`, `behindBy` and `status` to a token without the `repo` scope, and the Dashboard's token holds `read:packages` alone, by D10, so that it cannot write; the refusal came in the live gather of 3 October 2026, with status 200 and the message that the field requires the `repo` scope, and it cost the unreleased work, the readiness, the pending back-merge and every branch's lag in every repository. REST's comparison answers the same facts to the same token, which was checked the same day. Set aside: giving the token the `repo` scope, which would make it a token that can write, against the design.

## 2026-10-03: the status sentence's count, and the tab's Watch during a watch on one pull request

Decided, as built, with the readings R21 and R22 of [`what-it-shows.md`](what-it-shows.md): the status sentence names the problems of both gathers while there are at most two, and counts them beyond that ("3 facts could not be gathered"), the dialog listing every problem (R21); and while a watch on one pull request runs, the tab's Watch reads "Watching", and pressing it cancels that watch and starts a fresh watch of the whole set, compared with the list the tab then holds, with its own ten minutes (R22). Reason: not recorded beyond the ruling that the page as built stands. Set aside: none recorded.

---
<sub>© 2026 Gary Frattarola · Licensed under [MIT](../LICENSE-MIT) OR [Apache-2.0](../LICENSE-APACHE) · part of [ParkviewLab](https://github.com/ParkviewLab)</sub>
