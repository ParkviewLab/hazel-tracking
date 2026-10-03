# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""The page's parts: the brand and the stylesheet, the words and the formatting, the three
views, the status bar, the gather schedule and the watch.

`hazel_tracking.page` assembles them for one browser; nothing here holds state
between browsers, and nothing here reads a source. The views are pure functions
of the contract in `hazel_tracking.model`, so each can be rendered and read in a
test without a browser.
"""
