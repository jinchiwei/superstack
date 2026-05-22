"""conclusions layout — dark-navy closing slide with rotating brand-accent cards.

Sidecar entry shape:
{
  "kind": "conclusions",
  "params": {
    "title": "Takeaways",
    "lede": "...",
    "section_label": "Takeaways",
    "cards": [
      {"label": "Headline AUC", "body": "...", "icon": "FaChartLine"},
      {"label": "Survivors",    "body": "...", "icon": "FaCheckCircle"},
      {"label": "Caveat",       "body": "...", "icon": "FaExclamationTriangle"},
      {"label": "Honest ceiling","body": "...", "icon": "FaCrosshairs"}
    ],
    "callout": {"text": "Path forward: ...", "tone": "dark"}
  }
}

Geometry:
  - Dark navy background
  - Cards take 2/3 of body height; callout takes 1/3 with 0.20in gutter
  - If callout is omitted, cards take full body height
  - Card grid layout:
      n=2 → 1×2
      n=3 → 1×3
      n=4 → 2 rows × 2 cards  (preferred for visual balance)
      n=5 → 2 rows: 3 + 2
      n=6 → 2 rows × 3 cards
      n>6 → 2 rows, split as evenly as possible

Per-card accent rotation:
  Regardless of section accent, each card cycles through
  [TURQUOISE, DEEPPINK, AMBER, BLUEVIOLET] in order. The sidebar
  accent bar stays the section color — we don't override it.

Icon-homogeneity rule: closing-slide cards typically span distinct semantic
categories, so distinct icons are preserved. Homogeneous icon sets (all same
FA name) are dropped per the usual rule.
"""

from __future__ import annotations

import math

import branding
from pptx.dml.color import RGBColor

from palette import LIGHT

from ._common import (
    _add_chrome,
    _set_bg,
    DARK_BG_RGB,
    WHITE_RGB,
    TURQUOISE_RGB,
    DEEPPINK_RGB,
    AMBER_RGB,
    BLUEVIOLET_RGB,
    _rgb,
)
from .blocks.card_row import render as _card_row
from .blocks.accent_callout import render as _accent_callout

# Brand-rotating accent cycle for card-level accents
_ACCENT_CYCLE = [
    branding.TURQUOISE,
    branding.DEEPPINK,
    branding.AMBER,
    branding.BLUEVIOLET,
]


def _grid_split(n: int) -> list[int]:
    """Return the row sizes for n cards.

    n=2 → [2]
    n=3 → [3]
    n=4 → [2, 2]
    n=5 → [3, 2]
    n=6 → [3, 3]
    n>6 → two rows split as evenly as possible
    """
    if n <= 3:
        return [n]
    if n == 4:
        return [2, 2]
    if n == 5:
        return [3, 2]
    if n == 6:
        return [3, 3]
    # n > 6: two rows, top gets ceiling
    top = math.ceil(n / 2)
    return [top, n - top]


def render(slide, *, params: dict, accent_rgb: RGBColor, footer_kwargs: dict, palette=LIGHT) -> None:
    """Render a conclusions/takeaways closing slide.

    params keys:
        title        str
        lede         str
        section_label str
        cards        list[{"label": str, "body": str, "icon": str | null}]
        callout      {"text": str, "tone": "dark"|"accent"}  (optional)
    """
    title = params.get("title", "")
    lede = params.get("lede", "")
    cards = list(params.get("cards") or [])
    callout = params.get("callout") or {}

    title_present = bool(title)
    title_wraps = len(title) > 30 if title_present else False

    # Dark background: theme canvas on dark themes (matches the deck), else navy.
    _set_bg(slide, palette.canvas_rgb if palette.on_dark else DARK_BG_RGB)

    body_top, body_h, body_l, body_w, body_bottom = _add_chrome(
        slide,
        title=title,
        lede=lede,
        footer_kwargs=footer_kwargs,
        accent=accent_rgb,       # sidebar stays section color
        title_present=title_present,
        title_wraps=title_wraps,
        use_side_by_side=False,
        dark_bg=True,            # flip title white, lede/footer to light dim grey
    )

    if not cards:
        return

    # ── Apply icon-homogeneity rule ──────────────────────────────────────────
    all_icons = [str(c.get("icon") or "") for c in cards]
    non_empty_icons = [ic for ic in all_icons if ic]
    homogeneous_icons = (
        len(non_empty_icons) > 0
        and len(set(non_empty_icons)) == 1
    )
    if homogeneous_icons:
        cards = [{**c, "icon": None} for c in cards]

    # ── Assign rotating per-card accent_hex ─────────────────────────────────
    # The card-row block reads card["accent_hex"] for per-card accent overrides.
    # We stamp them here so the brand rotation is deterministic regardless of
    # which section accent the planner happened to pick.
    cards_with_accents = []
    for i, card in enumerate(cards):
        card_with_accent = dict(card)
        card_with_accent["accent_hex"] = _ACCENT_CYCLE[i % len(_ACCENT_CYCLE)]
        cards_with_accents.append(card_with_accent)
    cards = cards_with_accents

    # ── Vertical allocation ──────────────────────────────────────────────────
    gutter = 0.20
    if callout:
        callout_h = max(0.60, body_h / 3)
        cards_h = max(0.50, body_h - callout_h - gutter)
    else:
        callout_h = 0.0
        cards_h = body_h

    # ── Card grid ────────────────────────────────────────────────────────────
    row_sizes = _grid_split(len(cards))
    n_rows = len(row_sizes)
    row_gutter = gutter if n_rows > 1 else 0.0
    row_h = max(0.40, (cards_h - row_gutter * (n_rows - 1)) / n_rows)

    card_idx = 0
    for row_i, row_size in enumerate(row_sizes):
        row_top = body_top + row_i * (row_h + row_gutter)
        row_cards = cards[card_idx: card_idx + row_size]
        card_idx += row_size

        # Pass dark_bg so cards get #1A2D50 fill and white body text
        _card_row(
            slide,
            left=body_l, top=row_top,
            width=body_w, height=row_h,
            params={"cards": row_cards, "dark_bg": True},
            accent_rgb=accent_rgb,  # row-level accent is section color; per-card overrides win
        )

    # ── Accent callout ───────────────────────────────────────────────────────
    if callout:
        callout_top = body_top + cards_h + gutter
        _accent_callout(
            slide,
            left=body_l, top=callout_top,
            width=body_w, height=callout_h,
            params=callout,
            accent_rgb=accent_rgb,
        )
