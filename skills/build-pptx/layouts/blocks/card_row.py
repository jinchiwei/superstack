"""card-row block — N cards side-by-side, each with optional icon.

params:
    cards   list[dict]  — each: {"label": str, "body": str, "icon": "FaName",
                                  "icon_path": "path/to/icon.png"}
"""
from __future__ import annotations

from pptx.dml.color import RGBColor
from pptx.util import Inches

from ._base import (
    _add_card, _add_text,
    PAPER_RGB, INK_RGB,
    branding,
    _resolve_icon_path, _rgb_to_hex,
)


def render(slide, *, left: float, top: float, width: float, height: float,
           params: dict, accent_rgb: RGBColor) -> None:
    cards = params.get("cards", [])
    if not cards:
        return

    n = len(cards)
    gutter = 0.15
    card_w = (width - gutter * (n - 1)) / n

    # Build accent hex from RGBColor for icon color injection
    accent_hex = _rgb_to_hex(accent_rgb)

    for i, card in enumerate(cards):
        card_left = left + i * (card_w + gutter)
        label = str(card.get("label", ""))
        body = str(card.get("body", ""))
        icon_name = card.get("icon")
        icon_path_str = card.get("icon_path")

        icon_path = _resolve_icon_path(icon_name, icon_path_str, accent_hex, size_px=128)

        _add_card(
            slide,
            label=label,
            body=body,
            left=card_left, top=top,
            width=card_w, height=height,
            accent_rgb=accent_rgb,
            icon_path=icon_path,
        )
