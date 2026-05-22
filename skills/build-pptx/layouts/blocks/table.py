"""table block — accent-headered data table.

Reuses _add_table from _common.py.

params:
    rows    list[list]  — first row is the header; subsequent are data
                          cells can be str, int, or float
"""
from __future__ import annotations

from pptx.dml.color import RGBColor

from ._base import _add_table


def render(slide, *, left: float, top: float, width: float, height: float,
           params: dict, accent_rgb: RGBColor,
           surface_rgb: RGBColor | None = None,
           text_rgb: RGBColor | None = None) -> None:
    raw_rows = params.get("rows", [])
    if not raw_rows:
        return

    # Stringify all cells for _add_table
    rows = [[str(cell) for cell in row] for row in raw_rows]

    _add_table(
        slide,
        rows=rows,
        left=left, top=top,
        width=width, max_height=height,
        header_rgb=accent_rgb,
        surface_rgb=surface_rgb,
        text_rgb=text_rgb,
    )
