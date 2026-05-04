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
DARK_BG = "#0E1A35"


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
# CJK chars are dispatched via a virtual 'CJK' family that build-pdf's CSS
# defines with @font-face + unicode-range (mapping U+4E00-9FFF and related
# blocks to PingFang TC → Heiti TC → fallbacks).  This is needed because
# WeasyPrint's plain font-family fallback is unreliable for CJK — it tends
# to stay on the first font even when glyphs are missing.  Putting 'CJK'
# in the chain BEFORE sans-serif/monospace lets unicode-range fire and
# pick the right CJK font, while keeping Latin chars on Geist/Geist Mono.
SANS_FONT_STACK = (
    "'Geist', 'Helvetica', 'Liberation Sans', "
    "-apple-system, system-ui, "
    "'CJK', "
    "'PingFang TC', 'Heiti TC', 'PingFang SC', "
    "'Hiragino Sans GB', 'Hiragino Kaku Gothic ProN', "
    "'Noto Sans CJK TC', 'Noto Sans CJK SC', "
    "'Microsoft JhengHei', 'Microsoft YaHei', "
    "sans-serif"
)
MONO_FONT_STACK = (
    "'Geist Mono', 'SF Mono', 'Menlo', 'Liberation Mono', 'Consolas', "
    "'CJK', "
    "'PingFang TC', 'Heiti TC', 'PingFang SC', "
    "'Hiragino Sans GB', 'Hiragino Kaku Gothic ProN', "
    "'Noto Sans CJK TC', 'Noto Sans CJK SC', "
    "'Microsoft JhengHei', 'Microsoft YaHei', "
    "monospace"
)


# === Plain font names (for python-pptx, python-docx -- they want a single name not a chain) ===
SANS_FONT = "Geist"
MONO_FONT = "Geist Mono"


# === Section→color auto-inference ===
# Order matters: more-specific categories come first so e.g. "Methodology
# overview" classifies as DEEPPINK (methodology) rather than TURQUOISE
# (overview). The TURQUOISE list is intentionally last because its keywords
# (overview, context, intro, future) are generic enough to appear in headers
# of every other category.
_SECTION_KEYWORDS = (
    (("method", "methodology", "approach", "design", "framework", "cohort",
      "pipeline", "architecture", "model"), DEEPPINK),
    (("result", "finding", "performance", "outcome", "metric", "headline"), AMBER),
    (("validation", "limitation", "caveat", "robust", "external", "sensitivity",
      "discussion", "replication", "ablation"), BLUEVIOLET),
    (("background", "motivation", "introduction", "intro", "context", "conclusion",
      "next", "future", "overview", "direction"), TURQUOISE),
)


# === Accent → category name for section divider eyebrows ===
# The eyebrow is a thematic label that pairs with the H1 (used as the big
# title); without this, a section divider repeats its H1 as both eyebrow
# and title which feels redundant.
_ACCENT_CATEGORY = {
    TURQUOISE.upper():  "Overview",
    DEEPPINK.upper():   "Methodology",
    AMBER.upper():      "Results",
    BLUEVIOLET.upper(): "Validation",
}


def category_for_accent(accent_hex: str) -> str:
    """Display name for the section divider's eyebrow, given accent color.
    Returns the category label so the eyebrow is a thematic anchor
    (Overview / Methodology / Results / Validation) rather than a duplicate
    of the slide's H1."""
    return _ACCENT_CATEGORY.get(accent_hex.upper(), "Overview")


def match_section_color(name: str) -> str:
    """Infer the section's accent color from its name via keyword matching.

    Returns one of TURQUOISE / DEEPPINK / AMBER / BLUEVIOLET. Falls back to
    TURQUOISE if no keyword matches.
    """
    if not name:
        return TURQUOISE
    needle = name.lower()
    for keywords, color in _SECTION_KEYWORDS:
        for kw in keywords:
            if kw in needle:
                return color
    return TURQUOISE
