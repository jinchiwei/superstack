"""cards-triple layout: 3 (or 2-4) flat full-width stacked cards, no hierarchy.

Use for parallel concepts where each card is equal weight — e.g. 3 study
aims, 3 questions, 3 takeaways. Renders as full-width horizontal stripes
that fill the slide cleanly with sparse text.

Sidecar entry shape:
{
  "kind": "cards-triple",
  "params": {
    "title": "Motivation",
    "lede": "...",
    "section_label": "Background",
    "cards": [
      {"label": "Severity",         "body": "...", "icon": null},
      {"label": "APOE4 modulation", "body": "...", "icon": null},
      {"label": "Replication",      "body": "...", "icon": null}
    ]
  }
}

Geometry:
  - Each card: full-width PAPER-fill row
  - Top accent stripe (1.0in wide partial — flush left, mono-weight)
  - All cards visually equal: same stripe size, same label/body sizes
  - Vertically distributed (or centered if total_h < body_h)
  - Supports n=2 (sparse), n=3 (default), n=4 (cap)
"""

from __future__ import annotations

from pathlib import Path

import branding
from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt

from palette import LIGHT

from ._common import (
    _add_card,
    _add_chrome,
    _add_rect,
    _add_text,
    _estimate_paragraph_height,
    _set_bg,
)


_STRIPE_H        = 0.06       # uniform top accent stripe (in)
_STRIPE_W        = 1.0        # partial-width stripe (in)
_LABEL_SIZE      = 14
_BODY_SIZE       = 12
_LABEL_H_ALLOC   = 0.40
_LABEL_TOP_OFF   = _STRIPE_H + 0.14
_BODY_TOP_OFF    = _STRIPE_H + 0.14 + _LABEL_H_ALLOC
_PAD_LEFT        = 0.18
_PAD_BOT         = 0.20


def render(slide, *, params: dict, accent_rgb: RGBColor, footer_kwargs: dict, palette=LIGHT) -> None:
    """Render N flat stacked cards (no hierarchy).

    params keys:
        title         str
        lede          str
        section_label str
        cards         list[{"label": str, "body": str, "icon": Path|None}] — 2-4 items
    """
    title = params.get("title", "")
    lede = params.get("lede", "")
    cards = list(params.get("cards") or [])

    if not cards:
        return
    cards = cards[:4]   # cap at 4 to keep cards readable

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
        palette=palette,
    )

    n = len(cards)

    # ── Estimate each card's natural height ──
    heights = []
    for card in cards:
        body_text = card.get("body", "") or ""
        body_est = _estimate_paragraph_height(
            body_text, width=body_w - 2 * _PAD_LEFT,
            size=_BODY_SIZE, line_spacing=1.35,
        )
        h = _BODY_TOP_OFF + max(body_est, 0.30) + _PAD_BOT
        h = max(0.95, h)
        heights.append(h)

    gutter = 0.20
    total_h = sum(heights) + gutter * (n - 1)

    # Vertically center the stack if it fits; otherwise scale down.
    if total_h < body_h:
        cur_top = body_top + (body_h - total_h) / 2.0
    else:
        # Compress proportionally to fit body_h.
        scale = (body_h - gutter * (n - 1)) / max(sum(heights), 0.01)
        heights = [max(0.85, h * scale) for h in heights]
        cur_top = body_top

    # ── Render each card ──
    for idx, card in enumerate(cards):
        c_label = card.get("label", "")
        c_body  = card.get("body", "")
        c_icon  = card.get("icon")
        c_h     = heights[idx]

        # Card background
        _add_rect(slide, left=body_l, top=cur_top,
                  width=body_w, height=c_h, fill_rgb=palette.surface_rgb)

        # Top-left partial stripe (mono-weight — no primary differentiation)
        _add_rect(slide, left=body_l, top=cur_top,
                  width=_STRIPE_W, height=_STRIPE_H, fill_rgb=accent_rgb)

        # Optional icon
        label_l = body_l + _PAD_LEFT
        label_w = body_w - 2 * _PAD_LEFT
        if c_icon is not None:
            c_icon = Path(c_icon) if not isinstance(c_icon, Path) else c_icon
            if c_icon.exists():
                try:
                    slide.shapes.add_picture(
                        str(c_icon),
                        Inches(body_l + _PAD_LEFT), Inches(cur_top + _LABEL_TOP_OFF),
                        width=Inches(0.32), height=Inches(0.32),
                    )
                    label_l = body_l + 0.58
                    label_w = body_w - 0.76
                except Exception:
                    pass

        # Skip the label box entirely when there's no label — body floats up
        # to occupy the freed height. Keeps body-only cards from showing a
        # phantom empty header above the text.
        if c_label:
            _add_text(slide, c_label,
                      left=label_l, top=cur_top + _LABEL_TOP_OFF,
                      width=label_w, height=_LABEL_H_ALLOC,
                      size=_LABEL_SIZE, color_rgb=accent_rgb,
                      font=branding.MONO_FONT, bold=True)
            body_top_off = _BODY_TOP_OFF
        else:
            body_top_off = _LABEL_TOP_OFF  # body starts where label would have
        _add_text(slide, c_body,
                  left=body_l + _PAD_LEFT, top=cur_top + body_top_off,
                  width=body_w - 2 * _PAD_LEFT,
                  height=c_h - body_top_off - _PAD_BOT,
                  size=_BODY_SIZE, color_rgb=palette.text_rgb,
                  font=branding.SANS_FONT)

        cur_top = cur_top + c_h + gutter
