"""stats-with-takeaway layout — N big-number stat tiles + dark accent-callout footer.

Sidecar entry shape:
{
  "kind": "stats-with-takeaway",
  "params": {
    "title": "...",
    "lede": "...",
    "section_label": "...",
    "stats": [
      {"value": "0.91", "label": "Internal AUC", "sub": "5-seed mean"},
      ...
    ],
    "callout": {"text": "key takeaway sentence", "tone": "dark"}
  }
}

Geometry:
  - Stat tiles row: 2/3 of body height
  - Accent callout: 1/3 of body height
  - Gutter between: 0.20in

Icon-homogeneity rule: if stats[].icon is provided but all tiles are the
same semantic kind (e.g., all model-performance metrics, all patient counts),
drop icons to avoid arbitrary icon variation. The caller can suppress this by
ensuring icons genuinely differ in meaning. By default, this layout drops icons
unless the caller explicitly varies them — if all icons are the same FA name,
they are all dropped.
"""

from __future__ import annotations

import branding
from pptx.dml.color import RGBColor

from palette import LIGHT

from ._common import (
    _add_chrome,
    _set_bg,
)
from .blocks.stat_tile import render as _stat_tile
from .blocks.accent_callout import render as _accent_callout


def render(slide, *, params: dict, accent_rgb: RGBColor, footer_kwargs: dict, palette=LIGHT) -> None:
    """Render a stats-with-takeaway slide.

    params keys:
        title       str
        lede        str
        section_label str
        stats       list[{"value": str, "label": str, "sub": str, "icon": str}]
                    2–5 entries; icon is optional FA name
        callout     {"text": str, "tone": "dark"|"accent"}
    """
    title = params.get("title", "")
    lede = params.get("lede", "")
    stats = list(params.get("stats") or [])
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
    )

    gutter = 0.20
    callout_h = max(0.60, body_h / 3)
    stat_h = max(0.50, body_h - callout_h - gutter)

    # ── Apply icon-homogeneity rule ──────────────────────────────────────────
    # If every stat has the same icon name (or all have the same icon after
    # deduplication), drop all icons — homogeneous rows don't benefit from icons.
    all_icons = [str(s.get("icon") or "") for s in stats]
    non_empty_icons = [ic for ic in all_icons if ic]
    homogeneous_icons = (
        len(non_empty_icons) > 0
        and len(set(non_empty_icons)) == 1  # all same icon
    )
    if homogeneous_icons:
        stats = [{**s, "icon": None} for s in stats]

    # Theme block-helper colors only on dark palettes. Under a light/strict
    # palette, pass None so the block helpers fall back to their exact
    # original (possibly distinct) constants — preserving byte parity
    # (e.g. the distinct MUTED label / DIM sub colors in stat tiles).
    _surf = palette.surface_rgb if palette.on_dark else None
    _text = palette.text_rgb if palette.on_dark else None
    _muted = palette.muted_rgb if palette.on_dark else None

    # ── Stat tiles grid ──────────────────────────────────────────────────────
    # n=1..4 → 1 row; n=5..8 → 2 rows so each tile stays readable.
    n = max(len(stats), 1)
    tile_gutter = 0.15
    if n <= 4:
        cols = n
    elif n in (5, 6):
        cols = 3   # 2x3
    elif n in (7, 8):
        cols = 4   # 2x4
    else:
        cols = 4   # cap; further rows
    rows = (n + cols - 1) // cols
    tile_w = (body_w - tile_gutter * (cols - 1)) / cols
    tile_row_h = (stat_h - tile_gutter * (rows - 1)) / rows if rows > 1 else stat_h

    for i, stat in enumerate(stats):
        r = i // cols
        c = i % cols
        # If the last row is partial, center its tiles within the body width
        row_start = i // cols * cols
        row_end = min(row_start + cols, n)
        row_count = row_end - row_start
        if row_count < cols:
            row_w = row_count * tile_w + (row_count - 1) * tile_gutter
            row_left = body_l + (body_w - row_w) / 2
        else:
            row_left = body_l
        tile_left = row_left + c * (tile_w + tile_gutter)
        tile_top = body_top + r * (tile_row_h + tile_gutter)
        _stat_tile(
            slide,
            left=tile_left, top=tile_top,
            width=tile_w, height=tile_row_h,
            params=stat,
            accent_rgb=accent_rgb,
            surface_rgb=_surf,
            text_rgb=_text,
            muted_rgb=_muted,
        )

    # ── Accent callout ───────────────────────────────────────────────────────
    callout_top = body_top + stat_h + gutter
    _accent_callout(
        slide,
        left=body_l, top=callout_top,
        width=body_w, height=callout_h,
        params=callout,
        accent_rgb=accent_rgb,
    )
