"""left-accent-card block — card with vertical left stripe (pattern 7).

Like _add_card but the stripe is on the left edge (0.06in wide × full
card height) instead of the top. Paper bg fill, no shadow.

params:
    label   str     — card heading
    body    str     — card body text
    icon    str     — optional FA icon name (e.g. "FaDna")
    icon_path str   — optional raw icon path fallback
"""
from __future__ import annotations

from pptx.dml.color import RGBColor
from pptx.util import Inches

from ._base import (
    _add_text, _add_rect,
    PAPER_RGB, INK_RGB,
    branding,
    _resolve_icon_path, _rgb_to_hex,
)


def render(slide, *, left: float, top: float, width: float, height: float,
           params: dict, accent_rgb: RGBColor) -> None:
    label = str(params.get("label", ""))
    body = str(params.get("body", ""))
    icon_name = params.get("icon")
    icon_path_str = params.get("icon_path")

    # Paper bg
    _add_rect(slide, left=left, top=top, width=width, height=height,
              fill_rgb=PAPER_RGB)

    # Left vertical accent stripe
    stripe_w = 0.06
    _add_rect(slide, left=left, top=top, width=stripe_w, height=height,
              fill_rgb=accent_rgb)

    content_left = left + stripe_w + 0.14
    content_w = width - stripe_w - 0.28

    # Optional icon — top-right corner
    accent_hex = _rgb_to_hex(accent_rgb)
    icon_size = 0.30
    if icon_name or icon_path_str:
        icon_path = _resolve_icon_path(icon_name, icon_path_str, accent_hex, size_px=128)
        if icon_path is not None:
            try:
                slide.shapes.add_picture(
                    str(icon_path),
                    Inches(left + width - icon_size - 0.10),
                    Inches(top + 0.10),
                    width=Inches(icon_size),
                    height=Inches(icon_size),
                )
                content_w = width - stripe_w - 0.28 - icon_size - 0.12
            except Exception:
                pass

    _add_text(slide, label,
              left=content_left, top=top + 0.12,
              width=content_w, height=0.36,
              size=13, color_rgb=accent_rgb,
              font=branding.MONO_FONT, bold=True)

    if body:
        _add_text(slide, body,
                  left=content_left, top=top + 0.52,
                  width=content_w, height=max(0.20, height - 0.60),
                  size=12, color_rgb=INK_RGB, font=branding.SANS_FONT)
