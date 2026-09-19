<!--
SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# hazel-tracking: northstar

## What it is

The ParkviewLab Engineering Dashboard: one page, served on trixie, showing the present state of every ParkviewLab repository, and in later phases the lab's services and development machines.

## Why it exists

To let one person see, in a single browser window and without searching, what is going on now and what needs attention, instead of visiting GitHub, BookStack, trixie and each machine in turn.

## Intents

1. Everything at once. Every project, and in time every service and machine, on one screen, with no scrolling and nothing to click through.
2. True as of now. The page is gathered from its sources when it is requested and held nowhere, so what it shows is what the sources say at that moment, and what could not be gathered is shown as such.
3. Private and read-only. It serves the home network alone, reads its sources without ever writing to them, and shows no secret.

### How the intents reinforce each other

Gathering on request is what lets the Dashboard hold no data, so that it has nothing to protect beyond its credentials; and showing only the present, with no history, is what keeps everything to one screen.

## Axioms

1. Report, do not judge. Each fact is shown as its source states it; a roll-up, such as "ready to cut a release", follows a written rule and names the condition that fails.
2. Store nothing: no database, no cache, no history.
3. Never write to a source.
4. Show what is unknown: data that could not be gathered is greyed out, and the status bar says why.
5. One window: a page that does not fit is a defect.
6. No secret on the page, anywhere.

## What hazel-tracking is not

- Not a monitoring system: no history, no graphs, no alerts.
- Not a control panel: it changes nothing anywhere.
- Not a task list: nothing on it is entered by hand.
- Not public: it serves the home network only.

---
<sub>© 2026 Gary Frattarola · Licensed under [MIT](../LICENSE-MIT) OR [Apache-2.0](../LICENSE-APACHE) · part of [ParkviewLab](https://github.com/ParkviewLab)</sub>
