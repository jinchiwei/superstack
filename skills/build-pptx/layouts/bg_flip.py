"""bg-flip layout: dark navy background, white title text — "take-away" slide."""

from __future__ import annotations

import branding
from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt

from palette import LIGHT

from ._common import (
    _add_rect,
    _add_text,
    _estimate_paragraph_height,
    _render_paragraph_block,
    _rgb,
    _set_bg,
    DARK_BG_RGB,
    DEEPPINK_RGB,
    AMBER_RGB,
    BLUEVIOLET_RGB,
    MUTED_RGB,
    RULE_RGB,
    WHITE_RGB,
)

# Off-white for the lede on dark background
_LEDE_RGB = _rgb("#C8C8D2")
# Slightly lighter muted for footer visibility on dark bg
_FOOTER_RGB = _rgb("#888888")


def render(slide, *, params: dict, accent_rgb: RGBColor, footer_kwargs: dict, palette=LIGHT) -> None:
    """Render a dark-background (bg-flip) content slide.

    params keys — same shape as content-text:
        title   (str)
        lede    (str)
        body    list[{"kind", "html"}]

    NOTE: Does NOT call _add_chrome (which assumes white bg). Chrome is drawn
    manually here with white/light-colored text on the dark navy background.
    """
    title = params.get("title", "")
    lede = params.get("lede", "")
    body = list(params.get("body") or [])

    title_present = bool(title)
    title_wraps = len(title) > 30 if title_present else False

    # ── Background ──────────────────────────────────────────────────────────────
    # Theme canvas on dark themes (matches the deck), else navy.
    _set_bg(slide, palette.canvas_rgb if palette.on_dark else DARK_BG_RGB)

    # ── Left accent bar ─────────────────────────────────────────────────────────
    _add_rect(slide, left=0, top=0, width=0.22, height=7.5, fill_rgb=accent_rgb)

    # ── Title ───────────────────────────────────────────────────────────────────
    title_h = 1.05 if title_wraps else 0.55
    hairline_top = 0.30 + title_h + 0.10
    subtitle_top = hairline_top + 0.10

    if title_present:
        _add_text(slide, title, left=0.50, top=0.30, width=12.30, height=title_h,
                  size=28, color_rgb=WHITE_RGB, font=branding.MONO_FONT, bold=True)
        # Hairline in accent colour (not the default RULE_RGB)
        _add_rect(slide, left=0.50, top=hairline_top, width=12.30, height=0.005,
                  fill_rgb=accent_rgb)

    # ── Lede ────────────────────────────────────────────────────────────────────
    if lede:
        est_h = _estimate_paragraph_height(lede, width=12.30, size=13,
                                           line_spacing=1.30)
        lede_h = min(1.0, max(0.40, est_h))
        _add_text(slide, lede, left=0.50, top=subtitle_top, width=12.30,
                  height=lede_h,
                  size=13, color_rgb=_LEDE_RGB, font=branding.SANS_FONT)
    else:
        lede_h = 0.40

    # ── Body geometry ───────────────────────────────────────────────────────────
    if title_present:
        body_top = subtitle_top + lede_h + 0.10
    else:
        body_top = 0.40

    body_bottom = 6.85
    body_h = body_bottom - body_top
    body_l = 0.50
    body_w = 12.30

    # ── Body content ────────────────────────────────────────────────────────────
    # Bullet markers rotate through the non-turquoise priority colours so
    # each takeaway point gets a distinct accent (Bug 4 fix).
    # The slide's main accent (left bar / hairline / heading) stays as
    # accent_rgb (typically turquoise for takeaway slides).
    _BULLET_CYCLE = [DEEPPINK_RGB, AMBER_RGB, BLUEVIOLET_RGB]
    if body:
        _render_paragraph_block(
            slide,
            items=body,
            left=body_l, top=body_top,
            width=body_w, height=body_h,
            accent_rgb=accent_rgb,
            size=14,
            distribute=True,
            text_color=WHITE_RGB,
            accent_cycle=_BULLET_CYCLE,
        )

    # ── Footer ──────────────────────────────────────────────────────────────────
    name = footer_kwargs.get("name", "")
    org = footer_kwargs.get("org", "")
    deck_title = footer_kwargs.get("deck_title", "")
    date = footer_kwargs.get("date", "")
    footer_parts = [p for p in (name, org, deck_title, date) if p]
    if footer_parts:
        _add_text(slide, "  ·  ".join(footer_parts),
                  left=0.50, top=7.12, width=12.30, height=0.30,
                  size=9, color_rgb=_FOOTER_RGB, font=branding.MONO_FONT)
