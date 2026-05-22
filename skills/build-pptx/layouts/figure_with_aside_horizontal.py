"""figure-with-aside-horizontal layout — figure on top (full-width),
commentary card on the bottom (full-width), accent stripe on top.

Use for WIDE / panel-composite figures where forcing the figure into a
2/3-width side-by-side layout (figure-with-aside) would crush it. Here the
figure gets the full body width and the commentary card sits below it as a
short caption-strip.

Sidecar entry shape:
{
  "kind": "figure-with-aside-horizontal",
  "params": {
    "title": "...",
    "lede": "...",
    "section_label": "...",
    "image": "path/to/fig.png",
    "alt": "...",
    "aside": {"label": "Why X wins", "body": "...", "icon": null}
  }
}

Geometry:
  - Figure (top, weight 2): full body width
  - Aside card (bottom, weight 1): full body width, with TOP accent stripe
  - Gutter: 0.20in
"""

from __future__ import annotations

import branding
from pptx.dml.color import RGBColor

from palette import LIGHT

from ._common import (
    _add_chrome,
    _add_rect,
    _add_text,
    _set_bg,
    WHITE_RGB,
    PAPER_RGB,
    INK_RGB,
    MUTED_RGB,
)
from .blocks.figure import render as _figure


_ASIDE_STRIPE_H  = 0.07
_ASIDE_PAD_LEFT  = 0.20
_ASIDE_LABEL_SZ  = 14
_ASIDE_BODY_SZ   = 12


def _aside_top_accent_card(
    slide, *,
    left: float, top: float, width: float, height: float,
    params: dict, accent_rgb: RGBColor,
) -> None:
    """Render a card with a TOP accent stripe (vs the side-rail variant).

    params: {"label": str, "body": str, "icon": str|None}
    """
    label = (params.get("label") or "").strip()
    body  = (params.get("body") or "").strip()

    # Card background
    _add_rect(slide, left=left, top=top, width=width, height=height,
              fill_rgb=PAPER_RGB)

    # Top accent stripe — full-width, signals horizontal flow
    _add_rect(slide, left=left, top=top,
              width=width, height=_ASIDE_STRIPE_H, fill_rgb=accent_rgb)

    label_top = top + _ASIDE_STRIPE_H + 0.14
    body_top  = label_top + (0.40 if label else 0.0)

    if label:
        _add_text(
            slide, label,
            left=left + _ASIDE_PAD_LEFT, top=label_top,
            width=width - 2 * _ASIDE_PAD_LEFT, height=0.40,
            size=_ASIDE_LABEL_SZ, color_rgb=accent_rgb,
            font=branding.MONO_FONT, bold=True,
        )

    if body:
        _add_text(
            slide, body,
            left=left + _ASIDE_PAD_LEFT, top=body_top,
            width=width - 2 * _ASIDE_PAD_LEFT,
            height=top + height - body_top - 0.10,
            size=_ASIDE_BODY_SZ, color_rgb=INK_RGB,
            font=branding.SANS_FONT,
        )


def render(slide, *, params: dict, accent_rgb: RGBColor, footer_kwargs: dict, palette=LIGHT) -> None:
    """Render a figure-with-aside-horizontal slide.

    params keys:
        title         str
        lede          str
        section_label str
        image         str
        alt           str
        aside         {"label": str, "body": str, "icon": str | null}
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

    # ── Vertical split — adaptive to aside content length ──────────────────
    # Short captions (≤ ~150 chars, no multi-bullet body, no label) only need
    # a thin caption strip; let the figure absorb the rest. Long / multi-line
    # asides cap at the original 1/3 split so they don't overpower the figure.
    gutter = 0.20
    available_h = body_h - gutter

    aside_label_text = (aside.get("label") or "").strip()
    aside_body_text  = (aside.get("body")  or "").strip()

    # Estimate natural aside height: stripe + top-pad + label + body lines + bottom-pad.
    # body width determines wrap; ~110 chars/line at 12pt Geist on a ~12" body.
    import math
    chars_per_line = max(60, int(body_w * 9))   # ~9 chars per inch at 12pt
    n_body_lines   = max(1, math.ceil(len(aside_body_text) / chars_per_line)) if aside_body_text else 0
    label_block_h  = 0.40 if aside_label_text else 0.0
    body_block_h   = n_body_lines * 0.24        # ~0.24 in per line at 12pt
    pad_top        = _ASIDE_STRIPE_H + 0.14
    pad_bottom     = 0.20
    natural_aside_h = pad_top + label_block_h + body_block_h + pad_bottom

    min_aside_h = 0.55                          # floor: thin caption strip
    max_aside_h = available_h * (1 / 3)         # ceiling: original 2:1 split
    aside_h = max(min_aside_h, min(natural_aside_h, max_aside_h))
    fig_h   = available_h - aside_h

    # ── Figure (top, full width) ────────────────────────────────────────────
    _figure(
        slide,
        left=body_l, top=body_top,
        width=body_w, height=fig_h,
        params={"image_path": image, "alt": alt},
        accent_rgb=accent_rgb,
    )

    # ── Aside card with TOP accent (bottom, full width) ─────────────────────
    aside_top = body_top + fig_h + gutter
    _aside_top_accent_card(
        slide,
        left=body_l, top=aside_top,
        width=body_w, height=aside_h,
        params=aside,
        accent_rgb=accent_rgb,
    )
