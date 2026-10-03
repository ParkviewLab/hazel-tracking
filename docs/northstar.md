<!--
SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# hazel-tracking: northstar

## What it is

The ParkviewLab Engineering Dashboard: a page, served on the development server, showing the present state of every ParkviewLab repository, with a second page of their open pull requests alone, and in later phases the lab's services and development machines.

## Why it exists

To let one person see, in a single browser window and without searching, what is going on now and what needs attention, instead of visiting GitHub, BookStack, the development server and each machine in turn.

## Intents

1. Everything at once. Every project, and in time every service and machine, on one page as wide as one window, with nothing to click through to see a repository's state.
2. True as of now. The page is gathered from its sources when it is requested and held nowhere, so what it shows is what the sources say at that moment, and what could not be gathered is shown as such.
3. Private and read-only. It serves the development network alone, reads its sources without ever writing to them, and shows no secret.

### How the intents reinforce each other

Gathering on request is what lets the Dashboard hold no data, so that it has nothing to protect beyond its credentials; and showing only the present, with no history, is what keeps everything to one page.

## Axioms

1. Report, do not judge. Each fact is shown as its source states it; a roll-up, such as "ready to cut a release", follows a written rule and names the condition that fails.
2. Store nothing: no database, no cache, no history.
3. Never write to a source.
4. Show what is unknown: data that could not be gathered is greyed out, and the status bar says why.
5. One window wide: a page wider than the window is a defect; it grows in height only as the repositories grow in number.
6. No secret on the page, anywhere.

## What hazel-tracking is not

- Not a monitoring system: no history, no graphs, no alerts.
- Not a control panel: it changes nothing anywhere.
- Not a task list: nothing on it is entered by hand.
- Not public: it serves the development network only.

---
<sub>© 2026 Gary Frattarola · Licensed under [MIT](../LICENSE-MIT) OR [Apache-2.0](../LICENSE-APACHE) · part of [ParkviewLab](https://github.com/ParkviewLab)</sub>
