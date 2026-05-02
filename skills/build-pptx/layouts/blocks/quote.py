"""quote block — italic block quote with optional attribution.

params:
    text            str — the quote body
    attribution     str — optional attribution (e.g. "Dr. Smith")
"""
from __future__ import annotations

from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

from ._base import (
    _add_text, _add_rect,
    INK_RGB, MUTED_RGB, RULE_RGB,
    branding,
)


def render(slide, *, left: float, top: float, width: float, height: float,
           params: dict, accent_rgb: RGBColor) -> None:
    text = str(params.get("text", ""))
    attribution = str(params.get("attribution", ""))

    attr_h = 0.28 if attribution else 0.0
    attr_gap = 0.10 if attribution else 0.0
    quote_h = max(0.30, height - attr_h - attr_gap)

    # Left quote bar (thin accent stripe)
    _add_rect(slide, left=left, top=top, width=0.05, height=height,
              fill_rgb=accent_rgb)

    quote_left = left + 0.18

    if text:
        _add_text(
            slide,
            f"“{text}”",
            left=quote_left, top=top,
            width=width - 0.20, height=quote_h,
            size=16, color_rgb=INK_RGB,
            font=branding.SANS_FONT, italic=True,
        )

    if attribution:
        _add_text(
            slide,
            f"— {attribution}",
            left=quote_left, top=top + quote_h + attr_gap,
            width=width - 0.22, height=attr_h,
            size=12, color_rgb=MUTED_RGB,
            font=branding.MONO_FONT, align=PP_ALIGN.RIGHT,
        )
