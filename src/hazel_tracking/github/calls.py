# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""The calls to GitHub: the HTTP mechanics in one place, so that the rest of the gathering
reads answers and never a request.

`Reader` sends every call through the `httpx.AsyncClient` it is given, whose base
URL and `Authorization` header `app.py` set, and answers with a `Reply`: the data
where GitHub answered, a `Failure` where it did not, and both where a GraphQL
answer carried errors beside partial data. Nothing here raises for a call that
failed, so that a gather which loses one call keeps the rest (northstar, axiom 8).

Three things are taken from the answers as they arrive. GitHub's rate limit, which
the status bar shows, comes from the GraphQL answers' own `rateLimit`, the budget
a gather spends; REST's budget is a different one, so a REST answer's
`x-ratelimit-*` headers are read only to say when a refusal resets. When the token
expires comes from the `github-authentication-token-expiration` header of any
answer. And a call cancelled when the wait runs out stays in `outstanding`, which
is the list R11's problem names: only a call that answered, or failed, is struck
off.

The token itself is never read here beyond `redact`, which every message that
leaves this module passes through, so that a credential cannot reach a problem, a
log record or an exception message (docs/what-it-shows.md, "Constraints").
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

import httpx

from hazel_tracking.config import Config
from hazel_tracking.model import RateLimit

logger = logging.getLogger(__name__)

GRAPHQL_PATH = "/graphql"

# The header GitHub sends for a classic token, such as "2027-09-18 00:00:00 UTC".
EXPIRY_HEADER = "github-authentication-token-expiration"

# A REST list is read a hundred items at a time, by page number rather than by the `Link`
# header, so that the end of a list is one condition: a page shorter than a full one.
REST_PAGE = 100
# A guard, not a definition: no list the lab holds runs to this many pages, and a source
# that never ends must not hold a gather open.
PAGE_LIMIT = 20
# How many REST calls a gather has in flight at once. The comparisons are one call a repository
# and one a working branch, which for the lab is some two dozen; GitHub asks a client to keep its
# concurrent calls modest, and nothing here is the faster for exceeding that.
REST_AT_ONCE = 8
# A source's own message is carried this far and no further.
MESSAGE_LIMIT = 300

# `mergeStateStatus` came in under this preview and is asked for with it still, as GitHub's
# own clients do.
_GRAPHQL_HEADERS = {"Accept": "application/vnd.github.merge-info-preview+json"}
_REST_HEADERS = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}


class FailureKind(StrEnum):
    """Why a call failed, in the terms a problem's sentence is written from (`problems.py`)."""

    NO_ANSWER = "no answer"
    TOKEN_REFUSED = "the token was refused"
    REFUSED = "refused"
    RATE_LIMITED = "the rate limit is spent"
    NOT_FOUND = "nothing to read"
    FAILED = "GitHub failed"
    SCOPE_REFUSED = "the token lacks a scope"
    TOO_LONG = "longer than one gather reads"
    UNREADABLE = "the answer could not be read"
    ERROR = "GitHub answered with an error"


@dataclass(frozen=True)
class Failure:
    """One call that did not give what it was asked for: which call, why, the HTTP status
    where an answer came, the source's own message where it gave one (redacted), and when the
    budget resets where the refusal was for the rate limit."""

    call: str
    kind: FailureKind
    status: int | None = None
    message: str | None = None
    resets_at: datetime | None = None
    paths: tuple[tuple[Any, ...], ...] = ()
    """Where in the answer the errors fell, as GraphQL's `path` names it: the first element is the
    alias of the target the call asked for, so a call for many targets can lose one and keep the
    rest. An answer whose errors name no path at all is a loss of every target of that call."""


@dataclass(frozen=True)
class Reply:
    """What one call gave: `data` where GitHub answered, which for GraphQL is the answer's
    `data` and may be partial, and `failure` where something went wrong. Both are set where a
    GraphQL answer carried errors beside data."""

    call: str
    data: Any = None
    failure: Failure | None = None


def redact(text: str | None, token: str | None) -> str | None:
    """`text` on one line, with the token named in general terms wherever it appears, shortened to
    `MESSAGE_LIMIT`, and `None` where nothing is left.

    The order matters: shortening first would cut a token that straddles the limit in two and leave
    the first half standing.
    """
    if text is None:
        return None
    named = " ".join(text.split())
    if token:
        named = named.replace(token, "the GitHub token")
    return named[:MESSAGE_LIMIT] or None


def aware(moment: str | None) -> datetime | None:
    """An ISO 8601 instant as GitHub writes it (`2026-10-03T14:03:12Z`), aware; `None` where it
    is absent or not an instant."""
    if not moment:
        return None
    try:
        read = datetime.fromisoformat(moment.strip())
    except ValueError:
        return None
    return read if read.tzinfo is not None else read.replace(tzinfo=UTC)


def expiry(value: str | None) -> datetime | None:
    """The token's expiry as GitHub's header writes it, aware.

    Two forms are read: a space-separated instant with a named zone, "2027-09-18 00:00:00 UTC",
    and ISO 8601 with an offset. Anything else, and an absent header, give `None`, since the
    page shows an expiry only where GitHub reported one.
    """
    if value is None:
        return None
    text = value.strip()
    for zone in (" UTC", " GMT"):
        if text.upper().endswith(zone):
            return aware(f"{text[: -len(zone)].strip()}+00:00")
    return aware(text)


def dig(data: Any, *keys: str) -> Any:
    """`data[k1][k2]…` where every step is a mapping, and `None` at the first step that is not:
    GitHub's answers hold nulls wherever a repository, a ref or a rollup is absent, and a
    partial answer holds more of them, so every reading of them goes through here."""
    found = data
    for key in keys:
        if not isinstance(found, Mapping):
            return None
        found = found.get(key)
    return found


def nodes(connection: Any) -> list[Any]:
    """A connection's nodes, and an empty list where the connection or its nodes are absent."""
    found = dig(connection, "nodes")
    return [node for node in found if node is not None] if isinstance(found, list) else []


def page_cursor(connection: Any) -> str | None:
    """The cursor to read a connection's next page from, and `None` where it has no next page."""
    info = dig(connection, "pageInfo")
    if not isinstance(info, Mapping) or not info.get("hasNextPage"):
        return None
    end = info.get("endCursor")
    return end if isinstance(end, str) else None


@dataclass
class Reader:
    """GitHub, read through one client. One `Reader` serves one gather, and holds what that
    gather learned about its own budget and credential."""

    cfg: Config
    client: httpx.AsyncClient
    rate_limit: RateLimit | None = None
    credential_expires_at: datetime | None = None
    _in_flight: dict[str, int] = field(default_factory=dict, repr=False)
    _rest_at_once: asyncio.Semaphore = field(
        default_factory=lambda: asyncio.Semaphore(REST_AT_ONCE), repr=False
    )

    @property
    def outstanding(self) -> tuple[str, ...]:
        """Every call sent and not yet answered, in name order: what R11's problem names when
        the wait runs out."""
        return tuple(sorted(call for call, count in self._in_flight.items() if count > 0))

    async def graphql(self, call: str, operation: str, document: str, variables: Mapping[str, Any]) -> Reply:
        """One GraphQL call, named for the dialog by `call` and for GitHub by `operation`.

        An answer refused at the HTTP level is read as such before its body is parsed, since a 502
        from a proxy carries no JSON at all; a GraphQL answer's own errors come with status 200.
        """
        body = {"query": document, "variables": dict(variables), "operationName": operation}
        sent = await self._send(call, "POST", GRAPHQL_PATH, json=body, headers=_GRAPHQL_HEADERS)
        if isinstance(sent, Failure):
            return Reply(call=call, failure=sent)
        if sent.status_code >= 400:
            return Reply(call=call, failure=self._http_failure(call, sent))
        payload = self._read(call, sent)
        if isinstance(payload, Failure):
            return Reply(call=call, failure=payload)
        if not isinstance(payload, Mapping):
            return Reply(call=call, failure=self._unreadable(call, sent.status_code))
        self._read_rate_limit(call, sent, payload)
        data = payload.get("data")
        if payload.get("errors"):
            return Reply(call=call, data=data, failure=self._graphql_failure(call, sent, payload["errors"]))
        return Reply(call=call, data=data)

    async def rest(self, call: str, path: str, params: Mapping[str, Any] | None = None) -> Reply:
        """One REST call, no more than `REST_AT_ONCE` of them in flight at a time.

        A call waiting for its turn is outstanding from the moment it is made, not from the moment
        it is sent, so that the wait running out names it (R11).
        """
        sent = await self._send(
            call, "GET", path, params=params, headers=_REST_HEADERS, at_once=self._rest_at_once
        )
        if isinstance(sent, Failure):
            return Reply(call=call, failure=sent)
        if sent.status_code >= 400:
            return Reply(call=call, failure=self._http_failure(call, sent))
        payload = self._read(call, sent)
        if isinstance(payload, Failure):
            return Reply(call=call, failure=payload)
        return Reply(call=call, data=payload)

    async def rest_list(
        self, call: str, path: str, params: Mapping[str, Any] | None = None
    ) -> tuple[list[Any], Failure | None]:
        """A REST list read to its end: every item of every page, and the failure where a page
        gave none, after which the items of the pages that answered are returned as they are."""
        items: list[Any] = []
        for page in range(1, PAGE_LIMIT + 1):
            reply = await self.rest(call, path, {**(params or {}), "per_page": REST_PAGE, "page": page})
            if reply.failure is not None:
                return items, reply.failure
            if not isinstance(reply.data, list):
                return items, self._unreadable(call, None)
            items.extend(reply.data)
            if len(reply.data) < REST_PAGE:
                return items, None
        logger.warning("the list for %s runs past %s pages and was not read whole", call, PAGE_LIMIT)
        return items, self.too_long(call)

    def too_long(self, call: str) -> Failure:
        """The failure a list longer than `PAGE_LIMIT` pages makes: it was not read whole, so the
        fact it feeds is not gathered rather than counted short (R7)."""
        return Failure(
            call=call,
            kind=FailureKind.TOO_LONG,
            message=f"the list runs past the {PAGE_LIMIT} pages one gather reads",
        )

    async def _send(
        self,
        call: str,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json: Any = None,
        headers: Mapping[str, str] | None = None,
        at_once: asyncio.Semaphore | None = None,
    ) -> httpx.Response | Failure:
        """The one place a request is made. A call cut short by the wait is cancelled here, and
        is struck off neither list, so that `outstanding` still names it; `at_once` bounds how many
        calls of its kind are in flight, and waiting for it counts as outstanding too."""
        self._in_flight[call] = self._in_flight.get(call, 0) + 1
        try:
            if at_once is not None:
                async with at_once:
                    answer = await self.client.request(
                        method, path, params=params, json=json, headers=headers
                    )
            else:
                answer = await self.client.request(method, path, params=params, json=json, headers=headers)
        except httpx.HTTPError as refusal:
            self._answered(call)
            # The exception's own message can name the address it was sent to; its kind cannot.
            logger.warning("the call for %s gave no answer (%s)", call, type(refusal).__name__)
            return Failure(call=call, kind=FailureKind.NO_ANSWER)
        self._answered(call)
        self.credential_expires_at = expiry(answer.headers.get(EXPIRY_HEADER)) or self.credential_expires_at
        logger.debug("the call for %s answered %s", call, answer.status_code)
        return answer

    def _answered(self, call: str) -> None:
        self._in_flight[call] = max(0, self._in_flight.get(call, 0) - 1)

    def _read(self, call: str, answer: httpx.Response) -> Any | Failure:
        try:
            return answer.json()
        except ValueError:
            logger.warning("the answer for %s was not JSON", call)
            return self._unreadable(call, answer.status_code)

    def _unreadable(self, call: str, status: int | None) -> Failure:
        return Failure(
            call=call,
            kind=FailureKind.UNREADABLE,
            status=status,
            message="GitHub's answer was not of the shape the call expects",
        )

    def _graphql_failure(self, call: str, answer: httpx.Response, errors: Any) -> Failure:
        """The failure a GraphQL answer's own errors make, which come with status 200: the kind the
        errors name, the first message, and every path they fell at."""
        listed = [error for error in errors if isinstance(error, Mapping)] if isinstance(errors, list) else []
        message = next((error.get("message") for error in listed if error.get("message")), None)
        paths = tuple(
            tuple(error["path"]) for error in listed if isinstance(error.get("path"), list) and error["path"]
        )
        types = {error.get("type") for error in listed}
        if "INSUFFICIENT_SCOPES" in types:
            # GraphQL refuses a field the credential's scopes do not reach with status 200 and an
            # error of this type, as it does `Ref.compare`'s counts to a token without `repo`.
            kind = FailureKind.SCOPE_REFUSED
        elif "RATE_LIMITED" in types:
            kind = FailureKind.RATE_LIMITED
        else:
            kind = FailureKind.ERROR
        return Failure(
            call=call,
            kind=kind,
            status=answer.status_code,
            message=None if kind is FailureKind.RATE_LIMITED else self._message(message),
            resets_at=self._resets_at(answer) if kind is FailureKind.RATE_LIMITED else None,
            paths=paths,
        )

    def _http_failure(self, call: str, answer: httpx.Response) -> Failure:
        """The failure an answer refused at the HTTP level makes, whatever its body: the status says
        the kind, and the body's own `message`, where it has one, tells a refusal for the rate limit
        from a refusal of the credential."""
        body: Any
        try:
            body = answer.json()
        except ValueError:
            body = None
        message = dig(body, "message")
        kind = self._kind(answer, FailureKind.REFUSED, message if isinstance(message, str) else None)
        return Failure(
            call=call,
            kind=kind,
            status=answer.status_code,
            message=None if kind is FailureKind.RATE_LIMITED else self._message(message),
            resets_at=self._resets_at(answer) if kind is FailureKind.RATE_LIMITED else None,
        )

    def _kind(
        self, answer: httpx.Response, otherwise: FailureKind, message: str | None = None
    ) -> FailureKind:
        """Why the call failed, as its status says. A refusal for the rate limit comes as 429, or
        as 403 with the budget spent or the limit named, which tells it from a refusal of the
        credential's scope; GraphQL's own refusal comes as an error with status 200 instead."""
        status = answer.status_code
        if status == 429:
            return FailureKind.RATE_LIMITED
        if status == 403:
            spent = answer.headers.get("x-ratelimit-remaining") == "0" or "retry-after" in answer.headers
            if spent or (message and "rate limit" in message.lower()):
                return FailureKind.RATE_LIMITED
            return FailureKind.REFUSED
        if status == 401:
            return FailureKind.TOKEN_REFUSED
        if status == 404:
            return FailureKind.NOT_FOUND
        if status >= 500:
            return FailureKind.FAILED
        if status >= 400:
            return FailureKind.REFUSED
        return otherwise

    def _message(self, message: Any) -> str | None:
        return redact(message, self.cfg.github_token) if isinstance(message, str) else None

    def _resets_at(self, answer: httpx.Response) -> datetime | None:
        """When the budget the call was refused from resets: GitHub's `x-ratelimit-reset`, an
        instant in epoch seconds, or `retry-after`, a number of seconds from now."""
        reset = answer.headers.get("x-ratelimit-reset")
        if reset:
            try:
                return datetime.fromtimestamp(int(reset), UTC)
            except ValueError:
                pass
        after = answer.headers.get("retry-after")
        if after:
            try:
                return datetime.now(UTC) + timedelta(seconds=float(after))
            except ValueError:
                return None
        return None

    def _read_rate_limit(self, call: str, answer: httpx.Response, payload: Mapping[str, Any]) -> None:
        """The budget as this answer reported it, which the next answer replaces: the GraphQL
        `rateLimit` the queries ask for, or, where the answer carried none, the headers of the
        same budget."""
        reported = dig(payload, "data", "rateLimit")
        remaining, resets_at = dig(reported, "remaining"), aware(dig(reported, "resetAt"))
        if not isinstance(remaining, int) or resets_at is None:
            remaining = _int(answer.headers.get("x-ratelimit-remaining"))
            reset = _int(answer.headers.get("x-ratelimit-reset"))
            resets_at = datetime.fromtimestamp(reset, UTC) if reset is not None else None
        if isinstance(remaining, int) and resets_at is not None:
            self.rate_limit = RateLimit(remaining=remaining, resets_at=resets_at)
        cost = dig(reported, "cost")
        if cost is not None:
            logger.debug("the call for %s cost %s of the budget, %s left", call, cost, remaining)


def _int(value: str | None) -> int | None:
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None
