"""content-text-image layout: slide with 1 image AND text.

Handles two sub-cases:
  - side-by-side: squarish image (aspect <= 1.3) sits beside the text
  - stacked: wide image uses full body width with text caption above
"""

from __future__ import annotations

from pathlib import Path

from pptx.dml.color import RGBColor

from ._common import (
    _add_chrome,
    _estimate_paragraph_height,
    _render_media_block,
    _render_paragraph_block,
    _set_bg,
    _strip_html,
    WHITE_RGB,
)


def render(slide, *, params: dict, accent_rgb: RGBColor, footer_kwargs: dict) -> None:
    """Render a text+image content slide.

    params keys:
        title       (str)
        lede        (str)
        body        list[{"kind", "html"}]
        images      list[Path]
        tables      list[list[list[str]]]
        use_side_by_side  (bool)  — pre-computed by dispatcher
    """
    title = params.get("title", "")
    lede = params.get("lede", "")
    body = list(params.get("body") or [])
    images = list(params.get("images") or [])
    tables = list(params.get("tables") or [])
    use_side_by_side = bool(params.get("use_side_by_side", False))

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
        use_side_by_side=use_side_by_side,
    )

    if use_side_by_side:
        side_items = list(body)
        if lede:
            side_items.insert(0, {"kind": "paragraph", "html": lede})
        text_w = 5.60
        media_l = body_l + text_w + 0.40
        media_w = body_w - text_w - 0.40
        _render_paragraph_block(slide, items=side_items, left=body_l,
                                top=body_top, width=text_w, height=body_h,
                                accent_rgb=accent_rgb, size=13,
                                distribute=True)
        _render_media_block(slide, images=images, tables=tables,
                            left=media_l, top=body_top,
                            width=media_w, height=body_h,
                            accent=accent_rgb)
    else:
        cursor = body_top
        if body:
            est_h = sum(
                _estimate_paragraph_height(
                    _strip_html(it.get("html", "") if isinstance(it, dict)
                                else str(it).lstrip("• ").strip()),
                    width=body_w, size=13)
                for it in body
            )
            est_h += (len(body) - 1) * (8 / 72.0)
            cap_h = min(1.6, max(0.4, est_h + 0.10))
            _render_paragraph_block(slide, items=body, left=body_l, top=cursor,
                                    width=body_w, height=cap_h,
                                    accent_rgb=accent_rgb, size=13)
            cursor += cap_h + 0.15
        _render_media_block(slide, images=images, tables=tables,
                            left=body_l, top=cursor,
                            width=body_w, height=body_bottom - cursor,
                            accent=accent_rgb)
