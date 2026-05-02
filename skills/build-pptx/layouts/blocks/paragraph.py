"""paragraph block — wrapped prose, optional bullets.

params:
    items   list[str]  — text items; prefix "• " to force bullet style
    size    int        — font size in pt (default 14)
    bullets bool       — if true, render all items as bullet lines
"""
from __future__ import annotations

from pptx.dml.color import RGBColor

from ._base import _render_paragraph_block


def render(slide, *, left: float, top: float, width: float, height: float,
           params: dict, accent_rgb: RGBColor) -> None:
    items_raw = params.get("items", [])
    size = params.get("size", 14)
    bullets = params.get("bullets", False)

    # Normalise to the format _render_paragraph_block expects
    items = []
    for item in items_raw:
        if isinstance(item, dict):
            items.append(item)
        else:
            text = str(item)
            if bullets or text.startswith("•"):
                items.append({"kind": "bullet", "html": text.lstrip("• ").strip()})
            else:
                items.append({"kind": "paragraph", "html": text})

    if not items:
        return

    _render_paragraph_block(
        slide,
        items=items,
        left=left, top=top, width=width, height=height,
        accent_rgb=accent_rgb,
        size=size,
        distribute=True,
    )
