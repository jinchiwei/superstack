"""Block primitives for the composition layout.

Each module exposes:
    render(slide, *, left, top, width, height, params, accent_rgb)

Exported names map to the JSON kind strings (with underscores matching
hyphen-separated names in JSON after normalisation in composition.py).
"""
from .paragraph import render as paragraph
from .figure import render as figure
from .card_row import render as card_row
from .stat_tile import render as stat_tile
from .accent_callout import render as accent_callout
from .table import render as table
from .quote import render as quote
from .left_accent_card import render as left_accent_card

# Registry: JSON kind string → render function
BLOCKS: dict = {
    "paragraph":        paragraph,
    "figure":           figure,
    "card-row":         card_row,
    "stat-tile":        stat_tile,
    "accent-callout":   accent_callout,
    "table":            table,
    "quote":            quote,
    "left-accent-card": left_accent_card,
}
