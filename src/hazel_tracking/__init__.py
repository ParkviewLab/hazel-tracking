# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""hazel-tracking: the ParkviewLab Engineering Dashboard.

One page, served on the home network, showing the present state of every
repository of the ParkviewLab organisation, gathered from GitHub each time it
is shown and stored nowhere. docs/what-it-shows.md specifies the page, and
`model.py` is the contract between the gathering and the page.
"""

from hazel_tracking.config import VERSION

__version__ = VERSION
__all__ = ["VERSION", "__version__"]
