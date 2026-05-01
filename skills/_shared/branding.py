"""Single source of truth for Jin's brand palette and font stacks.

All build-* skills import constants from this module. If you change a color
or font here, every skill picks it up on the next render.
"""

from __future__ import annotations


# === Canonical priority colors ===
TURQUOISE  = "#40E0D0"
DEEPPINK   = "#FF1493"
AMBER      = "#F0C840"
BLUEVIOLET = "#8A2BE2"


# === Neutrals ===
INK    = "#14141C"   # body text — off-black with slight cool tint
WHITE  = "#FFFFFF"
PAPER  = "#FAFAFC"   # near-white code-block fill, slight cool tint
MUTED  = "#555560"   # dim gray for eyebrows, dates, labels on light backgrounds
DIM    = "#888888"   # page numbers, very low-emphasis text
RULE   = "#DDDDDD"   # hairline rule color


# === Dark slide background (PPTX title + closing) ===
DARK_BG = "#14141C"


# === Semantic role aliases ===
# These are the names used in renderers. If we ever swap which canonical
# color plays which role, change here, no other code changes needed.
HEADING_1     = TURQUOISE
HEADING_2     = DEEPPINK
HEADING_3     = INK
NAME_COLOR    = TURQUOISE
ORG_COLOR     = DEEPPINK
METRIC_COLOR  = BLUEVIOLET
EYEBROW_LIGHT = MUTED
EYEBROW_DARK  = TURQUOISE


# === Section divider cycle (PPTX) ===
SECTION_DIVIDER_CYCLE = [TURQUOISE, DEEPPINK, AMBER, BLUEVIOLET]


def pick_section_color(index: int) -> str:
    """Return the section divider color for the Nth section, cycling."""
    return SECTION_DIVIDER_CYCLE[index % len(SECTION_DIVIDER_CYCLE)]


def section_text_color(bg_color: str) -> str:
    """Return text color (white or off-black) for legibility on a section-divider background."""
    # Amber is too light for white text -- use off-black. Everything else uses white.
    if bg_color == AMBER:
        return INK
    return WHITE


# === Font stacks (CSS family strings) ===
SANS_FONT_STACK = (
    "'Geist', 'Helvetica', 'Liberation Sans', "
    "-apple-system, system-ui, "
    "'Hiragino Kaku Gothic ProN', 'Noto Sans CJK JP', 'Microsoft YaHei', "
    "sans-serif"
)
MONO_FONT_STACK = (
    "'Geist Mono', 'SF Mono', 'Menlo', 'Liberation Mono', 'Consolas', monospace"
)


# === Plain font names (for python-pptx, python-docx -- they want a single name not a chain) ===
SANS_FONT = "Geist"
MONO_FONT = "Geist Mono"
