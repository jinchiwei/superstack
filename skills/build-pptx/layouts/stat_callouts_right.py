"""stat-callouts-right layout: chart on the left, 4 stat tiles stacked on the right."""

from __future__ import annotations

from pathlib import Path

import branding
from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt

from palette import LIGHT

from ._common import (
    _add_chrome,
    _add_text,
    _get_image_aspect,
    _set_bg,
    DIM_RGB,
)

# Width budget for the image column (inches)
_IMAGE_COL_W = 7.5
# Left edge of the stats column
_STATS_COL_OFFSET = 7.7


def render(slide, *, params: dict, accent_rgb: RGBColor, footer_kwargs: dict, palette=LIGHT) -> None:
    """Render a stat-callouts-right content slide.

    params keys:
        title   (str)
        lede    (str)
        image   Path   — chart on the left
        stats   list[{"value": str, "label": str}]  — 2-4 items
    """
    title = params.get("title", "")
    lede = params.get("lede", "")
    image_path = params.get("image")
    stats = list(params.get("stats") or [])

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

    # ── Image on left ──────────────────────────────────────────────────────────
    img_l = body_l
    img_t = body_top
    img_w = _IMAGE_COL_W

    if image_path is not None:
        image_path = Path(image_path) if not isinstance(image_path, Path) else image_path

    if image_path is not None and image_path.exists():
        try:
            aspect = _get_image_aspect(image_path)
            img_h = img_w / aspect if aspect > 0 else body_h
            img_h = min(img_h, body_h)
            # Center vertically if shorter than body region
            v_offset = (body_h - img_h) / 2
            slide.shapes.add_picture(
                str(image_path),
                Inches(img_l), Inches(img_t + v_offset),
                width=Inches(img_w), height=Inches(img_h),
            )
        except Exception as e:
            _add_text(slide, f"[image: {image_path.name}: {e}]",
                      left=img_l, top=img_t, width=img_w, height=0.5,
                      size=10,
                      color_rgb=(palette.muted_rgb if palette.on_dark else DIM_RGB),
                      font=branding.MONO_FONT)
    else:
        # Placeholder box when image not available
        _add_text(slide, "[chart placeholder]",
                  left=img_l, top=img_t, width=img_w, height=body_h,
                  size=11,
                  color_rgb=(palette.muted_rgb if palette.on_dark else DIM_RGB),
                  font=branding.MONO_FONT)

    # ── Stats on right ─────────────────────────────────────────────────────────
    if not stats:
        return

    stats_l = body_l + _STATS_COL_OFFSET
    stats_w = body_w - _STATS_COL_OFFSET + body_l  # remaining right space

    # Ensure stats column doesn't go off-slide
    slide_w = 13.333
    if stats_l + stats_w > slide_w - 0.1:
        stats_w = slide_w - 0.1 - stats_l

    n = len(stats)
    gutter = 0.15
    value_h = 0.42    # height for the big number
    label_h = 0.36    # height for the smaller label
    tile_h = value_h + label_h + 0.08
    total_h = n * tile_h + (n - 1) * gutter
    # Centre the stats column vertically within body_h
    v_start = body_top + max(0.0, (body_h - total_h) / 2)

    for i, stat in enumerate(stats):
        tile_top = v_start + i * (tile_h + gutter)
        _add_text(
            slide, stat.get("value", ""),
            left=stats_l, top=tile_top,
            width=stats_w, height=value_h,
            size=24, color_rgb=accent_rgb, font=branding.MONO_FONT, bold=True,
        )
        _add_text(
            slide, stat.get("label", ""),
            left=stats_l, top=tile_top + value_h,
            width=stats_w, height=label_h,
            size=12, color_rgb=palette.muted_rgb, font=branding.SANS_FONT,
        )
