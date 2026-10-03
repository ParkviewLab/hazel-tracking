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


@dataclass(frozen=True)
class Reply:
    """What one call gave: `data` where GitHub answered, which for GraphQL is the answer's
    `data` and may be partial, and `failure` where something went wrong. Both are set where a
    GraphQL answer carried errors beside data."""

    call: str
    data: Any = None
    failure: Failure | None = None

    @property
    def ok(self) -> bool:
        return self.failure is None


def redact(text: str | None, token: str | None) -> str | None:
    """`text` on one line, shortened to `MESSAGE_LIMIT`, with the token named in general terms
    wherever it appears, and `None` where nothing is left."""
    if text is None:
        return None
    shortened = " ".join(text.split())[:MESSAGE_LIMIT]
    if token:
        shortened = shortened.replace(token, "the GitHub token")
    return shortened or None


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

    @property
    def outstanding(self) -> tuple[str, ...]:
        """Every call sent and not yet answered, in name order: what R11's problem names when
        the wait runs out."""
        return tuple(sorted(call for call, count in self._in_flight.items() if count > 0))

    async def graphql(self, call: str, operation: str, document: str, variables: Mapping[str, Any]) -> Reply:
        """One GraphQL call, named for the dialog by `call` and for GitHub by `operation`."""
        body = {"query": document, "variables": dict(variables), "operationName": operation}
        sent = await self._send(call, "POST", GRAPHQL_PATH, json=body, headers=_GRAPHQL_HEADERS)
        if isinstance(sent, Failure):
            return Reply(call=call, failure=sent)
        payload = self._read(call, sent)
        if isinstance(payload, Failure):
            return Reply(call=call, failure=payload)
        if not isinstance(payload, Mapping):
            return Reply(call=call, failure=self._unreadable(call, sent.status_code))
        self._read_rate_limit(call, sent, payload)
        data = payload.get("data")
        errors = payload.get("errors")
        if sent.status_code >= 400 or errors:
            return Reply(call=call, data=data, failure=self._graphql_failure(call, sent, errors))
        return Reply(call=call, data=data)

    async def rest(self, call: str, path: str, params: Mapping[str, Any] | None = None) -> Reply:
        """One REST call."""
        sent = await self._send(call, "GET", path, params=params, headers=_REST_HEADERS)
        if isinstance(sent, Failure):
            return Reply(call=call, failure=sent)
        if sent.status_code >= 400:
            return Reply(call=call, failure=self._rest_failure(call, sent))
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
        logger.warning("the list for %s is longer than %s pages and was read that far", call, PAGE_LIMIT)
        return items, None

    async def _send(
        self,
        call: str,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json: Any = None,
        headers: Mapping[str, str] | None = None,
    ) -> httpx.Response | Failure:
        """The one place a request is made. A call cut short by the wait is cancelled here, and
        is struck off neither list, so that `outstanding` still names it."""
        self._in_flight[call] = self._in_flight.get(call, 0) + 1
        try:
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
        listed = [error for error in errors if isinstance(error, Mapping)] if isinstance(errors, list) else []
        if any(error.get("type") == "RATE_LIMITED" for error in listed):
            return Failure(
                call=call,
                kind=FailureKind.RATE_LIMITED,
                status=answer.status_code,
                resets_at=self._resets_at(answer),
            )
        message = next((error.get("message") for error in listed if error.get("message")), None)
        kind = self._kind(answer, FailureKind.ERROR)
        return Failure(
            call=call,
            kind=kind,
            status=answer.status_code,
            message=None if kind is FailureKind.RATE_LIMITED else self._message(message),
            resets_at=self._resets_at(answer) if kind is FailureKind.RATE_LIMITED else None,
        )

    def _rest_failure(self, call: str, answer: httpx.Response) -> Failure:
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
