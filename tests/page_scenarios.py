# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""The snapshots the page's tests and its preview are built from, written in code.

Four full gathers: `live_like`, the organisation as it stands; `stress`,
twenty-five repositories with every state present; `failures`, a gather complete
within the wait in which two calls failed; and `timed_out`, a gather not complete
within the wait after the list of repositories had arrived. Three sequences of
the gather of the open pull requests alone, for the watch: one that sees a pull
request arrive, one that sees a chosen pull request's status change, and one in
which nothing changes until the watch's time runs out.

Every scenario is a pure function of the moment it is given, so that a test fixes
time rather than waiting for it, and nothing here reads a source or a file.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from hazel_tracking.model import (
    NOT_GATHERED,
    CheckState,
    DevRelease,
    Fact,
    Gathered,
    OpenPullRequest,
    Problem,
    ProblemDetail,
    PullRequest,
    PullRequestRef,
    PullRequestsSnapshot,
    PullRequestStatus,
    RateLimit,
    Readiness,
    ReleaseCondition,
    Repository,
    Snapshot,
    TrunkChecks,
    Trunks,
    Unreleased,
    WorkingBranch,
)

ORG = "ParkviewLab"
SOURCES = ("GitHub",)

# The moment every scenario is reckoned from: 13:03:12 UTC, which is 14:03:12 in the lab's zone
# in the tests, so that a time on the page proves it was converted.
MOMENT = datetime(2026, 10, 3, 13, 3, 12, tzinfo=UTC)

# The organisation as it stands, with hazel-tracking itself.
LIVE_LIKE_NAMES = (
    "cobalt-grinding",
    "cogrind-workshop",
    "conception-space",
    "deco-assaying",
    "dev-tools",
    "ebony-enriching",
    "flint-slating",
    "handbook",
    "hazel-tracking",
    "jonobones",
    "paper-boxing",
    "parkviewlab.ai",
    "pensa-forma",
    "pensa-grex",
    "pvl-dotview",
    "smalt-mcp",
    "zoestum.ai",
)

# Eight more, in the house style, to carry the stress scenario to twenty-five.
EXTRA_NAMES = (
    "amber-kilning",
    "azure-smelting",
    "carmine-etching",
    "indigo-forging",
    "ochre-milling",
    "sienna-tempering",
    "umber-glazing",
    "viridian-casting",
)

WEBSITES = ("parkviewlab.ai", "zoestum.ai")


def full(name: str) -> str:
    return f"{ORG}/{name}"


def pull_request_url(name: str, number: int) -> str:
    return f"https://github.com/{full(name)}/pull/{number}"


def pull_request(
    name: str, number: int, status: PullRequestStatus | None = PullRequestStatus.READY
) -> PullRequest:
    state: Fact[PullRequestStatus] = NOT_GATHERED if status is None else Gathered(status)
    return PullRequest(number=number, url=pull_request_url(name, number), status=state)


def branch(name: str, repository: str, behind: int | None = 0, number: int | None = None) -> WorkingBranch:
    behind_fact: Fact[int] = NOT_GATHERED if behind is None else Gathered(behind)
    reference = (
        None if number is None else PullRequestRef(number=number, url=pull_request_url(repository, number))
    )
    return WorkingBranch(name=name, behind=behind_fact, pull_request=Gathered(reference))


def trunks_of(name: str, *, lone_trunk: bool = False, no_default_branch: bool = False) -> Trunks:
    if no_default_branch:
        return Trunks(integration="", release=None)
    if lone_trunk:
        return Trunks(integration="main", release=None)
    if name in WEBSITES:
        return Trunks(integration="staging", release="live")
    return Trunks(integration="develop", release="main")


def checks_of(
    trunks: Trunks, release: CheckState | None, integration: CheckState | None
) -> tuple[TrunkChecks, ...]:
    """The checks on each trunk, the release trunk first (R2); `None` for a state not gathered."""
    states = []
    if trunks.release is not None:
        states.append((trunks.release, release))
    states.append((trunks.integration, integration))
    return tuple(
        TrunkChecks(trunk=trunk, state=NOT_GATHERED if state is None else Gathered(state))
        for trunk, state in states
    )


def derived_conditions(
    unreleased: int | None, integration_checks: CheckState | None, back_merge: bool | None
) -> frozenset[ReleaseCondition]:
    """The conditions of readiness that fail, given the facts a scenario sets (R6).

    Checks still running are passed over, as R2 reads the rule: readiness is judged on the
    latest commit whose checks have finished.
    """
    conditions = set()
    if not unreleased:
        conditions.add(ReleaseCondition.NOTHING_TO_RELEASE)
    if integration_checks in (CheckState.FAILING, CheckState.NONE, None):
        conditions.add(ReleaseCondition.CHECKS_FAILING)
    if back_merge:
        conditions.add(ReleaseCondition.BACK_MERGE_PENDING)
    return frozenset(conditions)


def repository(
    name: str,
    *,
    moment: datetime = MOMENT,
    pushed_minutes_ago: float | None = 42.0,
    issues: int | None = 0,
    tag: str | None = "v0.1.0",
    release: str | None = "v0.1.0",
    dev: str | None = None,
    unreleased: int | None = 0,
    documentation: bool | None = False,
    failing: Iterable[ReleaseCondition] | None = None,
    back_merge: bool | None = False,
    release_checks: CheckState | None = CheckState.PASSING,
    integration_checks: CheckState | None = CheckState.PASSING,
    branches: Sequence[WorkingBranch] = (),
    pull_requests: Sequence[PullRequest] | None = (),
    lone_trunk: bool = False,
    no_default_branch: bool = False,
    ungathered_versions: bool = False,
    ungathered_branches: bool = False,
    ungathered_dev: bool = False,
    ungathered_readiness: bool = False,
) -> Repository:
    """One repository, healthy by default; each argument set to `None` leaves that fact ungathered.

    `failing` left out derives the conditions that fail from the facts themselves, so that a
    scenario cannot read "ready to cut a release" with nothing to release (R6).
    """
    trunks = trunks_of(name, lone_trunk=lone_trunk, no_default_branch=no_default_branch)
    last_push: Fact[datetime | None] = (
        NOT_GATHERED
        if pushed_minutes_ago is None
        else Gathered(moment - timedelta(minutes=pushed_minutes_ago))
    )
    work = (
        None
        if trunks.release is None
        else Unreleased(
            pull_requests=NOT_GATHERED if unreleased is None else Gathered(unreleased),
            documentation=NOT_GATHERED if documentation is None else Gathered(documentation),
        )
    )
    readiness: Fact[Readiness] | None = None
    pending: Fact[bool] | None = None
    if trunks.release is not None:
        pending = NOT_GATHERED if back_merge is None else Gathered(back_merge)
    if trunks.integration == "develop":
        conditions = frozenset(
            failing if failing is not None else derived_conditions(unreleased, integration_checks, back_merge)
        )
        readiness = NOT_GATHERED if ungathered_readiness else Gathered(Readiness(failing=conditions))
    return Repository(
        name=full(name),
        trunks=trunks,
        last_push=last_push,
        open_issues=NOT_GATHERED if issues is None else Gathered(issues),
        newest_tag=NOT_GATHERED if ungathered_versions else Gathered(tag),
        newest_release=NOT_GATHERED if ungathered_versions else Gathered(release),
        dev_release=NOT_GATHERED
        if ungathered_dev
        else Gathered(None if dev is None else DevRelease(version=dev)),
        unreleased=work,
        readiness=readiness,
        back_merge_pending=pending,
        checks=checks_of(trunks, release_checks, integration_checks),
        working_branches=NOT_GATHERED if ungathered_branches else Gathered(tuple(branches)),
        pull_requests=NOT_GATHERED if pull_requests is None else Gathered(tuple(pull_requests)),
    )


def snapshot(
    repositories: Sequence[Repository],
    *,
    moment: datetime = MOMENT,
    duration_seconds: float = 3.1,
    completed: bool = True,
    archived: int | None = 2,
    problems: Sequence[Problem] = (),
    remaining: int | None = 4832,
    expires_in_days: int | None = 350,
) -> Snapshot:
    return Snapshot(
        began_at=moment,
        duration_seconds=duration_seconds,
        completed=completed,
        sources=SOURCES,
        repositories=tuple(repositories),
        archived=archived,
        problems=tuple(problems),
        rate_limit=None
        if remaining is None
        else RateLimit(remaining=remaining, resets_at=moment + timedelta(minutes=44)),
        credential_expires_at=None if expires_in_days is None else moment + timedelta(days=expires_in_days),
    )


def live_like(moment: datetime = MOMENT) -> Snapshot:
    """Seventeen repositories shaped as the organisation is: a few waiting, most quiet."""
    repositories = [
        repository(
            "cobalt-grinding",
            moment=moment,
            tag="v0.1.3",
            release="v0.1.3",
            pushed_minutes_ago=4 * 24 * 60,
        ),
        repository("cogrind-workshop", moment=moment, tag="v0.1.3", release="v0.1.3"),
        repository(
            "conception-space",
            moment=moment,
            tag="v0.8.9",
            release="v0.8.9",
            issues=2,
            unreleased=3,
            documentation=True,
            branches=[branch("feature-atlas", "conception-space", behind=2, number=61)],
            pull_requests=[pull_request("conception-space", 61, PullRequestStatus.READY)],
        ),
        repository(
            "deco-assaying",
            moment=moment,
            tag="v0.3.8",
            release="v0.3.8",
            branches=[branch("dependabot-pytest", "deco-assaying", behind=0, number=24)],
            pull_requests=[pull_request("deco-assaying", 24, PullRequestStatus.BEHIND)],
        ),
        repository("dev-tools", moment=moment, tag="v1.5.3", release="v1.5.3", unreleased=1),
        repository("ebony-enriching", moment=moment, tag="v1.0.0", release="v1.0.0"),
        repository(
            "flint-slating",
            moment=moment,
            tag="v0.1.9",
            release="v0.1.9",
            unreleased=2,
            integration_checks=CheckState.FAILING,
        ),
        repository(
            "handbook",
            moment=moment,
            tag="v2.1.1",
            release="v2.1.1",
            unreleased=2,
            documentation=True,
            pushed_minutes_ago=18,
        ),
        repository(
            "hazel-tracking",
            moment=moment,
            tag=None,
            release=None,
            dev="0.1.0.dev301",
            unreleased=1,
            documentation=True,
            integration_checks=CheckState.RUNNING,
            pushed_minutes_ago=6,
            branches=[
                branch("feature-github", "hazel-tracking", behind=0, number=2),
                branch("feature-page", "hazel-tracking", behind=0, number=3),
            ],
            pull_requests=[
                pull_request("hazel-tracking", 2, PullRequestStatus.CHECKS_RUNNING),
                pull_request("hazel-tracking", 3, PullRequestStatus.DRAFT),
            ],
        ),
        repository("jonobones", moment=moment, tag="v0.1.9", release="v0.1.9", issues=1),
        repository(
            "paper-boxing",
            moment=moment,
            tag="v0.4.3",
            release="v0.4.3",
            dev="0.4.4.dev502",
            unreleased=5,
            documentation=True,
            pushed_minutes_ago=34 * 60,
        ),
        repository("parkviewlab.ai", moment=moment, tag=None, release=None, back_merge=True),
        repository(
            "pensa-forma",
            moment=moment,
            tag="v0.2.1",
            release=None,
            branches=[branch("doc-spec", "pensa-forma", behind=2)],
        ),
        repository("pensa-grex", moment=moment, tag="v3.5.4", release="v3.5.4", issues=6, unreleased=3),
        repository("pvl-dotview", moment=moment, tag="v0.1.4", release=None),
        repository("smalt-mcp", moment=moment, tag="v2.0.0", release="v2.0.0", unreleased=2),
        repository("zoestum.ai", moment=moment, tag=None, release=None, back_merge=False),
    ]
    return snapshot(repositories, moment=moment)


def stress(moment: datetime = MOMENT) -> Snapshot:
    """Twenty-five repositories, twelve working branches, ten open pull requests, every state."""
    names = [*LIVE_LIKE_NAMES, *EXTRA_NAMES]
    repositories = []
    for index, name in enumerate(sorted(names)):
        repositories.append(repository(name, moment=moment, tag=f"v0.{index}.0", release=f"v0.{index}.0"))
    by_name = {repo.name: repo for repo in repositories}

    def amend(name: str, **changes: object) -> None:
        by_name[full(name)] = repository(name, moment=moment, **changes)  # type: ignore[arg-type]

    amend(
        "amber-kilning",
        tag="v1.2.0",
        release="v1.1.0",
        dev="1.3.0.dev404",
        unreleased=4,
        documentation=True,
        issues=12,
        branches=[
            branch("feature-one", "amber-kilning", behind=0, number=101),
            branch("bug-two", "amber-kilning", behind=7, number=102),
            branch("doc-three", "amber-kilning", behind=3),
        ],
        pull_requests=[
            pull_request("amber-kilning", 101, PullRequestStatus.READY),
            pull_request("amber-kilning", 102, PullRequestStatus.CONFLICTS),
            pull_request("amber-kilning", 103, PullRequestStatus.CHECKS_FAILING),
            pull_request("amber-kilning", 104, PullRequestStatus.DRAFT),
        ],
    )
    amend(
        "azure-smelting",
        tag="v0.9.0",
        release=None,
        unreleased=2,
        back_merge=True,
        integration_checks=CheckState.FAILING,
        release_checks=CheckState.RUNNING,
        issues=3,
        branches=[branch("feature-four", "azure-smelting", behind=11, number=201)],
        pull_requests=[pull_request("azure-smelting", 201, PullRequestStatus.CHECKS_RUNNING)],
    )
    amend(
        "carmine-etching",
        tag="v2.0.0",
        release="v2.0.0",
        release_checks=CheckState.NONE,
        integration_checks=CheckState.NONE,
        branches=[branch("ops-five", "carmine-etching", behind=1, number=301)],
        pull_requests=[pull_request("carmine-etching", 301, PullRequestStatus.BEHIND)],
    )
    amend(
        "indigo-forging",
        lone_trunk=True,
        tag="v0.4.0",
        release="v0.4.0",
        branches=[branch("feature-six", "indigo-forging", behind=2)],
        pull_requests=[],
    )
    amend(
        "ochre-milling",
        ungathered_versions=True,
        ungathered_dev=True,
        issues=None,
        integration_checks=None,
        unreleased=None,
        documentation=None,
        ungathered_branches=True,
        ungathered_readiness=True,
        pull_requests=None,
        pushed_minutes_ago=None,
        back_merge=None,
    )
    amend(
        "sienna-tempering",
        tag="v0.6.1",
        release="v0.6.1",
        unreleased=2,
        documentation=True,
        branches=[
            branch("feature-seven", "sienna-tempering", behind=0, number=401),
            branch("feature-eight", "sienna-tempering", behind=None),
        ],
        pull_requests=[pull_request("sienna-tempering", 401, None)],
    )
    amend(
        "umber-glazing",
        tag=None,
        release="v0.3.0",
        unreleased=1,
        branches=[branch("bug-nine", "umber-glazing", behind=4, number=501)],
        pull_requests=[pull_request("umber-glazing", 501, PullRequestStatus.READY)],
    )
    amend(
        "viridian-casting",
        tag="v0.7.0",
        release="v0.7.0",
        dev="0.8.0.dev12",
        unreleased=1,
        integration_checks=CheckState.RUNNING,
        branches=[branch("feature-ten", "viridian-casting", behind=6, number=601)],
        pull_requests=[pull_request("viridian-casting", 601, PullRequestStatus.CHECKS_RUNNING)],
    )
    amend(
        "parkviewlab.ai",
        tag=None,
        release=None,
        back_merge=True,
        branches=[branch("feature-eleven", "parkviewlab.ai", behind=0, number=701)],
        pull_requests=[pull_request("parkviewlab.ai", 701, PullRequestStatus.DRAFT)],
    )
    amend(
        "zoestum.ai",
        tag=None,
        release=None,
        back_merge=False,
        branches=[branch("doc-twelve", "zoestum.ai", behind=5)],
        pull_requests=[],
    )
    return snapshot(list(by_name.values()), moment=moment, duration_seconds=6.4, archived=3)


PACKAGES_REFUSED = Problem(
    what="the dev releases could not be read",
    why="GitHub refused the container packages",
    details=(
        ProblemDetail(call="the container packages of the organisation", status=403, message="Forbidden"),
    ),
)
COMPARISON_FAILED = Problem(
    what="one comparison could not be read",
    why="GitHub answered with an error for one repository",
    details=(ProblemDetail(call="handbook: main compared with develop", status=502, message="Bad gateway"),),
)
OUTSTANDING = Problem(
    what="GitHub did not answer within the wait",
    why="two calls were still outstanding when the wait ran out",
    details=(
        ProblemDetail(call="the open pull requests of each repository", status=None, message=None),
        ProblemDetail(call="the container packages of the organisation", status=None, message=None),
    ),
)
SEARCH_REFUSED = Problem(
    what="the open pull requests could not be read",
    why="GitHub refused the search",
    details=(ProblemDetail(call="the search for open pull requests", status=403, message="Forbidden"),),
)


def failures(moment: datetime = MOMENT) -> Snapshot:
    """A gather complete within the wait in which the packages were refused and one comparison failed."""
    base = live_like(moment)
    repositories = []
    for repo in base.repositories:
        changed = {"dev_release": NOT_GATHERED}
        if repo.name == full("handbook"):
            changed["unreleased"] = Unreleased(pull_requests=NOT_GATHERED, documentation=NOT_GATHERED)
            changed["readiness"] = NOT_GATHERED
        repositories.append(_replace(repo, changed))
    return snapshot(
        repositories,
        moment=moment,
        duration_seconds=4.7,
        problems=[PACKAGES_REFUSED, COMPARISON_FAILED],
        remaining=118,
    )


def timed_out(moment: datetime = MOMENT) -> Snapshot:
    """A gather not complete within the wait, after the list of the seventeen names had arrived."""
    base = live_like(moment)
    repositories = [
        _replace(
            repo,
            {
                "dev_release": NOT_GATHERED,
                "pull_requests": NOT_GATHERED,
                "working_branches": NOT_GATHERED,
                "open_issues": NOT_GATHERED,
            },
        )
        for repo in base.repositories
    ]
    return snapshot(
        repositories,
        moment=moment,
        duration_seconds=7.0,
        completed=False,
        problems=[OUTSTANDING],
        remaining=None,
        expires_in_days=None,
    )


def no_repositories(moment: datetime = MOMENT) -> Snapshot:
    """A gather not complete before the list of repositories arrived: the columns and no rows (R11)."""
    return snapshot(
        [],
        moment=moment,
        duration_seconds=7.0,
        completed=False,
        archived=None,
        problems=[OUTSTANDING],
        remaining=None,
        expires_in_days=None,
    )


def expiring_soon(moment: datetime = MOMENT) -> Snapshot:
    """A gather whose token expires within the warning, which the status bar turns yellow."""
    return snapshot(live_like(moment).repositories, moment=moment, expires_in_days=11)


def _replace(repo: Repository, changes: dict[str, object]) -> Repository:
    return replace(repo, **changes)  # type: ignore[arg-type]


# The gather of the open pull requests alone.


def open_pull_request(
    name: str, number: int, title: str, status: PullRequestStatus = PullRequestStatus.READY
) -> OpenPullRequest:
    return OpenPullRequest(
        repository=full(name), title=title, pull_request=pull_request(name, number, status)
    )


OPEN = (
    open_pull_request("conception-space", 61, "feat: the atlas generator", PullRequestStatus.READY),
    open_pull_request("deco-assaying", 24, "chore: bump pytest", PullRequestStatus.BEHIND),
    open_pull_request("hazel-tracking", 2, "feat: gather from GitHub", PullRequestStatus.CHECKS_RUNNING),
    open_pull_request("hazel-tracking", 3, "feat: the page", PullRequestStatus.DRAFT),
)

ARRIVED = open_pull_request("handbook", 12, "docs: the branching page", PullRequestStatus.CHECKS_RUNNING)


def pull_requests_snapshot(
    pull_requests: Sequence[OpenPullRequest] | None,
    *,
    moment: datetime = MOMENT,
    duration_seconds: float = 0.7,
    completed: bool = True,
    problems: Sequence[Problem] = (),
    remaining: int | None = 4831,
) -> PullRequestsSnapshot:
    return PullRequestsSnapshot(
        began_at=moment,
        duration_seconds=duration_seconds,
        completed=completed,
        pull_requests=NOT_GATHERED if pull_requests is None else Gathered(tuple(pull_requests)),
        problems=tuple(problems),
        rate_limit=None
        if remaining is None
        else RateLimit(remaining=remaining, resets_at=moment + timedelta(minutes=44)),
    )


def open_pull_requests(moment: datetime = MOMENT) -> PullRequestsSnapshot:
    """The tab as the live-like gather leaves it."""
    return pull_requests_snapshot(OPEN, moment=moment)


def watch_sees_a_change(moment: datetime = MOMENT) -> list[PullRequestsSnapshot]:
    """The first gather is the baseline; the second carries a pull request that has arrived."""
    return [
        pull_requests_snapshot(OPEN, moment=moment),
        pull_requests_snapshot([*OPEN, ARRIVED], moment=moment + timedelta(seconds=10)),
    ]


def watch_sees_a_status_change(moment: datetime = MOMENT) -> list[PullRequestsSnapshot]:
    """The set is unchanged; the pull request a watch may be started from becomes ready to merge."""
    changed = tuple(
        open_pull_request("hazel-tracking", 2, "feat: gather from GitHub", PullRequestStatus.READY)
        if p.pull_request.number == 2 and p.repository == full("hazel-tracking")
        else p
        for p in OPEN
    )
    return [
        pull_requests_snapshot(OPEN, moment=moment),
        pull_requests_snapshot(changed, moment=moment + timedelta(seconds=10)),
    ]


def watch_from_nothing_gathered(moment: datetime = MOMENT) -> list[PullRequestsSnapshot]:
    """The search had not answered when the watch began: it takes the first list that arrives as
    its baseline, and stops on the change after that."""
    return [
        pull_requests_not_gathered(moment),
        pull_requests_snapshot(OPEN, moment=moment + timedelta(seconds=10)),
        pull_requests_snapshot([*OPEN, ARRIVED], moment=moment + timedelta(seconds=20)),
    ]


def watch_times_out(moment: datetime = MOMENT) -> list[PullRequestsSnapshot]:
    """Nothing changes: the watch gathers the same set until its time runs out."""
    return [pull_requests_snapshot(OPEN, moment=moment + timedelta(seconds=10 * n)) for n in range(60)]


def pull_requests_not_gathered(moment: datetime = MOMENT) -> PullRequestsSnapshot:
    """The search did not answer: the list is greyed and the watch compares nothing (axiom 8)."""
    return pull_requests_snapshot(
        None, moment=moment, duration_seconds=7.0, completed=False, problems=[SEARCH_REFUSED]
    )
