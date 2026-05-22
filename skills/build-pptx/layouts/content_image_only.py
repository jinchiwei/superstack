"""content-image-only layout: has media (images/tables) but no body text."""

from __future__ import annotations

from pathlib import Path

from pptx.dml.color import RGBColor

from palette import LIGHT

from ._common import (
    _add_chrome,
    _render_media_block,
    _set_bg,
)


def render(slide, *, params: dict, accent_rgb: RGBColor, footer_kwargs: dict, palette=LIGHT) -> None:
    """Render a media-only content slide (no body text paragraphs).

    params keys:
        title       (str)
        lede        (str)
        images      list[Path]
        tables      list[list[list[str]]]
    """
    title = params.get("title", "")
    lede = params.get("lede", "")
    images = list(params.get("images") or [])
    tables = list(params.get("tables") or [])

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

    _render_media_block(slide, images=images, tables=tables,
                        left=body_l, top=body_top,
                        width=body_w, height=body_h,
                        accent=accent_rgb)
