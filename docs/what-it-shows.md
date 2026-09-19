<!--
SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# hazel-tracking: what the page shows

This is the specification of the page hazel-tracking serves, and the repository's authority for what it shows: an unintended disagreement between it and the code is a defect in the code, and a change to what the page shows amends this document in the same pull request. The rulings behind it, with their dates and reasons, are in [`decisions.md`](decisions.md), and the intent it serves is in [`northstar.md`](northstar.md). The readings R1 to R11 settle what the rulings leave open; each is labelled where it applies.

## Purpose and reader

The page lets one person see what is going on now and the state of every project, in a single browser window, without scrolling or clicking. It has one reader.

## Scope

Every repository of the ParkviewLab organisation that is not archived appears, as one row, whether or not anything is happening in it. Archived repositories do not appear.

The page shows only what GitHub supplies. The lab's services, its development machines, BookStack and `garycoding/Development-Lab` are outside this version; the later phases that would add them are a proposal ([`in-flight_ideas.md`](in-flight_ideas.md)).

GitHub is read with a classic token that holds `read:packages` alone (D10). Every repository of the organisation is public and the token reads every public repository, so every repository appears; a private repository would be absent from the page without notice, since the token cannot read it.

## The page

One page, at `/`. The chrome across the top carries the display name "ParkviewLab Engineering Dashboard", the age of the data and the Refresh button. Below it is one table, a row per repository in name order. A status bar runs across the bottom.

## Trunks and working branches

A repository's trunks come from its default branch: `develop` gives `main` and `develop`, `staging` gives `live` and `staging`, and `main` gives `main` alone, with no comparison and no readiness. In each pair the first is the release trunk and the second the integration trunk. Every other branch is a working branch, whoever made it: bots' branches count, and so do branches with nothing on them that the default branch lacks. Wherever this document says "behind `develop`", it means behind the default branch. (R1)

## The columns

Each row holds these columns, in this order. Three of them carry what is waiting on the reader: a release ready to cut and a back-merge not completed, in Release, and a branch pushed with no pull request, in Working branches.

### Repository

The repository's name.

### Last push

When anything last happened, shown as the time of the last push to any branch, labelled as the last push, in the lab's time zone.

### Issues

The number of open issues. It counts issues only: GitHub's own figure for open issues also includes open pull requests, which are listed separately.

### Final release

The latest final release, shown both ways: the newest version tag and the newest GitHub Release. Where the two differ, as when a tag was pushed but its Release never created, the page highlights the difference. The newest version tag is the highest `vX.Y.Z` by version, not by date; the newest Release is GitHub's latest Release. (R3)

### Dev release

The latest dev release, shown only when it is newer than the latest final release; otherwise none is shown. It is compared with the higher of the newest tag and the newest Release, and a repository with several packages takes the highest dev version among them. (R3)

A dev release is one that GitHub holds: an image on GHCR tagged `dev`, whose dev version is the tag beside `dev`, or an Electron app's dev build, whose installers a dev workflow keeps as the artefacts of its run. Such a build still counts once its downloadable files have expired, marked as expired. Work in a dev build still counts as unreleased until a final release carries it. Dev releases published only to TestPyPI or npm are not read, since this version reads GitHub alone. (R9)

### Unreleased

The unreleased work: the merged pull requests that no release carries yet. It counts distinct merged pull requests among the commits the integration trunk has and the release trunk lacks; direct commits are not counted. How far `develop` is ahead of `main` is measured in the same merged pull requests, so the two are one number, shown on one line.

The count carries the documentation mark when any of those pull requests changes the documentation. Documentation means the files the repository's documentation site is built from, those under `docs/` and `site/`. The README does not count, since GitHub shows it from `develop` as soon as a pull request merges; the mark therefore means that the published documentation site is behind `develop`. The mark applies in every repository. (R5)

A repository whose default branch is its only trunk has no comparison, and this column is empty for it.

### Release

For a repository whose trunks are `main` and `develop`, the single indicator "ready to cut a release". It reads ready when three conditions hold: at least one merged pull request is not in the latest final release (documentation-only work counts, and the indicator notes when documentation is included); the checks on `develop` pass, judged on its latest commit that ran checks; and the previous release's back-merge is complete, so that `main` holds nothing `develop` lacks. The latest commit that ran checks is the newest commit on `develop` whose checks have finished; a commit whose checks are still running is passed over (R2). When a condition fails, the indicator names it: nothing to release, checks failing on `develop`, or the back-merge pending; when several fail, it names every one (R6).

The indicator does not appear for the two website repositories, parkviewlab.ai and zoestum.ai, which deploy from `staging` to `live` and have no release tags. For them this column shows a pending back-merge instead: `live` holding commits `staging` lacks (R6). A repository whose default branch is its only trunk shows neither.

### Checks

Whether the checks on each trunk pass: passing, failing, running or none, judged on the trunk's newest commit that has any checks, finished or running. (R2)

### Working branches

Each working branch, with how far it is behind `develop`, measured in commits: the commits on `develop` that the branch does not have. A branch pushed with no open pull request is marked.

### Pull requests

Each open pull request, by number, with its status as GitHub reports it. Pull requests opened by bots count. Only open pull requests are listed: merged and closed ones are not, and merged ones appear only in the count of unreleased work. The page does not say whose turn it is.

The status is the first that applies of: draft, conflicts, checks failing, checks running, behind its base, ready to merge. A status GitHub has not yet computed (`UNKNOWN`) is read once more, and if it is still not computed, it is shown as not gathered. (R4)

## When the page gathers

The service stores nothing. When the page is requested, it gathers what the page shows from GitHub, renders the page from the answers and returns it, so what the page shows is current as of that request. The Refresh button gathers again on demand, and the page gathers again by itself while it is open.

The next automatic gather falls due ten minutes after the last gather began, whatever started it, or one minute after it began if it did not complete within the wait, so that the page tries again every minute until a gather completes and the ten-minute cycle then resumes. A gather that completes within the wait counts as succeeded even when some of its calls failed; the facts those calls feed are greyed (R7). The chrome shows one clock for the whole page, counting in minutes and seconds how old the data is, from the moment the last gather began, whether or not it completed. Times are shown in the lab's time zone. (R8)

## The wait

A gather waits for GitHub at most the configured wait, `HAZEL_TRACKING_WAIT_SECONDS`, 15 s by default; the wait is a setting of the stack (D7).

A gather not complete within the wait shows the facts that did arrive, those whose calls had answered within the wait, and nothing from an earlier gather, which is not kept. Each repository whose name had arrived is a row, with every fact that arrived shown as gathered and every other fact zeroed and greyed as R7 reads it. If the list of repositories had not arrived, the table shows its columns and no rows. The status bar says that GitHub did not answer within the wait and that the page tries again each minute, and the dialog names each call still outstanding. (R11)

## Data not gathered and the status bar

Data that could not be gathered is shown zeroed and greyed out. Zeroed means 0 for a count, "no" for a yes-or-no fact and an empty value for a version or a state, each in grey. A fact gathered and found empty, such as no release or no branch, reads "none" in ordinary type. (R7)

The status bar states the health of the last gather. When something went wrong, it says in one brief sentence what and why, and an information icon beside it opens a dialog with the detail of each problem.

## Colour and shape

Three colours carry state, from the brand: sage for passing and ready, yellow for running and pending, and red for failing and conflicts. Each state also carries its own word or shape, so that every state reads without colour. Grey, for data not gathered, and the chrome's deep teal, the brand's frame, carry no state and are not among the three. (R10)

## Constraints

- The page fits in a single browser window, with no scrolling: 1470 by 800 CSS pixels, the Mac's built-in display at its current scaling less the menu bar and a browser's toolbar, with no type smaller than 12 CSS pixels (D8).
- It needs no clicking: everything is visible at once.
- It is not interactive, except for the Refresh button in the chrome and the information icon in the status bar.
- It stores and manages no data of its own, and it never writes to GitHub.
- Nothing on the page, the status bar and its dialog included, ever shows a token, a password or any other secret value; a credential may be named in general terms, such as "the GitHub token was refused".
- Any device on the home network can open it, with no login, and nothing outside the network can reach it, like the lab's other services.

---
<sub>© 2026 Gary Frattarola · Licensed under [MIT](../LICENSE-MIT) OR [Apache-2.0](../LICENSE-APACHE) · part of [ParkviewLab](https://github.com/ParkviewLab)</sub>
