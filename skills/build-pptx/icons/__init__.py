"""Icons package: glyph registry + SVG→PNG renderer.

Delegates to skills/_shared/icons/ where the canonical assets live.
"""
from .registry import render_icon, resolve_svg_path

__all__ = ["render_icon", "resolve_svg_path"]
