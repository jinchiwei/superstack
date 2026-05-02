"""Registry mapping layout-id strings to render functions. New layouts plug
in here without touching the dispatcher."""

from . import (content_text, content_text_image, content_image_only,
               cards_grid)

REGISTRY = {
    "content-text":         content_text.render,
    "content-text-image":   content_text_image.render,
    "content-image-only":   content_image_only.render,
    "cards-grid":           cards_grid.render,
}


def get(kind: str):
    """Return the render function for a given layout kind. Raises KeyError
    on unknown kinds — callers should validate against REGISTRY first."""
    return REGISTRY[kind]
