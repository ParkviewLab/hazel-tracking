# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""GitHub, the one source this version reads: its calls, its words and the facts they feed.

Only this package names GitHub's interfaces. `hazel_tracking.gather` holds the two
entry points and the wait that bounds each gather (D7); the modules here hold the
calls (`calls`), the GraphQL documents (`queries`), the derivations the readings
R1 to R6 rule (`facts`), the wording of a problem (`problems`), the full gather's
collection (`full`) and the gather of the open pull requests alone
(`pull_requests`). Nothing here reaches back into the page.

The division of labour between GitHub's two interfaces has two reasons. GraphQL
answers the repositories and their facts, a page of them to a query, and what the
compared commits belong to. REST answers the organisation's container packages and
their versions, which GraphQL does not expose at all, and the comparisons of two
refs, whose counts GraphQL refuses to a token without the `repo` scope, which this
token does not have and by ruling D10 must not have (docs/decisions.md, 2026-10-03).
"""
