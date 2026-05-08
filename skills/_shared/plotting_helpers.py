"""Reusable matplotlib helpers used across pipeline projects.

`proportional_col_widths(rows, headers)` -> normalized column widths for
matplotlib `Table` objects so that long-content columns get more horizontal
space than short-content columns. Without this, matplotlib gives every column
equal width and long labels (model names, feature pipeline names) get visually
truncated while short numeric columns waste space.

Use anywhere you render a metrics leaderboard / scorecard table as a
matplotlib figure.
"""
from __future__ import annotations
from typing import Sequence


def proportional_col_widths(rows: Sequence[Sequence], headers: Sequence) -> list[float]:
    """Return column widths normalized to sum to 1.0, sized by max content length.

    Args:
        rows: list of row sequences (cell values; will be str()-cast for length)
        headers: header row sequence

    Returns:
        list of float widths (one per column) summing to 1.0; pass as
        `colWidths=` kwarg to `matplotlib.axes.Axes.table`.

    Each column's raw width is `max(len(str(cell)) for cell in column) + 2`
    (the +2 padding prevents tight contact with cell borders).
    """
    n_cols = len(headers)
    all_rows = [headers] + list(rows)
    raw = []
    for j in range(n_cols):
        max_len = max(len(str(r[j])) for r in all_rows)
        raw.append(max_len + 2)
    total = sum(raw)
    return [w / total for w in raw]
