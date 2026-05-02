"""figure-with-aside layout — figure on the left (weight 2), commentary card on the right (weight 1).

Sidecar entry shape:
{
  "kind": "figure-with-aside",
  "params": {
    "title": "...",
    "lede": "...",
    "section_label": "...",
    "image": "path/to/fig.png",
    "alt": "...",
    "aside": {"label": "Why X wins", "body": "...", "icon": "FaLightbulb"}
  }
}

Geometry:
  - 1 row, 2 blocks: figure (weight 2) + left-accent-card (weight 1)
  - Gutter: 0.20in
"""

from __future__ import annotations

import branding
from pptx.dml.color import RGBColor

from ._common import (
    _add_chrome,
    _set_bg,
    WHITE_RGB,
)
from .blocks.figure import render as _figure
from .blocks.left_accent_card import render as _left_accent_card


def render(slide, *, params: dict, accent_rgb: RGBColor, footer_kwargs: dict) -> None:
    """Render a figure-with-aside slide.

    params keys:
        title       str
        lede        str
        section_label str
        image       str — path to figure image
        alt         str — alt text / fallback
        aside       {"label": str, "body": str, "icon": str | null}
    """
    title = params.get("title", "")
    lede = params.get("lede", "")
    image = params.get("image", "")
    alt = params.get("alt", "")
    aside = params.get("aside") or {}

    title_present = bool(title)
    title_wraps = len(title) > 30 if title_present else False

    _set_bg(slide, WHITE_RGB)

    body_top, body_h, body_l, body_w, body_bottom = _add_chrome(
        slide,
        title=title,
        lede=lede,
        footer_kwargs=footer_kwargs,
        accent=accent_rgb,
        title_present=title_present,
        title_wraps=title_wraps,
        use_side_by_side=False,
    )

    # ── Weight-based 2:1 split ───────────────────────────────────────────────
    gutter = 0.20
    total_weight = 3  # figure=2, aside=1
    available_w = body_w - gutter
    fig_w = available_w * (2 / total_weight)
    aside_w = available_w * (1 / total_weight)

    # ── Figure (left) ────────────────────────────────────────────────────────
    _figure(
        slide,
        left=body_l, top=body_top,
        width=fig_w, height=body_h,
        params={"image_path": image, "alt": alt},
        accent_rgb=accent_rgb,
    )

    # ── Left-accent card (right) ──────────────────────────────────────────────
    aside_left = body_l + fig_w + gutter
    _left_accent_card(
        slide,
        left=aside_left, top=body_top,
        width=aside_w, height=body_h,
        params=aside,
        accent_rgb=accent_rgb,
    )
