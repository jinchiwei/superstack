"""table-with-takeaway layout — full-width data table + accent-callout footer.

Sidecar entry shape:
{
  "kind": "table-with-takeaway",
  "params": {
    "title": "...",
    "lede": "...",
    "section_label": "...",
    "rows": [
      ["Col A", "Col B", "Col C"],
      ["data",  "data",  "data"],
      ...
    ],
    "callout": {"text": "...", "tone": "dark"}
  }
}

Geometry:
  - Table block: 3/4 of body height (or as much as needed, floored at callout)
  - Accent callout: 1/4 of body height
  - Gutter between: 0.20in
"""

from __future__ import annotations

import branding
from pptx.dml.color import RGBColor

from palette import LIGHT

from ._common import (
    _add_chrome,
    _set_bg,
)
from .blocks.table import render as _table
from .blocks.accent_callout import render as _accent_callout


def render(slide, *, params: dict, accent_rgb: RGBColor, footer_kwargs: dict, palette=LIGHT) -> None:
    """Render a table-with-takeaway slide.

    params keys:
        title       str
        lede        str
        section_label str
        rows        list[list[str]]  — first row is the header
        callout     {"text": str, "tone": "dark"|"accent"}
    """
    title = params.get("title", "")
    lede = params.get("lede", "")
    rows = list(params.get("rows") or [])
    callout = params.get("callout") or {}

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

    gutter = 0.20
    # Only reserve space for the callout band when there's actually takeaway
    # text. An empty callout dict must NOT paint a blank band — the table
    # takes the full body height instead.
    has_callout = bool((callout or {}).get("text"))
    if has_callout:
        callout_h = max(0.55, body_h / 4)
        table_h = max(0.50, body_h - callout_h - gutter)
    else:
        callout_h = 0.0
        table_h = body_h

    # Theme block-helper colors only on dark palettes. Under a light/strict
    # palette, pass None so the block helpers fall back to their exact
    # original (possibly distinct) constants — preserving byte parity
    # (e.g. the alternating PAPER/WHITE table-row striping).
    _surf = palette.surface_rgb if palette.on_dark else None
    _text = palette.text_rgb if palette.on_dark else None

    # ── Table ─────────────────────────────────────────────────────────────────
    if rows:
        _table(
            slide,
            left=body_l, top=body_top,
            width=body_w, height=table_h,
            params={"rows": rows},
            accent_rgb=accent_rgb,
            surface_rgb=_surf,
            text_rgb=_text,
        )

    # ── Accent callout (only when there is takeaway text) ──────────────────────
    if has_callout:
        callout_top = body_top + table_h + gutter
        _accent_callout(
            slide,
            left=body_l, top=callout_top,
            width=body_w, height=callout_h,
            params=callout,
            accent_rgb=accent_rgb,
        )
