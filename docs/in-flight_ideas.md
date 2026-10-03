<!--
SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# In-flight ideas

Scratchpad for ideas under consideration: questions, not commitments (see the handbook's [`documentation.md`](https://github.com/ParkviewLab/handbook/blob/main/docs/documentation.md)). Do not act on an entry silently. A decision, once made, is recorded in [`decisions.md`](decisions.md), and a closed entry is removed from here.

## Open

### Installer dev builds

Dev releases are read from GHCR alone ([`what-it-shows.md`](what-it-shows.md#dev), R9). An Electron app's dev build keeps its installers as the artefacts of a dev workflow's run, in the `installers` job that conception-space and pensa-grex carry; neither had run it by 3 October 2026. Whether to read such builds (the workflow's latest successful run, the version at that commit, and the artefacts, marked when they have expired) once one is cut.

### Dev releases published only to TestPyPI or npm

The page reads GitHub alone, so a dev release published only to TestPyPI or npm is not read ([`what-it-shows.md`](what-it-shows.md#dev), R9); none existed on 18 September 2026. Whether to read such releases once a repository publishes one.

### Repositories shown in the Atlas's groupings

The page fits the browser window's width, and its height grows with the number of repositories, so a larger organisation means scrolling (ruled 2026-10-03). The Atlas generator, a proposal in BookStack (the book "Atlas generator"), groups repositories into the projects they form, a repository belonging to more than one group where it does. Whether the page should show the repositories in those groupings, one tab per grouping, so that each tab fits the window and the reader moves through the groupings by tab, beside a tab that keeps every repository on one table. It depends on the Atlas generator being built and its groupings being readable by the Dashboard.

### The later phases

This version shows only what GitHub supplies for the organisation's repositories. The later phases, which would add BookStack's tangents and proposals, the lab's services, the development server's info service, the storage server and the development machines, and the phase in which `garycoding/Development-Lab` joins, are a proposal in BookStack, in the book "The Dashboard". Their order is not ruled.
