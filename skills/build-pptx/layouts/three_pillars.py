"""three-pillars layout: three columns side-by-side with optional arrow connectors."""

from __future__ import annotations

import branding
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Inches, Pt

from palette import LIGHT

from ._common import (
    _add_card,
    _add_chrome,
    _add_rect,
    _add_text,
    _set_bg,
    TURQUOISE_RGB,
    DEEPPINK_RGB,
    AMBER_RGB,
    BLUEVIOLET_RGB,
)

# Map color_role → RGBColor; actual primary is the slide's accent (passed in)
_ROLE_FALLBACK = {
    "secondary": DEEPPINK_RGB,
    "tertiary": AMBER_RGB,
}


def _pillar_color(color_role: str | None, accent_rgb: RGBColor) -> RGBColor:
    """Return the RGBColor for a pillar based on its color_role."""
    if color_role is None or color_role == "primary":
        return accent_rgb
    return _ROLE_FALLBACK.get(color_role, accent_rgb)


def render(slide, *, params: dict, accent_rgb: RGBColor, footer_kwargs: dict, palette=LIGHT) -> None:
    """Render a three-pillars content slide.

    params keys:
        title       (str)
        lede        (str)
        pillars     list[{"label": str, "body": str, "color_role": str | None}]  — 2-3 items
        show_arrows (bool, default True for 3 pillars)
    """
    title = params.get("title", "")
    lede = params.get("lede", "")
    pillars = list(params.get("pillars") or [])
    n = max(1, len(pillars))

    show_arrows = params.get("show_arrows")
    if show_arrows is None:
        show_arrows = (n == 3)

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

    # Compute column geometry
    arrow_w = 0.25 if show_arrows and n > 1 else 0.0
    n_gaps = n - 1
    total_arrow_space = arrow_w * n_gaps
    gutter = 0.20
    col_w = (body_w - total_arrow_space - gutter * (n - 1)) / n

    for i, pillar in enumerate(pillars):
        col_l = body_l + i * (col_w + arrow_w + gutter)
        color = _pillar_color(pillar.get("color_role"), accent_rgb)
        _add_card(
            slide,
            label=pillar.get("label", ""),
            body=pillar.get("body", ""),
            left=col_l,
            top=body_top,
            width=col_w,
            height=body_h,
            accent_rgb=color,
            surface_rgb=palette.surface_rgb,
            text_rgb=palette.text_rgb,
        )

        # Arrow connector between columns (except after last)
        if show_arrows and i < len(pillars) - 1:
            arrow_l = col_l + col_w + 0.03
            arrow_h = 0.30
            arrow_top = body_top + (body_h - arrow_h) / 2
            shp = slide.shapes.add_shape(
                MSO_SHAPE.RIGHT_ARROW,
                Inches(arrow_l), Inches(arrow_top),
                Inches(arrow_w - 0.05), Inches(arrow_h),
            )
            shp.fill.solid()
            shp.fill.fore_color.rgb = accent_rgb
            shp.line.fill.background()
            shp.shadow.inherit = False
