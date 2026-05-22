"""cards-with-takeaway layout — N cards in a row + dark accent-callout footer.

Sidecar entry shape:
{
  "kind": "cards-with-takeaway",
  "params": {
    "title": "...",
    "lede": "...",
    "section_label": "...",
    "cards": [{"label": "...", "body": "...", "icon": null}, ...],
    "callout": {"text": "...", "tone": "dark"}
  }
}

Geometry:
  - Cards row: 2/3 of body height
  - Accent callout: 1/3 of body height
  - Gutter between: 0.20in

Icon-homogeneity rule: if all cards in the row share the same icon name
(or all have the same non-null FA icon), drop icons — homogeneous rows
look better without them. Cards with genuinely distinct icons (different
FA names) keep them.
"""

from __future__ import annotations

import branding
from pptx.dml.color import RGBColor

from palette import LIGHT

from ._common import (
    _add_chrome,
    _set_bg,
)
from .blocks.card_row import render as _card_row
from .blocks.accent_callout import render as _accent_callout


def render(slide, *, params: dict, accent_rgb: RGBColor, footer_kwargs: dict, palette=LIGHT) -> None:
    """Render a cards-with-takeaway slide.

    params keys:
        title       str
        lede        str
        section_label str
        cards       list[{"label": str, "body": str, "icon": str | null}]
        callout     {"text": str, "tone": "dark"|"accent"}
    """
    title = params.get("title", "")
    lede = params.get("lede", "")
    cards = list(params.get("cards") or [])
    callout = params.get("callout") or {}

    title_present = bool(title)
    title_wraps = len(title) > 30 if title_present else False

    _set_bg(slide, palette.canvas_rgb)

    body_top, body_h, body_l, body_w, body_bottom = _add_chrome(
        slide,
        title=title,
        lede=lede,
        footer_kwargs=footer_kwargs,
        accent=accent_rgb,
        title_present=title_present,
        title_wraps=title_wraps,
        use_side_by_side=False,
        on_dark=palette.on_dark,
    )

    gutter = 0.20
    callout_h = max(0.60, body_h / 3)
    cards_h = max(0.50, body_h - callout_h - gutter)

    # ── Apply icon-homogeneity rule ──────────────────────────────────────────
    # If all cards share the same icon name, drop icons to avoid arbitrary
    # variation. Distinct icons (different FA names) are preserved.
    all_icons = [str(c.get("icon") or "") for c in cards]
    non_empty_icons = [ic for ic in all_icons if ic]
    homogeneous_icons = (
        len(non_empty_icons) > 0
        and len(set(non_empty_icons)) == 1  # all same icon
    )
    if homogeneous_icons:
        cards = [{**c, "icon": None} for c in cards]

    # Theme block-helper colors only on dark palettes. Under a light/strict
    # palette, pass None so the block helpers fall back to their exact
    # original (possibly distinct) constants — preserving byte parity.
    _surf = palette.surface_rgb if palette.on_dark else None
    _text = palette.text_rgb if palette.on_dark else None

    # ── Cards row ────────────────────────────────────────────────────────────
    if cards:
        _card_row(
            slide,
            left=body_l, top=body_top,
            width=body_w, height=cards_h,
            params={"cards": cards},
            accent_rgb=accent_rgb,
            surface_rgb=_surf,
            text_rgb=_text,
        )

    # ── Accent callout ───────────────────────────────────────────────────────
    callout_top = body_top + cards_h + gutter
    _accent_callout(
        slide,
        left=body_l, top=callout_top,
        width=body_w, height=callout_h,
        params=callout,
        accent_rgb=accent_rgb,
    )
