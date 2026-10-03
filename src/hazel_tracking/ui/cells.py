# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""One fact, as the page shows it: the markup the detail and the overview share.

Every function here is a pure function of the contract in `hazel_tracking.model`
and returns a fragment of HTML, escaped at every point where a source's words
reach the page. The reading they all obey is R7: a fact that could not be
gathered is shown zeroed and greyed, 0 for a count, "no" for a yes-or-no fact and
an empty value for a version or a state; a fact gathered and found empty reads
"none" in ordinary type.
"""

from __future__ import annotations

import html
from datetime import datetime

from hazel_tracking.model import (
    CheckState,
    Gathered,
    PullRequest,
    ReleaseCondition,
    Repository,
    WorkingBranch,
)
from hazel_tracking.ui import text

GITHUB_URL = "https://github.com"

# The order in which a readiness indicator names the conditions that fail (R6), each with its style.
CONDITION_STYLE: dict[ReleaseCondition, tuple[str, str]] = {
    ReleaseCondition.NOTHING_TO_RELEASE: text.PLAIN,
    ReleaseCondition.CHECKS_FAILING: text.BAD,
    ReleaseCondition.BACK_MERGE_PENDING: text.PENDING,
}
CONDITION_ORDER = (
    ReleaseCondition.NOTHING_TO_RELEASE,
    ReleaseCondition.CHECKS_FAILING,
    ReleaseCondition.BACK_MERGE_PENDING,
)

READY_TO_CUT = "ready to cut a release"
DOCUMENTATION_NOTE = "documentation"


def escape(value: str) -> str:
    return html.escape(value, quote=True)


def span(content: str, cls: str = "") -> str:
    return f'<span class="{cls}">{content}</span>' if cls else content


def link(url: str, content: str, cls: str = "plain") -> str:
    """A link to GitHub, opened in a tab of its own."""
    return f'<a class="{cls}" href="{escape(url)}" target="_blank" rel="noopener">{content}</a>'


def state(style: tuple[str, str], word: str) -> str:
    """A state as its mark and its word, so that it reads without colour (R10)."""
    mark, cls = style
    marked = f'<span class="mark">{mark}</span> {escape(word)}' if mark else escape(word)
    return span(marked, cls)


def ungathered(zeroed: str) -> str:
    """A fact that could not be gathered, zeroed and greyed (R7)."""
    return span(escape(zeroed), "ungathered")


def ungathered_count() -> str:
    return ungathered("0")


def ungathered_yes_no(label: str = "no") -> str:
    return ungathered(label)


def ungathered_value() -> str:
    return ungathered(text.ZEROED_VALUE)


def nothing() -> str:
    """A fact gathered and found empty: "none", in ordinary type (R7)."""
    return "none"


def lines(parts: list[str]) -> str:
    return "".join(f'<span class="line">{part}</span>' for part in parts)


def chips(parts: list[str]) -> str:
    return "".join(f'<span class="chip">{part}</span>' for part in parts)


def repository_url(name: str) -> str:
    return f"{GITHUB_URL}/{name}"


def short_name(name: str) -> str:
    """ "ParkviewLab/handbook" reads as "handbook"; the full name is the link's title."""
    return name.split("/", 1)[1] if "/" in name else name


def repository_cell(repo: Repository) -> str:
    return (
        f'<a class="plain" href="{escape(repository_url(repo.name))}" target="_blank" '
        f'rel="noopener" title="{escape(repo.name)}">{escape(short_name(repo.name))}</a>'
    )


def last_push_cell(repo: Repository, now: datetime) -> str:
    if not isinstance(repo.last_push, Gathered):
        return ungathered_value()
    if repo.last_push.value is None:
        return nothing()
    return escape(text.since(repo.last_push.value, now))


def issues_cell(repo: Repository) -> str:
    if not isinstance(repo.open_issues, Gathered):
        return ungathered_count()
    if repo.open_issues.value == 0:
        return "0"
    return span(str(repo.open_issues.value), "strong")


def tag_release_cell(repo: Repository) -> str:
    """The newest version tag and the newest Release, both shown, a difference marked (R3)."""
    if not (isinstance(repo.newest_tag, Gathered) and isinstance(repo.newest_release, Gathered)):
        return ungathered_value()
    tag, release = repo.newest_tag.value, repo.newest_release.value
    if tag is None and release is None:
        return nothing()
    shown = escape(tag) if tag is not None else span("no tag", "yellow")
    if release is None:
        suffix = span(" / no release", "sub yellow")
    elif release == tag:
        suffix = span(f" / release {escape(release)}", "sub")
    else:
        suffix = span(f" / release {escape(release)}", "sub yellow")
    return span(shown, "strong") + suffix


def dev_cell(repo: Repository) -> str:
    if not isinstance(repo.dev_release, Gathered):
        return ungathered_value()
    if repo.dev_release.value is None:
        return nothing()
    return escape(repo.dev_release.value.version)


def unreleased_cell(repo: Repository) -> str:
    """The merged pull requests no release carries, with the documentation mark (R5).

    The count is also how far the integration trunk is ahead of the release trunk, so
    the two are one line. A repository whose default branch is its only trunk has no
    comparison, and the cell is empty.
    """
    if repo.unreleased is None:
        return ""
    count = repo.unreleased.pull_requests
    if not isinstance(count, Gathered):
        return ungathered_count()
    if count.value == 0:
        return nothing()
    shown = escape(f"{text.plural(count.value, 'pull request')} ahead")
    return shown + documentation_note(repo)


def documentation_note(repo: Repository, lead: str = " · ") -> str:
    """The documentation mark, where any unreleased pull request changes it, greyed where unknown (R5).

    `lead` is what separates the mark from what it follows: a middle dot beside the count in
    the detail, a comma inside the overview's parenthesis.
    """
    if repo.unreleased is None:
        return ""
    mark = repo.unreleased.documentation
    if not isinstance(mark, Gathered):
        return lead + span(f"{DOCUMENTATION_NOTE} {text.ZEROED_VALUE}", "ungathered")
    if not mark.value:
        return ""
    return lead + span(DOCUMENTATION_NOTE, "sub")


def readiness_cell(repo: Repository, *, with_count: bool = False) -> str:
    """Ready to cut a release, or every condition that fails; a pending back-merge for a
    website repository; nothing where the default branch is the only trunk (R6).

    `with_count` adds the count of unreleased pull requests, which the overview needs
    because it has no Unreleased column of its own.
    """
    if repo.readiness is not None:
        if not isinstance(repo.readiness, Gathered):
            return ungathered_value()
        failing = repo.readiness.value.failing
        if not failing:
            return state(text.GOOD, READY_TO_CUT) + (
                unreleased_note(repo) if with_count else documentation_note(repo)
            )
        named = [state(CONDITION_STYLE[c], str(c)) for c in CONDITION_ORDER if c in failing]
        return chips(named)
    if repo.back_merge_pending is not None:
        if not isinstance(repo.back_merge_pending, Gathered):
            return ungathered_yes_no("no back-merge pending")
        if repo.back_merge_pending.value:
            return state(text.PENDING, "back-merge pending")
        return "no back-merge pending"
    return ""


def unreleased_note(repo: Repository) -> str:
    """ " (3 pull requests, documentation)", for the overview's readiness indicator."""
    if repo.unreleased is None:
        return ""
    count = repo.unreleased.pull_requests
    if isinstance(count, Gathered):
        inner = escape(text.plural(count.value, "pull request"))
    else:
        inner = ungathered("0 pull requests")
    return span(f" ({inner}{documentation_note(repo, ', ')})", "sub")


def checks_cell(repo: Repository) -> str:
    """The checks on each trunk, the release trunk first (R2)."""
    if not repo.checks:
        return ""
    parts = []
    for check in repo.checks:
        if not isinstance(check.state, Gathered):
            shown = ungathered_value()
        elif check.state.value == CheckState.NONE:
            shown = nothing()
        else:
            shown = state(text.CHECK_STATE_STYLE[check.state.value], str(check.state.value))
        parts.append(f"{span(escape(check.trunk), 'sub')} {shown}")
    return lines(parts)


def branch_line(branch: WorkingBranch) -> str:
    behind = (
        span(f"({branch.behind.value})", "sub")
        if isinstance(branch.behind, Gathered)
        else span(f"({text.ZEROED_VALUE})", "ungathered")
    )
    if isinstance(branch.pull_request, Gathered):
        reference = branch.pull_request.value
        mark = " " + link(reference.url, f"#{reference.number}") if reference is not None else ""
    else:
        mark = " " + ungathered_value()
    return f"{escape(branch.name)} {behind}{mark}"


def branches_cell(repo: Repository) -> str:
    if not isinstance(repo.working_branches, Gathered):
        return ungathered_value()
    if not repo.working_branches.value:
        return nothing()
    return lines([branch_line(b) for b in repo.working_branches.value])


def pull_request_line(pull_request: PullRequest) -> str:
    if isinstance(pull_request.status, Gathered):
        shown = state(text.PULL_REQUEST_STYLE[pull_request.status.value], str(pull_request.status.value))
    else:
        shown = ungathered_value()
    return f"{link(pull_request.url, f'#{pull_request.number}')} {shown}"


def pull_requests_cell(repo: Repository) -> str:
    if not isinstance(repo.pull_requests, Gathered):
        return ungathered_value()
    if not repo.pull_requests.value:
        return nothing()
    return lines([pull_request_line(p) for p in repo.pull_requests.value])
