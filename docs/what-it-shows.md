<!--
SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# hazel-tracking: what the page shows

This is the specification of the page hazel-tracking serves, and the repository's authority for what it shows: an unintended disagreement between it and the code is a defect in the code, and a change to what the page shows amends this document in the same pull request. The rulings behind it, with their dates and reasons, are in [`decisions.md`](decisions.md), and the intent it serves is in [`northstar.md`](northstar.md). The readings R1 to R11 settle what the rulings leave open; each is labelled where it applies.

## Purpose and reader

The page has one reader and serves three needs, one tab each: an overview that shows on one screen what needs the reader's attention and the release state of every repository; the detail, every fact for every repository, which may scroll; and the open pull requests, to watch work arrive.

## Scope

Every repository of the ParkviewLab organisation that is not archived appears, whether or not anything is happening in it. Archived repositories do not appear; the status bar gives their count.

The page shows only what GitHub supplies. The lab's services, its development machines, BookStack and `garycoding/Development-Lab` are outside this version; the later phases that would add them are a proposal ([`in-flight_ideas.md`](in-flight_ideas.md)).

GitHub is read with a classic token that holds `read:packages` alone (D10). Every repository of the organisation is public and the token reads every public repository, so every repository appears; a private repository would be absent from the page without notice, since the token cannot read it.

## The page

One page, at `/`. The chrome across the top carries the ParkviewLab logo, the display name "ParkviewLab Engineering Dashboard" with the service's version, the age of the data, and the Refresh button. Below it are three tabs, Overview, Detail and Pull requests, and a status bar runs across the bottom. Switching tabs gathers nothing: the overview and the detail show the same gather, and the pull-requests tab shows its own.

While any gather runs, a large busy spinner is overlaid on the page. The page is drawn first, with its chrome and the spinner, and filled in place when the gather returns.

## Trunks and working branches

A repository's trunks come from its default branch: `develop` gives `main` and `develop`, `staging` gives `live` and `staging`, and `main` gives `main` alone, with no comparison and no readiness. In each pair the first is the release trunk and the second the integration trunk. Every other branch is a working branch, whoever made it: bots' branches count, and so do branches with nothing on them that the default branch lacks. Wherever this document says "behind `develop`", it means behind the default branch. (R1)

## The overview

One screen, a repository each, distilled from the detail's gather. For each repository it shows:

- the release state: the newest final version (the higher of the newest tag and the newest Release, R3), and the dev release where it is newer;
- readiness, as the detail's Release column reads it: ready to cut, with the count of unreleased pull requests and the documentation note; or each condition that fails; or, for the two website repositories, a pending back-merge;
- what waits on the reader: the trunks whose checks fail; the open pull requests counted by each status that calls for the reader (ready to merge, conflicts, checks failing, behind its base); and the number of open issues.

A repository with nothing waiting on the reader is shown quietly, with its release state alone, so that the eye goes to those that need something. A fact that could not be gathered counts as waiting: what is unknown is shown, not hidden. Everything else (the last push, the branches and their lag, the tag and the Release told apart, the individual pull requests) is on the detail tab.

## The detail

One table, a row per repository in name order, with these columns in this order. The table is as wide as the window and scrolls vertically within its tab.

### Repository

The repository's name, linked to it on GitHub.

### Last push

When anything last happened, shown as the time since the last push to any branch ("6 min ago", "34 h ago") up to 36 hours, and as the date after that.

### Issues

The number of open issues. It counts issues only: GitHub's own figure for open issues also includes open pull requests, which are listed separately.

### Tag / Release

The latest final release, shown both ways: the newest version tag and the newest GitHub Release. Where the two differ, as when a tag was pushed but its Release never created, the page highlights the difference. The newest version tag is the highest `vX.Y.Z` by version, not by date; the newest Release is GitHub's latest Release. (R3)

### Dev

The latest dev release, shown only when it is newer than the latest final release; otherwise none is shown. It is compared with the higher of the newest tag and the newest Release, and a repository with several packages takes the highest dev version among them. (R3)

A dev release is an image on GHCR tagged `dev`, whose dev version is the tag beside `dev`. Work in a dev build still counts as unreleased until a final release carries it. Dev releases published only as installers kept with a dev workflow's run, or only to TestPyPI or npm, are not read in this version. (R9, as amended on 2026-10-03)

### Unreleased

The unreleased work: the merged pull requests that no release carries yet. It counts distinct merged pull requests among the commits the integration trunk has and the release trunk lacks, leaving out the pull requests from `back-merge-` branches, which `git back-merge` opens at the end of every release and which also carry the commit that opens the next dev cycle; direct commits are not counted. How far `develop` is ahead of `main` is measured in the same merged pull requests, so the two are one number, shown on one line.

The count carries the documentation mark when any of those pull requests changes the documentation. Documentation means the files the repository's documentation site is built from, those under `docs/` and `site/`. The README does not count, since GitHub shows it from `develop` as soon as a pull request merges; the mark therefore means that the published documentation site is behind `develop`. The mark applies in every repository. (R5, as amended on 2026-10-03)

A repository whose default branch is its only trunk has no comparison, and this column is empty for it.

### Release

For a repository whose trunks are `main` and `develop`, the single indicator "ready to cut a release". It reads ready when three conditions hold: at least one merged pull request is unreleased as the Unreleased column counts it (documentation-only work counts, and the indicator notes when documentation is included); the checks on `develop` pass, judged on its latest commit that ran checks; and the previous release's back-merge is complete, so that `main` holds nothing `develop` lacks. The latest commit that ran checks is the newest commit on `develop` whose checks have finished; a commit whose checks are still running is passed over (R2). When a condition fails, the indicator names it: nothing to release, checks failing on `develop`, or the back-merge pending; when several fail, it names every one (R6).

The indicator does not appear for the two website repositories, parkviewlab.ai and zoestum.ai, which deploy from `staging` to `live` and have no release tags. For them this column shows a pending back-merge instead: `live` holding commits `staging` lacks (R6). A repository whose default branch is its only trunk shows neither.

### Checks

Whether the checks on each trunk pass, the release trunk first: passing, failing, running or none, judged on the trunk's newest commit that has any checks, finished or running; a head commit made with `[skip ci]`, such as a release's changelog commit on `main`, is passed over. (R2)

### Branches

Each working branch, with how far it is behind `develop`, measured in commits: the commits on `develop` that the branch does not have. Where a pull request is open from the branch, its number is shown beside it, linked to it. A branch with no pull request carries no mark: branches are created on GitHub first and pushed throughout the work, so a branch with no pull request is work in progress.

### Pull requests

Each open pull request, by number and linked to it, with its status as GitHub reports it. Pull requests opened by bots count. Only open pull requests are listed: merged and closed ones are not, and merged ones appear only in the count of unreleased work. The page does not say whose turn it is.

The status is the first that applies of: draft, conflicts, checks failing, checks running, behind its base, ready to merge. A status GitHub has not yet computed (`UNKNOWN`) is read once more, and if it is still not computed, it is shown as not gathered. (R4)

## The pull requests

Every open pull request into a repository's integration trunk across the organisation, Dependabot's included, except those from `back-merge-` branches, on one list: each with its repository, its number and title linked to it, and its status as R4 reads it. The tab carries the time of its own gather.

The tab has two buttons of its own. Refresh gathers the open pull requests alone, by one search, which costs GitHub one point. Watch gathers them every 10 seconds and stops when the set of open pull requests changes (a pull request, by repository and number, appears or disappears), after 10 minutes, when the reader leaves the tab, or when the page is closed; moving to another browser tab or another application does not stop it. While it watches, the button says so, and pressing it again cancels the watch. When the watch stops on a change, the browser tab's title marks it (for example "1 new pull request") and the tab shows the pull request that arrived or left.

## When the page gathers

The service stores nothing. When the page is opened, it gathers what the overview and the detail show from GitHub and fills the page from the answers, so what the page shows is current as of that gather. The Refresh button in the chrome gathers again on demand, and the page gathers again by itself while it is open.

The automatic gather runs 30 minutes after the last gather began, whatever started it. A gather is wholly successful when it completed within the wait and no call failed. After a gather that is not wholly successful, the page tries again 1 minute after it began, and after each further attempt that is not wholly successful, twice the previous delay: 1, 2, 4, 8 and 16 minutes, about 31 minutes in all, after which the 30-minute cycle resumes. Any wholly successful gather, the Refresh button's or a page load's included, ends the retries and restarts the 30-minute cycle from that gather. A gather that completes within the wait with some calls failed shows what it gathered and greys the facts those calls feed (R7). The chrome shows how old the overview's and the detail's data is, counting from the moment their gather began; times are shown in the lab's time zone. (R8, as amended on 2026-10-03)

## The wait

A gather waits for GitHub at most the configured wait, `HAZEL_TRACKING_WAIT_SECONDS`, 15 s by default; the wait is a setting of the stack (D7).

A gather not complete within the wait shows the facts that did arrive, those whose calls had answered within the wait, and nothing from an earlier full gather, which is not kept. Each repository whose name had arrived is shown, with every fact that arrived shown as gathered and every other fact zeroed and greyed as R7 reads it. If the list of repositories had not arrived, the detail shows its columns and no rows. The status bar says that GitHub did not answer within the wait and when the page tries again, and the dialog names each call still outstanding. (R11)

## Data not gathered and the status bar

Data that could not be gathered is shown zeroed and greyed out. Zeroed means 0 for a count, "no" for a yes-or-no fact and an empty value for a version or a state, each in grey. A fact gathered and found empty, such as no release or no branch, reads "none" in ordinary type. (R7)

The status bar states the health of the last gather in one sentence, such as "Gathered from GitHub at 14:03:12 in 3.1 s", with GitHub's rate limit remaining and when it resets, and the number of archived repositories not shown. When something went wrong, the sentence says what and why, and an information icon beside it opens a dialog with the detail of each problem.

## Colour and shape

Three colours carry state, from the brand: sage for passing and ready, yellow for running and pending, and red for failing and conflicts. Each state also carries its own word or shape, so that every state reads without colour. Grey, for data not gathered, and the chrome's deep teal, the brand's frame, carry no state and are not among the three. (R10)

## Constraints

- The page fits the width of a browser window 1470 CSS pixels wide, the Mac's built-in display at its current scaling, with no type smaller than 12 CSS pixels. The overview fits one screen, 1470 by 800 CSS pixels (that display less the menu bar and a browser's toolbar); the detail and the pull requests grow in height only as their contents grow, and scroll within their tabs. (D8, as amended on 2026-10-03)
- The interactive elements are the Refresh button, the three tabs, the pull-requests tab's Refresh and Watch, the information icon in the status bar, and the links to GitHub.
- It stores and manages no data of its own, and it never writes to GitHub.
- Nothing on the page, the status bar and its dialog included, ever shows a token, a password or any other secret value; a credential may be named in general terms, such as "the GitHub token was refused".
- Any device on the development network can open it, with no login, and nothing outside the network can reach it, like the lab's other services.

---
<sub>© 2026 Gary Frattarola · Licensed under [MIT](../LICENSE-MIT) OR [Apache-2.0](../LICENSE-APACHE) · part of [ParkviewLab](https://github.com/ParkviewLab)</sub>
