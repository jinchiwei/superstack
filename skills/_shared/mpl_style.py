"""Canonical matplotlib styling for Jin's figures.

ONE WAY to style figures across all projects -- do NOT hand-roll rcParams or
inline colors in plot scripts. Import from here:

    import sys
    sys.path.insert(0, "/home/jiwei/arcadia/superstack/skills/_shared")
    from mpl_style import apply_style, title, palette, TURQUOISE, DEEPPINK, AMBER, GOLD, BLUEVIOLET

    apply_style()                  # call once before any pyplot calls
    ax.bar(...)                    # axes prop_cycle picks brand colors in priority order
    title(ax, "My chart")          # black Geist Mono title (default)

Brand rules baked in (per feedback_brand_spec_applies_everywhere):

  * Titles / suptitles / panel labels  -> Geist Mono, BLACK
  * Body text (axis labels, ticks, legends, annotations) -> Geist sans, BLACK
  * Data marks (bars, lines, markers)  -> brand palette by priority:
        1) turquoise  #40E0D0
        2) deeppink   #FF1493
        3) amber      #F0C840   (use GOLD = matplotlib 'gold' for SOLID FILLS)
        4) blueviolet #8A2BE2
  * Single-variable charts: use ONE color (the highest-priority unused: turquoise).
  * Multi-series / multi-model charts: cycle through the palette in the order above.
  * Errorbar / annotation text: black; only data marks may be colored.

This module's `apply_style()` enforces the text-color and font-family parts;
the prop_cycle handles default series colors. Always still pass `color=`
explicitly when you want a specific category mapping (e.g., turquoise = in-dist,
deeppink = shifted).
"""
from __future__ import annotations

import matplotlib as mpl

# Pull canonical colors from the same source the build-* skills use,
# so a change in one place propagates everywhere.
try:
    from branding import AMBER, BLUEVIOLET, DEEPPINK, TURQUOISE  # type: ignore
except ImportError:  # standalone use without sys.path setup
    TURQUOISE = "#40E0D0"
    DEEPPINK = "#FF1493"
    AMBER = "#F0C840"
    BLUEVIOLET = "#8A2BE2"

# `gold` (matplotlib named color) is the SOLID-FILL substitute for amber per
# Jin's global guideline: amber for lines/outlines/text, gold for filled patches.
GOLD = "gold"

# Ordered palettes
PALETTE_LINES = [TURQUOISE, DEEPPINK, AMBER, BLUEVIOLET]
PALETTE_FILLS = [TURQUOISE, DEEPPINK, GOLD, BLUEVIOLET]

# Font stacks (use the same Latin fonts as the build-* skills)
FONT_BODY = ["Geist", "DejaVu Sans"]
FONT_TITLE = ["Geist Mono", "DejaVu Sans Mono"]


def apply_style() -> None:
    """Apply Jin's matplotlib defaults: black text, Geist body, brand prop cycle.

    For FIGURES intended for documents (papers, lab writeups, manuscripts):
        - titles black Geist Mono
        - body text black Geist
        - data colors brand palette priority

    Slides (pptx) get aesthetic latitude in their build-* templates; this is
    only for matplotlib figure output.
    """
    mpl.rcParams.update({
        # body fonts
        "font.family": FONT_BODY,
        # color discipline
        "text.color": "black",
        "axes.labelcolor": "black",
        "axes.titlecolor": "black",
        "xtick.color": "black",
        "ytick.color": "black",
        # title weight/size
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.labelsize": 11,
        # axes
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.prop_cycle": mpl.cycler(color=PALETTE_LINES),
        "axes.grid": True,
        "grid.alpha": 0.25,
        "grid.linewidth": 0.5,
        # legend / ticks
        "legend.frameon": False,
        "legend.fontsize": 9,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        # output
        "figure.dpi": 110,
        "savefig.dpi": 200,
        "savefig.bbox": "tight",
    })


def title(ax, text: str, *, color: str = "black") -> None:
    """Black Geist Mono title -- the figure brand spec."""
    ax.set_title(text, fontfamily=FONT_TITLE, color=color, weight="bold")


def palette(n: int, *, kind: str = "fills") -> list[str]:
    """Return the first n colors from the chosen palette (cycles if n > 4)."""
    base = PALETTE_FILLS if kind == "fills" else PALETTE_LINES
    if n <= len(base):
        return base[:n]
    return [base[i % len(base)] for i in range(n)]


__all__ = [
    "TURQUOISE", "DEEPPINK", "AMBER", "GOLD", "BLUEVIOLET",
    "PALETTE_LINES", "PALETTE_FILLS",
    "FONT_BODY", "FONT_TITLE",
    "apply_style", "title", "palette",
]
