"""accent-callout block — full-width emphasized takeaway bar.

params:
    text    str     — callout text
    tone    str     — "dark" (DARK_BG fill, white italic) or
                      "accent" (accent_rgb fill, INK text)
"""
from __future__ import annotations

from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

from ._base import (
    _add_rect, _add_text,
    DARK_BG_RGB, WHITE_RGB, INK_RGB,
    branding,
)


def render(slide, *, left: float, top: float, width: float, height: float,
           params: dict, accent_rgb: RGBColor) -> None:
    text = str(params.get("text", ""))
    tone = params.get("tone", "dark")

    if tone == "accent":
        fill_rgb = accent_rgb
        text_rgb = INK_RGB
        italic = False
    else:
        # dark (default)
        fill_rgb = DARK_BG_RGB
        text_rgb = WHITE_RGB
        italic = True

    _add_rect(slide, left=left, top=top, width=width, height=height,
              fill_rgb=fill_rgb)

    if text:
        pad_v = max(0.05, (height - _text_height(text, width)) / 2)
        _add_text(
            slide, text,
            left=left + 0.25, top=top + pad_v,
            width=width - 0.50, height=height - pad_v * 2,
            size=15, color_rgb=text_rgb,
            font=branding.SANS_FONT,
            italic=italic, bold=not italic,
            anchor=MSO_ANCHOR.MIDDLE,
        )


def _text_height(text: str, width: float) -> float:
    """Rough height estimate for the callout text."""
    char_w = 15 * 0.0095
    chars_per_line = max(1, int(width / char_w))
    n_lines = max(1, -(-len(text) // chars_per_line))  # ceiling div
    return n_lines * 15 * 1.35 / 72.0
