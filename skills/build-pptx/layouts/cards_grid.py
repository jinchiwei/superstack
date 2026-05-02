"""cards-grid layout: auto-detected def-list bullets or h3-led blocks."""

from __future__ import annotations

from pptx.dml.color import RGBColor

from ._common import (
    _add_card,
    _add_chrome,
    _render_paragraph_block,
    _set_bg,
    WHITE_RGB,
)


def render(slide, *, params: dict, accent_rgb: RGBColor, footer_kwargs: dict) -> None:
    """Render a cards-grid content slide.

    params keys:
        title       (str)
        lede        (str)
        body        list[{"kind", "html"}]  — intro paragraphs above the grid
        cards       list[{"label", "body", "icon"}]
    """
    title = params.get("title", "")
    lede = params.get("lede", "")
    body = list(params.get("body") or [])
    cards = list(params.get("cards") or [])

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
                                width=body_w, height=1.0,
                                accent_rgb=accent_rgb, size=13)
        grid_top = body_top + 1.10
    else:
        grid_top = body_top

    n = len(cards)
    if n == 0:
        return
    cols = 3 if n >= 3 else max(n, 1)
    rows = (n + cols - 1) // cols
    gutter = 0.20
    card_w = (body_w - gutter * (cols - 1)) / cols
    avail_h = body_bottom - grid_top
    card_h = (avail_h - gutter * (rows - 1)) / rows
    for i, card in enumerate(cards):
        r, c = divmod(i, cols)
        cx = body_l + c * (card_w + gutter)
        cy = grid_top + r * (card_h + gutter)
        _add_card(slide, label=card["label"], body=card["body"],
                  left=cx, top=cy, width=card_w, height=card_h,
                  accent_rgb=accent_rgb,
                  icon_path=card.get("icon"))
