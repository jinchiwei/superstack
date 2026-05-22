"""content-text layout: text-only content slide (bullets/paragraphs, no media, no cards)."""

from __future__ import annotations

from pptx.dml.color import RGBColor

from palette import LIGHT

from ._common import (
    _add_chrome,
    _render_paragraph_block,
    _set_bg,
    WHITE_RGB,
)


def render(slide, *, params: dict, accent_rgb: RGBColor, footer_kwargs: dict, palette=LIGHT) -> None:
    """Render a text-only content slide.

    params keys:
        title       (str)
        lede        (str)
        body        list[{"kind", "html"}]
    """
    title = params.get("title", "")
    lede = params.get("lede", "")
    body = list(params.get("body") or [])

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

    if body:
        _render_paragraph_block(slide, items=body, left=body_l, top=body_top,
                                width=body_w, height=body_h,
                                accent_rgb=accent_rgb, size=14,
                                distribute=True)
