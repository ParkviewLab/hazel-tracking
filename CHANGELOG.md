# Changelog

All notable changes to this project are recorded here.

## [Unreleased]

## [v0.1.0] - 2026-10-03

### Highlights

First release of the ParkviewLab Engineering Dashboard: a single page, served at `/`, that gathers the state of every organisation repository from GitHub over GraphQL and REST and presents it in three tabs — Overview, Detail and Pull Requests — with a header carrying the ParkviewLab mark, the version, the age of the data and a Refresh All button, a status line reporting the rate limit, archived repositories, token expiry and any problems, and a spinner over the dimmed page for each gather. Open pull requests refresh on their own, and a Watch, startable for one pull request or the whole set, marks the browser tab's title and stops on a change of status or set, on leaving the tab, or after ten minutes; a full gather also repeats every 30 minutes with retries, and facts that could not be read are shown as not gathered rather than guessed. Ships with a container image and example compose stack, a health and version endpoint, and documentation — architecture, deployment, what the page shows and the decision record — published as a site.

### Features

- Scaffold the package, the contract, the image, the workflows and the documents (#1)
- Publish docs/ as the documentation site, with the northstar's twin (#2)
- The page: overview, detail and pull requests, with the spinner and the watch (#3)
- Gather the organisation's state and its open pull requests from GitHub (#5)
- The chrome as prima-dev-dashboard's header (#8)
- One look for the buttons, their names, the Pull Requests tab, and the box spinner (#10)

### Bug fixes

- The pull requests are one table, the Watch in a column of its own (#4)
- The comparison's problem names the page guard, and R23 recorded (#7)
- The mark at prima-dev-dashboard's size, the chrome's top margin, and the pre-release document corrections (#9)

### Docs

- The documents at Phase 1 built: architecture, deployment, the README, R21 and R22 (#6)
