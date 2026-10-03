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

The division of labour between GitHub's two interfaces follows the plan of
2026-09-18: GraphQL for the repositories and their facts, which one query a page
answers, and REST for the organisation's container packages and their versions,
which GraphQL does not expose at all.
"""
