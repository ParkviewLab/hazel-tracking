# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""The brand and the stylesheet: the vendored mark, the vendored display face, the palette
and the one `<style>` the page puts in its head.

Nothing is fetched. The mark and Michroma are vendored from the handbook's brand
under `brand/`, as paper-boxing vendors them, and both are embedded in the page:
the font as a `data:` URI in an `@font-face`, the mark as inline SVG whose own
`@import` of the face is replaced with that declaration before it is served. The
two files keep their own licences, outside the repository's dual licence, and
`REUSE.toml` annotates them.

The palette carries the rule of docs/what-it-shows.md, "Colour and shape": three
colours carry state, sage for passing and ready, yellow for running and pending
and red for failing and conflicts, each state also carrying its own word or
shape; grey carries only data not gathered. The chrome sits on the page's own
ground, as prima-dev-dashboard's does. Secondary text is the teal-tinted `--muted`, never the grey, so that grey
on the page means one thing.
"""

from __future__ import annotations

import base64
import html
from functools import cache
from importlib import resources

# The brand's own values (the handbook's docs/brand.md).
TEAL_DEEP = "#004f52"
TEAL = "#00C2C7"
SAGE = "#90b095"
YELLOW = "#F2B33D"
RED = "#E2483D"

# The ground the page is drawn on, as the dashboard this one succeeds was tuned.
BACKGROUND = "#0f2328"
PANEL = "#16333d"
LINE = "#1f414d"
TEXT = "#dcebee"
MUTED = "#7d98a0"
# Data not gathered: a neutral grey, told from the teal-tinted secondary text at a glance.
GREY = "#9c9c9c"

# No type on the page is smaller than this (docs/what-it-shows.md, "Constraints").
MINIMUM_TYPE_PX = 12

_BRAND = resources.files("hazel_tracking.ui").joinpath("brand")
_GOOGLE_IMPORT = "@import url('https://fonts.googleapis.com/css2?family=Michroma&amp;display=swap');"


@cache
def _michroma_face() -> str:
    """The `@font-face` for Michroma with the vendored file embedded, so nothing is fetched.

    Read and encoded once for the life of the process: it is the same 11 kB for every browser,
    and the page puts it both in its own head and inside the mark's own markup.
    """
    font = base64.b64encode(_BRAND.joinpath("fonts", "michroma-latin.woff2").read_bytes()).decode("ascii")
    return (
        "@font-face{font-family:'Michroma';font-style:normal;font-weight:400;"
        f"src:url('data:font/woff2;base64,{font}') format('woff2');}}"
    )


def logo_svg(height_px: int = 70) -> str:
    """The horizontal mark, white artwork for the chrome's dark ground, at `height_px` tall.

    The file is prima-dev-dashboard's copy of the handbook's mark, its canvas cropped to
    the artwork (478 by 145), so it fills `height_px` as prima-dev-dashboard's does. It
    `@import`s its wordmark face from Google Fonts; that line is replaced with the
    embedded face, so the page fetches nothing.
    """
    svg = _BRAND.joinpath("parkview-lab.svg").read_text(encoding="utf-8")
    if _GOOGLE_IMPORT not in svg:
        raise RuntimeError("the vendored mark no longer carries the font import this code replaces")
    svg = svg.replace(_GOOGLE_IMPORT, _michroma_face(), 1)
    box_width, box_height = 478.28751, 145.34091
    width_px = round(height_px * box_width / box_height)
    return svg.replace(
        f'width="{box_width}"\n   height="{box_height}"',
        f'width="{width_px}"\n   height="{height_px}"',
        1,
    )


# The chrome's display name and running version, both in Michroma at one size, centred together
# between the logo and the data's age, the version in the muted colour, as prima-dev-dashboard
# sets its title (the owner's ruling of 2026-10-03).
NAME_PX = 18
VERSION_PX = 18
_BRAND_PART = "font-family:'Michroma',sans-serif; font-size:{size}px; font-weight:400; letter-spacing:.06em"
# The chrome's Refresh, prima-dev-dashboard's button colour; it is chrome and carries no state.
REFRESH_COLOUR = "#5898d4"
# The version's colour, prima-dev-dashboard's dimmed title.
VERSION_COLOUR = "#6d838a"


def brand_name_html(name: str) -> str:
    """The chrome's display name, at `NAME_PX`."""
    return f'<span style="{_BRAND_PART.format(size=NAME_PX)}">{html.escape(name)}</span>'


def brand_version_html(version: str) -> str:
    """The chrome's running version, at `VERSION_PX`, read "v<version>"."""
    style = _BRAND_PART.format(size=VERSION_PX) + f"; color:{VERSION_COLOUR}"
    return f'<span style="{style}">v{html.escape(version)}</span>'


_STYLESHEET = """
:root {{
  --bg:{background}; --panel:{panel}; --line:{line};
  --text:{text}; --muted:{muted}; --grey:{grey};
  --sage:{sage}; --yellow:{yellow}; --red:{red};
  --teal-deep:{teal_deep}; --teal:{teal};
}}
/* The ground is the page's own, not the dark theme's default, which is why the rule names the
   class Quasar puts on the body as well. */
body, body.body--dark {{ background:var(--bg) !important; color:var(--text);
  font:13px/1.35 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }}
.nicegui-content {{ padding:0; gap:0; }}
.brand-face {{ font-family:'Michroma',sans-serif; letter-spacing:.04em; }}

/* The tabs fill what the chrome and the status bar leave, and each panel scrolls inside itself. */
.q-tab-panels, .q-tab-panels > .q-panel-parent {{ height:100%; background:transparent; }}
.q-tab-panel {{ padding:0; height:100%; overflow-y:auto; overflow-x:hidden; background:transparent; }}

/* The three views share one table. */
table.sheet {{ border-collapse:collapse; width:100%; table-layout:auto; }}
table.sheet th {{ position:sticky; top:0; z-index:1; background:var(--bg);
  text-align:left; font-size:12px; font-weight:600; letter-spacing:.06em; text-transform:uppercase;
  color:var(--muted); padding:5px 10px; border-bottom:1px solid var(--line); white-space:nowrap; }}
table.sheet td {{ padding:4px 10px; border-bottom:1px solid var(--line);
  vertical-align:top; white-space:nowrap; }}
/* The overview holds a line per repository within one screen, so its lines are tighter; the
   type is the same size, since nothing on the page goes under 12 px. */
table.sheet.compact td {{ padding:3px 10px; }}
table.sheet.compact th {{ padding:4px 10px; }}
table.sheet tr.quiet td {{ color:var(--muted); }}
table.sheet tr.quiet td.repo a {{ color:var(--muted); }}
td.repo a, a.plain {{ color:var(--text); text-decoration:none; font-weight:600; }}
td.repo a:hover, a.plain:hover {{ text-decoration:underline; }}

.sub {{ color:var(--muted); font-size:12px; }}
.strong {{ font-weight:600; }}
.sage {{ color:var(--sage); }}
.yellow {{ color:var(--yellow); }}
.red {{ color:var(--red); }}
/* Data not gathered: zeroed, grey and italic, so it reads as a non-value without colour (R7). */
.ungathered {{ color:var(--grey); font-style:italic; }}
.mark {{ font-style:normal; }}
.line {{ display:block; }}
.chip {{ display:inline-block; margin-right:10px; }}
.chip:last-child {{ margin-right:0; }}

.statusbar {{ font-size:12px; color:var(--muted); }}
.statusbar .yellow {{ color:var(--yellow); }}
.statusbar .red {{ color:var(--red); }}
.problem-what {{ color:var(--text); font-weight:600; font-size:13px; }}
.problem-why {{ color:var(--text); font-size:13px; }}
.problem-detail {{ color:var(--muted); font-size:12px; }}
/* The pull requests are the detail's table again, as wide as the tab, its columns fixed so that
   every line's Watch stands in one column at the right however long the title beside it is. */
table.sheet.prlist {{ table-layout:fixed; }}
table.sheet.prlist td {{ vertical-align:baseline; }}
table.sheet.prlist .prcol-repo {{ width:200px; }}
table.sheet.prlist .prcol-title {{ width:auto; white-space:normal; word-break:break-word; }}
table.sheet.prlist .prcol-status {{ width:170px; }}
table.sheet.prlist .prcol-watch {{ width:110px; text-align:right; }}
/* A line's own Watch is small, but no type on the page goes under 12 px, so its size is set
   here rather than taken from the button's own `size` property. */
.prcol-watch .q-btn {{ font-size:12px; min-height:22px; padding:0 8px; }}

.wrap {{ white-space:normal; }}
.tabbar {{ border-bottom:1px solid var(--line); }}
.chrome {{ background:var(--bg); }}

/* Every gather shows a spinner over a scrim: a translucent dimming of what lies beneath, which
   is not the grey that marks data not gathered. The scrim of the pull-requests tab's frame takes
   no pointer, so the tab's own controls stay within reach while the watch gathers. */
.busy {{ background:rgba(15,35,40,.55); }}
.scrim {{ pointer-events:none; }}
.q-tab-panel.framed {{ position:relative; overflow:hidden; }}
.framed-scroll {{ height:100%; overflow:auto; }}
"""


def stylesheet() -> str:
    """The page's own CSS, the palette's values filled in."""
    return _STYLESHEET.format(
        background=BACKGROUND,
        panel=PANEL,
        line=LINE,
        text=TEXT,
        muted=MUTED,
        grey=GREY,
        sage=SAGE,
        yellow=YELLOW,
        red=RED,
        teal_deep=TEAL_DEEP,
        teal=TEAL,
    )


def head_html() -> str:
    """The one `<style>` for the page head: the embedded face and the stylesheet."""
    return f"<style>{_michroma_face()}{stylesheet()}</style>"
