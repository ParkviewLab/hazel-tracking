<!--
SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# hazel-tracking: architecture

## What it is

hazel-tracking is the ParkviewLab Engineering Dashboard: one page, in three tabs, of the present state of every repository of the organisation, gathered from GitHub each time it is opened or refreshed, and every 30 minutes while it is open, and stored nowhere. Why it exists is stated in [`northstar.md`](northstar.md); what the page shows, fact by fact, is specified in [`what-it-shows.md`](what-it-shows.md), the repository's authority for it, whose readings this document cites where it relies on one; the dated record of the choices is [`decisions.md`](decisions.md); and how the image is run is [`deployment.md`](deployment.md). This document describes how the software is put together and why.

## The service and its two gathering entry points

The service is one Python process in one container: a NiceGUI application, served by uvicorn, listening on port 35850 inside the container and outside it. `python -m hazel_tracking` reads the configuration from the environment (`config.py`), refuses to start without the GitHub token, with exit status 2 and one line naming the variable, and otherwise calls `app.install()` and `app.run()`. `install()` registers the two operational endpoints, `/health` and `/admin/version`, and the page at `/`; `run()` starts the server with one process and no reloading. There is no database, no cache, no volume and no background work: nothing runs except on behalf of a page a browser has open.

Everything the page shows comes from two functions of `gather.py`, the only entry points into the gathering:

- `gather(cfg, client)` returns a `Snapshot`, the full gather: every non-archived repository with each of its facts, the count of archived repositories, the problems, GitHub's rate limit, and when the token expires. The overview and the detail tabs show it.
- `gather_pull_requests(cfg, client)` returns a `PullRequestsSnapshot`: the open pull requests alone, with their own problems and rate limit. The pull-requests tab and its watch show it.

`install()` binds each to a function of no arguments that the page awaits. Each call opens one `httpx.AsyncClient` (GitHub's API as its base address, the token in its `Authorization` header and nowhere else, `hazel-tracking/<version>` as its user agent, and httpx's timeout set to the wait), runs the gather through it, and closes it. httpx's timeout bounds each phase of a call (connecting, sending, reading, and waiting for a connection from the pool) separately; the bound on the gather as a whole is the wait, below. No client, connection or answer outlives the gather that made it.

## How the page is made

The page is built afresh for each browser that connects, as one `Dashboard` object inside NiceGUI's `ui.page`, so that nothing belonging to one browser lives at module level or is shared with another. It is drawn first, before anything is gathered: the chrome (the ParkviewLab mark, "ParkviewLab Engineering Dashboard" with the version, the age of the data and Refresh), the three tabs, the status bar, and the busy spinner already over the page. As soon as the browser has connected, the page runs both gathers concurrently, and each fills its own part of the page in place when it returns: the full gather the overview, the detail and the status bar, the gather of the open pull requests the pull-requests tab. The page never holds its response while a gather runs.

There are two gathers and no more. Opening the page and the chrome's Refresh run both; the pull-requests tab's own Refresh and its watch run the gather of the open pull requests alone; the automatic gather runs the full gather alone. Switching tabs gathers nothing: the overview is derived from the full gather's snapshot by `overview.py`, a pure function with no gather of its own, and the three tabs show the two snapshots the page already holds. Those two snapshots and, while a watch runs, the list it compares with, in memory, for as long as the page is open, are all the service ever keeps.

While a gather runs, its spinner covers the ground it will fill, which is dimmed beneath it by a translucent scrim, not by the grey that marks data not gathered: the large spinner over the whole page for each full gather, whatever started it, the automatic gather and its retries included; and a spinner filling the pull-requests tab's frame for each gather of the open pull requests, the watch's included, so that the chrome and the other tabs stay usable. The tab's scrim takes no pointer, so that the tab's own controls stay within reach while the watch gathers. The chrome's Refresh is disabled while a full gather runs. A full gather's result is applied only while it is the newest, so that one overtaken by a later full gather is dropped rather than drawn over it, and the retries cannot skip a step; a gather still running when the browser leaves is dropped on its return.

A gather that raises before it finishes is read as a gather that did not complete: the page shows a problem saying that the gather failed and naming only the kind of the error, never its message or a traceback.

Every timer belongs to the browser's connection: the clock that ages the data each second, the automatic gather and the watch. Closing the page stops all three, and no two browsers share one; each open page runs its own gathers on the same token.

## Each fact's call

GitHub is read through GraphQL, with REST for two things: the container packages, which GraphQL does not expose (decided on 2026-10-03, "GraphQL", which rules REST for the packages alone), and the comparisons, which GraphQL refuses this token (decided on 2026-10-03, "the comparisons are read over REST"). Only the package `hazel_tracking.github` names GitHub's interfaces: `queries.py` holds the GraphQL documents, `calls.py` the HTTP mechanics, `facts.py` the derivations R1 to R6 rule as pure functions of GitHub's answers, `full.py` and `pull_requests.py` the two collections, and `problems.py` the wording of every problem.

| Facts | Call | Interface |
|---|---|---|
| Every repository: its name, archived or not, default branch, last push, open issues, newest Release, every tag and branch, the recent history of each trunk with its check rollups (R2), and its open pull requests with what R4 reads | the `Repositories` query, 25 repositories a page in name order, the tags and the branches 100 to a page and the open pull requests 50, each read to its end, and each trunk's history ten commits deep (R15); `RepositoryRefs` and `RepositoryPullRequests` for a list that runs past its first page | GraphQL |
| How far the integration trunk is ahead of the release trunk, the commits it is ahead by, and whether the release trunk holds anything it lacks (a pending back-merge) | `GET /repos/<org>/<repo>/compare/<release>...<integration>`, one a repository with two trunks, read 100 commits a page | REST |
| Each working branch's lag behind the default branch | `GET /repos/<org>/<repo>/compare/<integration>...<branch>`, one a working branch, one commit a page, since only `behind_by` is read | REST |
| The merged pull requests among the unreleased commits, with the branch each is from (R5) | `CommitPullRequests`, the commits named by the oids REST's comparison gave, 50 to a query | GraphQL |
| Whether the unreleased work changes the documentation (R5) | `PullRequestFiles`, the changed files of each unreleased pull request, 20 pull requests to a query and 100 files a page, with `PullRequestFilesPage` for the rest of a long one; reading stops at the first file under `docs/` or `site/` | GraphQL |
| A pull request's status GitHub had not yet computed (R4's second read) | `PullRequestStatuses`, 20 pull requests to a query | GraphQL |
| The open pull requests, for the pull-requests tab | `OpenPullRequests`, one search, `org:<org> is:pr is:open archived:false`, 100 a page | GraphQL |
| The dev releases (R3, R9) | `GET /orgs/<org>/packages?package_type=container`, then `GET /orgs/<org>/packages/container/<package>/versions` for each package, 100 a page | REST |

The comparisons are REST's because GraphQL's `Ref.compare` refuses `aheadBy`, `behindBy` and `status` to a token without the `repo` scope, which this token, by D10, does not hold (decided on 2026-10-03, "the comparisons are read over REST"). What the compared commits belong to is still read over GraphQL, by their oids, and the files are read once for each unreleased pull request rather than once for each of its commits. GitHub lists 250 commits of a comparison only when the comparison is not paged; the gather pages it, 100 commits a page, up to the guard of 20 pages. Where the comparison runs past the guard, or GitHub stops listing before the total it gives, the unreleased count and the documentation mark are not gathered, and a problem says how many of how many commits were listed. The container packages are REST's because GraphQL does not expose them at all.

The full gather sends each call once what it depends on has answered. The repositories query, page by page, runs beside the packages, whose versions are read, package by package and concurrently, once the list of packages has answered. When the repositories have arrived, the rest of any list that ran past one page is read, all such lists concurrently, since the comparisons need every branch. Then R4's second read and the comparisons start side by side: each working branch's comparison is one call, and each repository's unreleased work is one chain (the trunks' comparison, then the pull requests of its commits, then their files), which starts when that repository's comparison answers and runs beside the other repositories' chains, the branch comparisons and the second read. Within a repository's chain the groups of commits are read one after another, and so are the groups of first pages of files; only the further pages of a pull request with more than one page of files are read concurrently. At most eight REST calls are in flight at once. Three queries name many targets by alias in one document: `CommitPullRequests`, 50 commits of one repository to a query; `PullRequestFiles`, 20 pull requests of one repository to a query; and `PullRequestStatuses`, 20 pull requests of any repositories to a query. One such query costs what its targets would cost separately and takes one round trip instead of one for each; every value from GitHub that reaches a document is quoted as a GraphQL literal or passed as a variable.

The gather of the open pull requests is the one search and, where it answered a status as not yet computed, R4's second read. Neither of its two conditions is a search term, so the search's answer is filtered in code: a pull request is kept when its base is its repository's default branch, which is the integration trunk (R1), and when its head branch does not begin `back-merge-`; Dependabot's are kept like any other. The list is sorted by repository and number.

Two further facts come with the answers rather than from calls of their own. GitHub's rate limit is read from the `rateLimit` field every GraphQL query asks for, each answer replacing the last. When the token expires is read from the `github-authentication-token-expiration` header of any answer, and the status bar shows it only where GitHub sent it.

## Data not gathered

Every fact in the contract carries its own state, `Gathered` or `NotGathered`, so that a call that fails costs the facts it feeds and no others (axiom 8). Each call answers with a `Reply` rather than raising: the data where GitHub answered, a `Failure` where it did not, and both where a GraphQL answer carried errors beside partial data. A failure is classified by what GitHub answered: no answer at all, the token refused (401), the rate limit spent (429; 403 with the budget at zero, a `retry-after` header or a message naming the limit; or GraphQL's own refusal, an error of type `RATE_LIMITED` with status 200), a scope the token lacks (GraphQL's `INSUFFICIENT_SCOPES`), any other GraphQL error ("GitHub answered with an error"), any other refusal, nothing to read (404), GitHub failing (5xx), an answer that could not be read, or a list longer than 20 pages. Each step of a collection also runs under a guard that turns anything raised unexpectedly into a problem for the facts that step feeds, reporting only the kind of the error, since its message could hold whatever the answer held.

A list a definition needs whole (a repository's tags, its branches, its open pull requests, the open pull requests of the organisation) is read to its end or not gathered at all: the newest tag by version, which branches exist, and which branch has a pull request open from it are facts of the whole list. Each list is read at most 20 pages, a guard against a source that never ends rather than a limit any list reaches.

Each failure becomes a `Problem`: what the reader loses, in the page's words; why, in one sentence; and the detail of each call behind it, with the HTTP status and GitHub's own message where there was one, shortened to 300 characters. A call is named in the page's words ("the organisation's container packages"), never as a path or an address. The page shows a fact not gathered zeroed and greyed (R7); the status bar's sentence names the problems of both gathers while there are at most two and counts them beyond that (R21), and the information icon opens a dialog listing every problem of both gathers with its detail.

## The wait, and a gather cut short

Each gather runs under one deadline, the wait (D7): `HAZEL_TRACKING_WAIT_SECONDS`, 15 s by default, a setting of the stack. The whole collection runs inside `asyncio.timeout(wait)`, which bounds the gather; httpx's timeout, set to the same number, bounds each phase of each call. Each answer is written into the gather's state as it arrives, rather than assembled at the end, and a fact is written only when every call feeding it has answered. A gather cut short by the wait therefore keeps every fact that had arrived whole: each repository whose name had arrived is shown with what arrived for it, and everything else is greyed (R11). What was still being read at the cut stays not gathered: a list still being paged, an unreleased count still being read and the documentation mark with it, a dev release whose packages were still being read, and the count of archived repositories, which is written only once the whole list of repositories has arrived. If the list of repositories had not arrived, the detail shows its columns and no rows; if the search had answered before the wait ran out, its list stands. The gather records each call it has sent and not had answered, and the problem a gather cut short carries, "GitHub did not answer within the wait of 15 seconds" with the default wait, names every one of them in its detail.

## The 30-minute cycle and its retries

While a page is open it runs the full gather by itself, as [`what-it-shows.md`](what-it-shows.md#when-the-page-gathers) rules it (R8, as amended on 2026-10-03). The schedule (`ui/schedule.py`) is a one-shot timer, cancelled when any full gather begins and set again when it ends, so that a Refresh or a page load restarts it rather than running beside it. The delay is measured from when the gather that just ended began:

- after a wholly successful full gather (complete within the wait, and no problem), 30 minutes;
- after one that is not, the retries: 1 minute, then 2, 4, 8 and 16 minutes after each further attempt that is not wholly successful;
- after the fifth retry, the 30-minute cycle resumes; a later gather that is not wholly successful begins the retries afresh.

While a retry is pending, the status bar says when the page tries again. The interval and the retries are ruled constants in `config.py`, not settings. The pull-requests tab's Refresh and its watch do not touch this cycle.

## The watch

The pull-requests tab's Watch (`ui/watch.py`) gathers the open pull requests alone every 10 seconds, comparing each answer with the snapshot the watch was started on. It stops:

- when the set of open pull requests changes, a pull request by repository and number appearing or disappearing;
- when started from one pull request's row, also when that pull request's status changes;
- after 10 minutes;
- when the reader leaves the tab, presses the button again, or closes the page.

Moving to another browser tab or another application does not stop it. The tab's own Watch, pressed while a line's watch runs, cancels that watch and starts a fresh watch of the whole set, compared with the list the tab then holds and with its own 10 minutes (R22). A gather of the watch's own that could not read the pull requests stops nothing and compares nothing, since an unanswered search is not a pull request disappearing; a watch begun before any list had been gathered takes the first list that arrives as the one it compares with; and an answer to a watch already cancelled or begun afresh is ignored. When the watch stops on a change, the browser tab's title carries the change ("1 new pull request", "#12 ready to merge") ahead of the display name, and the tab shows a line naming the pull request that arrived, left or changed; the chrome's Refresh or the next watch clears both. The 10 seconds and the 10 minutes are ruled constants in `config.py`. The tab's own Refresh during a watch leaves the watch comparing with the snapshot it was started on.

## GitHub's rate limits and a gather's cost

GitHub gives a token two separate budgets: GraphQL's, 5,000 points an hour, and REST's, 5,000 requests an hour, as GitHub documents them for a personal token. GraphQL's is the one the status bar shows (R17), as points left and when the budget resets; REST's headers are read only to say, where a REST call was refused for the limit, when that refusal resets. Every open page spends from the same token's budgets.

Measured live on 2026-10-03 against the organisation as it then stood, two runs of the full gather took 5.4 s and 7.4 s and cost about 47 points of GraphQL's budget, and the search for the open pull requests, measured the same day, took 0.45 to 0.77 s and cost 1 point. The 0.6 to 0.7 s that the decision log gives for the search is a separate measurement, recorded with the ruling on the pull-requests tab. On those figures, a page load, which runs both, costs about 48 points; an open page's automatic cycle, two full gathers an hour, about 94 points an hour; and a watch run to its 10 minutes, a gather every 10 seconds, about 60 points. A full gather's REST calls are one for the organisation's packages, one for each package's versions, and one comparison for each repository with two trunks and for each working branch, with more pages only where a list or a comparison is longer than one.

## What is never shown

The token travels only in the gathering client's `Authorization` header. The configuration keeps it out of its own representation; `/admin/version` reports every setting except it; and no problem, log record or exception message carries it. Every message that leaves `calls.py` passes through `redact`, which replaces the token with "the GitHub token" wherever it appears; an exception from the HTTP client is reported and logged by its kind alone, since its message can name the address it was sent to. A credential is named in general terms only ("the GitHub token was refused"). No traceback reaches the page. Paths and addresses of GitHub's interfaces do not appear in problems, which name calls in the page's words.

## The code's layout and the contract

One distribution, `hazel-tracking`, in the src layout under `src/hazel_tracking/`:

| Module | Holds |
|---|---|
| `__main__.py` | the entry point: the configuration, the refusal without a token, `install()` and `run()` |
| `config.py` | the configuration from the environment, the ruled intervals, and the one place the version is derived, from the package metadata |
| `app.py` | `install()` and `run()`, the two operational endpoints, and the client each gather reads through |
| `model.py` | the contract between the gathering and the page |
| `gather.py` | the two gathering entry points and the wait |
| `github/` | GitHub: `calls.py`, `queries.py`, `facts.py`, `full.py`, `pull_requests.py`, `collecting.py` (what both gathers share: the wait, the guard, the grouping of targets) and `problems.py` |
| `overview.py` | the overview, derived from the full gather's snapshot |
| `page.py` | the page at `/`: one `Dashboard` per browser, its gathers, its spinners, its schedule and its watch |
| `ui/` | the page's parts: `theme.py` (the palette, the stylesheet, the vendored mark and face), `text.py` and `cells.py` (the words and one fact's markup), `overview_view.py`, `detail_view.py` and `pull_requests_view.py`, `status_bar.py`, `schedule.py` and `watch.py`; `brand/` holds the ParkviewLab mark and Michroma, vendored from the handbook's brand under their own licences |

The contract is `model.py`: frozen dataclasses and enumerations with no behaviour, in the words of [`what-it-shows.md`](what-it-shows.md). Every fact is a `Fact[T]`, `Gathered(value)` or `NotGathered`, and a fact that does not apply to a repository, given its trunks (R1), is `None` rather than a fact. The gathering returns the contract and nothing else; the page reads the contract and nothing else, and never a source; and no type in it is shaped by one source's interface, so that a later phase's source can feed the same views. `Gather` and `GatherPullRequests`, the two functions the page awaits, are its seam: `install()` binds the gathering to them, and a test binds stubs.

The views are pure functions of the contract that return markup, except the pull-requests list, which is built from elements because each line carries a button. The mark and the face are embedded in the page, the face as a `data:` URI, so that a page load requests nothing outside the service.

## Tests

The tests run with `uv run pytest -m "not network and not integration" -q`, as CI's `test` job runs them, and need no network and no token.

- The configuration, the entry point, the app's endpoints and seam, the contract, and the overview: `test_config.py`, `test_main.py`, `test_app.py`, `test_model.py`, `test_overview.py`.
- The gathering, against a fake GitHub (`tests/gh_fakes.py`): a synthetic organisation built in code, with a repository for each case the readings turn on (`tests/gh_fixtures.py`), answered through an `httpx` transport so that nothing leaves the machine. The fake can force an answer for a named call, hold one back so that the wait cuts a gather short, and cap every page so that each list is read to its end over several calls. `test_gh_facts.py` reads each derivation against R1 to R6; `test_gh_gather.py` the full gather, fact by fact; `test_gh_failures.py` every kind of failure and the two gathers cut short; `test_gh_pull_requests.py` the search and its filtering. Two tests of `test_gh_failures.py` look for the sentinel token: one makes four calls fail, in four different ways, in one full gather, GitHub echoing the token in its own messages, and the other refuses the search; in both the token is absent from each problem and each log record.
- The page, with NiceGUI's `user` fixture: `tests/page_main.py` installs the application as `__main__` does, with both gathers stubbed to read the scenarios a test loads, under a configuration whose intervals are shortened so that the schedule, the retries and the watch run within a test. The scenarios, in `tests/page_scenarios.py`, are six full gathers (live-like, stress, failures, timed out, no repositories, an expiring token) and four sequences for the watch (a pull request arriving, a chosen pull request's status changing, a watch begun before anything was gathered, nothing changing until the time runs out). `test_page_chrome.py`, `test_page_overview.py`, `test_page_detail.py`, `test_page_pull_requests.py`, `test_page_greying.py`, `test_page_status.py`, `test_page_schedule.py`, `test_page_watch.py` and `test_page_secrets.py` read the page a browser is shown against [`what-it-shows.md`](what-it-shows.md), and look for the sentinel token in everything a browser is sent.
- `uv run python -m tests.page_preview <scenario>` serves one scenario on the loopback address under the ruled intervals, for a person to look at and to measure.

CI's `image` job builds the image, runs it as the stack runs it with a dummy token and GitHub's API pointed at a closed local port, and requires it to become healthy, to report `pyproject.toml`'s version on `/health`, and to answer `/` with the display name.

---
<sub>© 2026 Gary Frattarola · Licensed under [MIT](../LICENSE-MIT) OR [Apache-2.0](../LICENSE-APACHE) · part of [ParkviewLab](https://github.com/ParkviewLab)</sub>
