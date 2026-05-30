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


def text_on_brand_fill(fill_hex: str) -> str:
    """Pick the high-contrast text color (black or white) for text placed on
    top of a brand-4 fill — mirrors the slide-side `layouts._common._text_on`
    so figures get the same answer.

    Per Jinchi's brand spec (validated against WCAG luminance):
      * TURQUOISE (#40E0D0) → black  (L≈0.64 → ink ratio 12.1, white 1.5)
      * AMBER     (#F0C840) → black  (L≈0.62 → ink ratio 11.7, white 1.5)
      * DEEPPINK  (#FF1493) → white  (brand pref; ink 5.2, white 3.5 — knife's edge)
      * BLUEVIOLET(#8A2BE2) → white  (L≈0.09 → white ratio 7.6, ink 1.8)

    Any other fill falls back to WCAG luminance — whichever of black/white has
    the higher contrast against the fill.

    Use this anywhere a matplotlib figure puts text on top of a colored patch
    (FancyBboxPatch, Rectangle, bar fill, …) instead of hardcoding "white" or
    "black" — keeps figures consistent with slide composition and prevents the
    "white text on turquoise" class of bug.
    """
    h = fill_hex.upper().lstrip("#")
    # Explicit brand overrides
    if h in ("40E0D0", "F0C840"):   # turquoise, amber
        return "black"
    if h in ("FF1493", "8A2BE2"):   # deeppink, blueviolet
        return "white"
    # Generic WCAG-based pick for non-brand fills
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    def _lin(c: int) -> float:
        s = c / 255.0
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4
    lum = 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)
    return "black" if lum > 0.5 else "white"


def check_text_overflow(fig, *, tolerance_in: float = 0.02) -> list[dict]:
    """Walk all text artists in `fig` and flag any whose rendered bbox
    extends past its containing Axes' data-limit box.

    Catches the "text wider than its FancyBboxPatch" / "label runs off the
    plot edge" class of bug that slide-level contrast checks can't see (the
    matplotlib figure is a flat raster image to python-pptx). Returns a list
    of warning dicts: {axes, text, text_bbox, axes_bbox, side, overflow_in}.

    Call AFTER fig.savefig (which forces a draw + computes real text extents).
    Tolerance in inches for sub-pixel slop.
    """
    import matplotlib.pyplot as plt
    fig.canvas.draw()  # ensure renderer + bboxes are real
    renderer = fig.canvas.get_renderer()
    fig_w_in, fig_h_in = fig.get_size_inches()
    warnings: list[dict] = []
    for ax in fig.axes:
        # Axes bbox in display units → inches
        ax_bbox_disp = ax.get_window_extent(renderer)
        for text in ax.texts:
            try:
                tb = text.get_window_extent(renderer)
            except Exception:
                continue
            if tb.width <= 0 or tb.height <= 0:
                continue
            # Convert overflow from display units to inches
            dpi = fig.dpi
            ax_l, ax_r = ax_bbox_disp.x0, ax_bbox_disp.x1
            ax_b, ax_t = ax_bbox_disp.y0, ax_bbox_disp.y1
            sides = {}
            if tb.x0 < ax_l - tolerance_in * dpi:
                sides["left"] = (ax_l - tb.x0) / dpi
            if tb.x1 > ax_r + tolerance_in * dpi:
                sides["right"] = (tb.x1 - ax_r) / dpi
            if tb.y0 < ax_b - tolerance_in * dpi:
                sides["bottom"] = (ax_b - tb.y0) / dpi
            if tb.y1 > ax_t + tolerance_in * dpi:
                sides["top"] = (tb.y1 - ax_t) / dpi
            if sides:
                warnings.append({
                    "text": text.get_text()[:60],
                    "ax": ax,
                    "sides": sides,
                })
    return warnings


def warn_text_overflow(fig, *, source: str = "") -> None:
    """Convenience wrapper: run check_text_overflow and print warnings to stderr.

    Call from a figure script right after savefig so a build log shows every
    overflowing text artist by name. No-op when nothing overflows.
    """
    import sys
    issues = check_text_overflow(fig)
    if not issues:
        return
    prefix = f"[{source}] " if source else ""
    print(f"{prefix}text overflow: {len(issues)} text artist(s) extend past their axes",
          file=sys.stderr)
    for w in issues:
        sides = ", ".join(f"{k} {v:.2f}in" for k, v in w["sides"].items())
        print(f'  "{w["text"]}" overflows: {sides}', file=sys.stderr)


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
    "text_on_brand_fill", "check_text_overflow", "warn_text_overflow",
]
