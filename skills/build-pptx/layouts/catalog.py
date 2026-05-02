"""Registry mapping layout-id strings to render functions. New layouts plug
in here without touching the dispatcher."""

from . import (content_text, content_text_image, content_image_only,
               cards_grid, cards_heterogeneous, three_pillars,
               stat_callouts_right, bg_flip, timeline)

REGISTRY = {
    "content-text":         content_text.render,
    "content-text-image":   content_text_image.render,
    "content-image-only":   content_image_only.render,
    "cards-grid":           cards_grid.render,
    "cards-heterogeneous":  cards_heterogeneous.render,
    "three-pillars":        three_pillars.render,
    "stat-callouts-right":  stat_callouts_right.render,
    "bg-flip":              bg_flip.render,
    "timeline":             timeline.render,
}


def get(kind: str):
    """Return the render function for a given layout kind. Raises KeyError
    on unknown kinds — callers should validate against REGISTRY first."""
    return REGISTRY[kind]
