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

  * Titles / suptitles / panel labels  -> Geist Mono, BLACK (LIGHT mode) /
    near-white (DARK mode). Set theme=... to pick.
  * Body text (axis labels, ticks, legends, annotations) -> Geist sans, themed.
  * Data marks (bars, lines, markers)  -> brand palette by priority — the SAME
    on light and dark canvases (the brand-4 palette is designed to work on both):
        1) turquoise  #40E0D0
        2) deeppink   #FF1493
        3) amber      #F0C840   (use GOLD = matplotlib 'gold' for SOLID FILLS)
        4) blueviolet #8A2BE2
  * Single-variable charts: use ONE color (the highest-priority unused: turquoise).
  * Multi-series / multi-model charts: cycle through the palette in the order above.
  * Errorbar / annotation text: themed text color; only data marks may be colored.

Theme-aware usage (figures embedded in a slide deck — match the deck theme so
the figure background blends with the slide canvas instead of being a stark
white rectangle inside a dark slide):

    apply_style(theme="slate")        # dark navy — matches build-pptx "slate"
    T = theme_colors("slate")
    fig.savefig(..., facecolor=T.canvas)
    ax.text(..., color=T.ink_text)

Supported themes (mirror build-pptx themes.py):
  DARK:    "slate", "midnight", "forest"
  LIGHT:   "paper", "bone"
  DEFAULT (when theme=None): "paper" — preserves prior behavior.
"""
from __future__ import annotations

from dataclasses import dataclass

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

# Ordered palettes (identical on light and dark — brand accents work on both)
PALETTE_LINES = [TURQUOISE, DEEPPINK, AMBER, BLUEVIOLET]
PALETTE_FILLS = [TURQUOISE, DEEPPINK, GOLD, BLUEVIOLET]

# Font stacks (use the same Latin fonts as the build-* skills)
FONT_BODY = ["Geist", "DejaVu Sans"]
FONT_TITLE = ["Geist Mono", "DejaVu Sans Mono"]


# ---------------------------------------------------------------------------
# Theme palette (mirrors build-pptx skills/build-pptx/themes.py)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ThemeColors:
    """Color set used by figures intended to match a build-pptx deck theme."""
    name: str
    on_dark: bool       # True → text inverts to light; background is dark
    canvas: str         # figure facecolor — matches the slide canvas
    ink_text: str       # primary text (titles, axis labels, callouts)
    muted_text: str     # secondary text (tick labels, sub-captions)
    rule: str           # axis spines, gridlines, fine dividers
    surface: str        # secondary card / panel fill (lighter than canvas on dark)


THEMES: dict[str, ThemeColors] = {
    # Dark themes ----------------------------------------------------------
    "slate": ThemeColors(
        name="slate", on_dark=True,
        canvas="#1E293B", ink_text="#F1F5F9", muted_text="#94A3B8",
        rule="#334155", surface="#27384F",
    ),
    "midnight": ThemeColors(
        name="midnight", on_dark=True,
        canvas="#14141C", ink_text="#F1F5F9", muted_text="#94A3B8",
        rule="#2A2A40", surface="#1F1F30",
    ),
    "forest": ThemeColors(
        name="forest", on_dark=True,
        canvas="#0F1E17", ink_text="#E5F2E9", muted_text="#86A192",
        rule="#1F3A2E", surface="#152E22",
    ),
    # Light themes ---------------------------------------------------------
    "paper": ThemeColors(
        name="paper", on_dark=False,
        canvas="#FFFFFF", ink_text="#0B0B0F", muted_text="#9aa0a6",
        rule="#cfd2d6", surface="#F7F7F4",
    ),
    "bone": ThemeColors(
        name="bone", on_dark=False,
        canvas="#F6F4EE", ink_text="#0B0B0F", muted_text="#9aa0a6",
        rule="#D8D4C8", surface="#FFFFFF",
    ),
}


def theme_colors(theme: str | None = None) -> ThemeColors:
    """Look up a theme palette by name. Unknown / None → 'paper' (default light)."""
    if theme and theme in THEMES:
        return THEMES[theme]
    return THEMES["paper"]


# ---------------------------------------------------------------------------
# apply_style — picks rcParams to match the requested theme
# ---------------------------------------------------------------------------

def apply_style(theme: str | None = None) -> None:
    """Apply Jin's matplotlib defaults for the chosen deck theme.

    `theme=None` (default) preserves prior behavior: black text on white,
    suitable for paper / docx figures and the "paper" pptx theme.

    `theme="slate"` (or any DARK theme name) flips text + spine + grid
    colors so the figure renders cleanly on a dark slide canvas. Brand
    accent colors are unchanged — they're designed to work on both.

    For FIGURES intended for a deck, pass the same theme name the deck uses
    (read from `<deck>.md.layout.json` `theme` field). Then also save with
    `fig.savefig(..., facecolor=theme_colors(theme).canvas)` so the figure
    background matches the slide canvas (no harsh white rectangle on dark).
    """
    T = theme_colors(theme)
    ink, muted, rule = T.ink_text, T.muted_text, T.rule

    mpl.rcParams.update({
        # fonts
        "font.family": FONT_BODY,
        # color discipline — themed
        "text.color": ink,
        "axes.labelcolor": ink,
        "axes.titlecolor": ink,
        "xtick.color": ink,
        "ytick.color": ink,
        "axes.edgecolor": rule,
        "axes.facecolor": T.canvas,
        "figure.facecolor": T.canvas,
        "savefig.facecolor": T.canvas,
        # title weight/size
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.labelsize": 11,
        # axes
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.prop_cycle": mpl.cycler(color=PALETTE_LINES),
        "axes.grid": True,
        "grid.color": rule,
        "grid.alpha": 0.30 if T.on_dark else 0.25,
        "grid.linewidth": 0.5,
        # legend / ticks
        "legend.frameon": False,
        "legend.fontsize": 9,
        "legend.labelcolor": ink,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        # output
        "figure.dpi": 110,
        "savefig.dpi": 200,
        "savefig.bbox": "tight",
    })


def title(ax, text: str, *, color: str | None = None, theme: str | None = None) -> None:
    """Geist Mono title. Color defaults to the active theme's ink_text.

    Pass `color=` to override, or `theme=` to look up a specific theme's
    ink even when apply_style was called with a different theme.
    """
    if color is None:
        color = theme_colors(theme).ink_text if theme else mpl.rcParams.get("text.color", "black")
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
    "ThemeColors", "THEMES", "theme_colors",
    "apply_style", "title", "palette",
]
