"""cards-heterogeneous layout: one large primary card left + 2-3 secondary cards stacked right."""

from __future__ import annotations

from pathlib import Path

import branding
from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt

from ._common import (
    _add_card,
    _add_chrome,
    _add_rect,
    _add_text,
    _set_bg,
    WHITE_RGB,
    PAPER_RGB,
    INK_RGB,
)


def render(slide, *, params: dict, accent_rgb: RGBColor, footer_kwargs: dict) -> None:
    """Render a heterogeneous-cards slide.

    params keys:
        title           (str)
        lede            (str)
        primary_card    {"label": str, "body": str, "icon": Path | None}
        secondary_cards list[{"label": str, "body": str, "icon": Path | None}]  — 2-3 items
    """
    title = params.get("title", "")
    lede = params.get("lede", "")
    primary = params.get("primary_card") or {}
    secondary_cards = list(params.get("secondary_cards") or [])

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

    primary_w = body_w * 0.60
    right_gap = 0.20
    right_l = body_l + primary_w + right_gap
    right_w = body_w - primary_w - right_gap

    # --- Primary card (bigger label 15pt, body 13pt) ---
    p_label = primary.get("label", "")
    p_body = primary.get("body", "")
    p_icon = primary.get("icon")

    _add_rect(slide, left=body_l, top=body_top, width=primary_w, height=body_h,
              fill_rgb=PAPER_RGB)
    _add_rect(slide, left=body_l, top=body_top, width=primary_w, height=0.06,
              fill_rgb=accent_rgb)

    if p_icon is not None:
        p_icon = Path(p_icon) if not isinstance(p_icon, Path) else p_icon

    if p_icon is not None and p_icon.exists():
        try:
            slide.shapes.add_picture(
                str(p_icon),
                Inches(body_l + 0.18), Inches(body_top + 0.20),
                width=Inches(0.40), height=Inches(0.40),
            )
            label_l = body_l + 0.70
            label_w = primary_w - 0.88
        except Exception:
            label_l = body_l + 0.18
            label_w = primary_w - 0.36
    else:
        label_l = body_l + 0.18
        label_w = primary_w - 0.36

    _add_text(slide, p_label, left=label_l, top=body_top + 0.20,
              width=label_w, height=0.50,
              size=15, color_rgb=accent_rgb, font=branding.MONO_FONT, bold=True)
    _add_text(slide, p_body, left=body_l + 0.18, top=body_top + 0.80,
              width=primary_w - 0.36, height=body_h - 0.90,
              size=13, color_rgb=INK_RGB, font=branding.SANS_FONT)

    # --- Secondary cards stacked vertically ---
    n = max(1, len(secondary_cards))
    gutter = 0.15
    sec_h = (body_h - gutter * (n - 1)) / n

    for i, card in enumerate(secondary_cards):
        cy = body_top + i * (sec_h + gutter)
        _add_card(
            slide,
            label=card.get("label", ""),
            body=card.get("body", ""),
            left=right_l,
            top=cy,
            width=right_w,
            height=sec_h,
            accent_rgb=accent_rgb,
            icon_path=card.get("icon"),
        )
