<!--
SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# hazel-tracking: northstar

## What it is

The ParkviewLab Engineering Dashboard, served on the development server: three views of the present state of every ParkviewLab repository (an overview, the detail and the open pull requests), and in later phases the lab's services and development machines.

## Why it exists

To let one person see, in a single browser window and without searching, what is going on now and what needs attention, instead of visiting GitHub, BookStack, the development server and each machine in turn.

## Intents

1. The overview: what needs attention, at a glance. One screen, with no scrolling and nothing to click through, shows what is waiting on the reader from every source the Dashboard reads, and the state of each thing it reads (in this version, the release state of every repository); once the Atlas generator groups the repositories into projects, one screen per grouping.
2. The detail: everything, for every source. Every fact the Dashboard gathers, in one table per source as wide as the window (in this version, one table of every repository), each growing in height with what it holds.
3. The pull requests: the work arriving. Every open pull request into the integration trunks except the back-merges of releases, each linked to it, with its own refresh that gathers the pull requests alone, cheap enough to repeat as often as new work is expected, and a watch the reader starts that repeats it for a few minutes and marks the arrival or departure of a pull request, or a chosen pull request's change of status.
4. Safe to leave open. Every view is read-only and private: it reads its sources without changing anything it reads, serves the development network alone, and shows no secret, so the page can stay open on any screen in the lab, whatever sources later phases add.

### How the intents reinforce each other

The overview can leave detail out because the detail view holds it, and the detail view can grow because the overview stays on one screen; that is the trade-off between them, completeness given up on the overview to fit one screen, and fitting given up on the detail to show everything. The pull requests view gathers one thing, so it can be refreshed freely, and the full gather is spent only where the whole picture is needed. Being safe to leave open is what lets all three views stay in sight all day, which is how the reader uses them to monitor the work.

## Axioms

1. Report, do not judge. Each fact is shown as its source states it; a roll-up, such as "ready to cut a release", follows a written rule and names the condition that fails.
2. Gather on request, store nothing: the page is gathered from its sources when it is opened or refreshed, and refreshes itself on a written schedule while it is open; nothing is held beyond the open page, so what it shows is what the sources said at the time it names; no database, no cache, no history.
3. Never write to a source.
4. Show what is unknown: data that could not be gathered is greyed out, and the status bar says why.
5. One window wide: a view wider than the window is a defect; the overview fits one screen, and the other views grow in height only as their contents grow.
6. No secret on the page, anywhere.
7. The development network alone: it serves nothing outside it.
8. One source's failure never hides another's: each source is gathered on its own, what it could not give is greyed, and the rest of the page stands.

## What hazel-tracking is not

- Not an alerting system: it keeps no history, draws no graphs, and tells nothing to anyone not looking at it; it is the reader who monitors.
- Not a control panel: it changes nothing anywhere.
- Not a task list: nothing on it is entered by hand.
- Not public: it serves the development network only.

---
<sub>© 2026 Gary Frattarola · Licensed under [MIT](../LICENSE-MIT) OR [Apache-2.0](../LICENSE-APACHE) · part of [ParkviewLab](https://github.com/ParkviewLab)</sub>
