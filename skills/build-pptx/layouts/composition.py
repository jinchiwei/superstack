"""composition layout — weight-based row × column block grid.

Sidecar entry shape:
{
  "kind": "composition",
  "params": {
    "title": "...",
    "lede": "...",
    "section_label": "...",
    "rows": [
      {
        "weight": 2,           // optional; default 1; overridden by "height"
        "height": 1.5,         // optional fixed inches; overrides weight
        "accent_hex": "#FF1493",  // optional per-row accent override
        "blocks": [
          {"kind": "stat-tile", "weight": 1, "params": {...}},
          {"kind": "figure",    "weight": 2, "params": {...}}
        ]
      },
      ...
    ]
  }
}

Vertical allocation:
  - Rows with "height" get that exact height (inches).
  - Remaining vertical space is divided proportionally among auto rows
    by their "weight" (default 1).
  - Inter-row gutter: 0.20in.

Horizontal allocation (per row):
  - Blocks share the row width proportionally by "weight" (default 1).
  - Inter-block gutter: 0.20in.

Per-row accent override:
  - If a row has "accent_hex", the accent colour for all blocks in that
    row is overridden.  This enables two-tone slides.
"""

from __future__ import annotations

import sys
from pathlib import Path

from pptx.dml.color import RGBColor

from ._common import (
    _add_chrome,
    _set_bg,
    _rgb,
    WHITE_RGB,
    DARK_BG_RGB,
)

from .blocks import BLOCKS


def render(slide, *, params: dict, accent_rgb: RGBColor,
           footer_kwargs: dict) -> None:
    title = params.get("title", "")
    lede = params.get("lede", "")
    dark_bg = bool(params.get("dark_bg", False))

    title_present = bool(title)
    title_wraps = len(title) > 30 if title_present else False

    _set_bg(slide, DARK_BG_RGB if dark_bg else WHITE_RGB)

    body_top, body_h, body_l, body_w, body_bottom = _add_chrome(
        slide,
        title=title,
        lede=lede,
        footer_kwargs=footer_kwargs,
        accent=accent_rgb,
        title_present=title_present,
        title_wraps=title_wraps,
        use_side_by_side=False,
        dark_bg=dark_bg,
    )

    rows = params.get("rows", [])
    if not rows:
        return

    _layout_rows(slide, rows, body_top, body_l, body_w, body_h, accent_rgb)


def _layout_rows(slide, rows: list, body_top: float, body_l: float,
                 body_w: float, body_h: float, accent_rgb: RGBColor) -> None:
    """Allocate vertical space, then dispatch each row's blocks."""
    n_rows = len(rows)
    gutter = 0.20

    # Fixed rows
    fixed_h = sum(r["height"] for r in rows if "height" in r)
    auto_rows = [r for r in rows if "height" not in r]
    total_auto_weight = sum(r.get("weight", 1) for r in auto_rows) or 1

    available_auto = max(0.2, body_h - fixed_h - gutter * max(0, n_rows - 1))

    y = body_top
    for i, row in enumerate(rows):
        if "height" in row:
            h = max(0.1, float(row["height"]))
        else:
            w = row.get("weight", 1)
            h = max(0.2, available_auto * (w / total_auto_weight))

        # Per-row accent override
        row_accent = accent_rgb
        row_accent_hex = row.get("accent_hex")
        if row_accent_hex:
            try:
                row_accent = _rgb(row_accent_hex)
            except Exception:
                pass

        blocks = row.get("blocks", [])
        if blocks:
            _layout_row_blocks(slide, blocks,
                               left=body_l, top=y,
                               width=body_w, height=h,
                               accent_rgb=row_accent)

        y += h + gutter


def _layout_row_blocks(slide, blocks: list, *, left: float, top: float,
                       width: float, height: float,
                       accent_rgb: RGBColor) -> None:
    """Allocate horizontal space for blocks in a row, then render each."""
    n_blocks = len(blocks)
    gutter = 0.20

    total_weight = sum(b.get("weight", 1) for b in blocks) or 1
    available_w = max(0.1, width - gutter * max(0, n_blocks - 1))

    x = left
    for block in blocks:
        bw = max(0.1, available_w * (block.get("weight", 1) / total_weight))
        kind = block.get("kind", "")
        bparams = block.get("params", {})

        renderer = BLOCKS.get(kind)
        if renderer is not None:
            try:
                renderer(slide,
                         left=x, top=top,
                         width=bw, height=height,
                         params=bparams,
                         accent_rgb=accent_rgb)
            except Exception as exc:
                # Graceful degradation: render an error placeholder
                from ._common import _add_text, DIM_RGB
                import branding
                _add_text(slide, f"[block error: {kind}: {exc}]",
                          left=x, top=top, width=bw, height=max(0.3, height),
                          size=9, color_rgb=DIM_RGB, font=branding.MONO_FONT)
        else:
            # Unknown kind — placeholder
            from ._common import _add_text, DIM_RGB
            import branding
            _add_text(slide, f"[unknown block: {kind}]",
                      left=x, top=top, width=bw, height=max(0.3, height),
                      size=9, color_rgb=DIM_RGB, font=branding.MONO_FONT)

        x += bw + gutter
