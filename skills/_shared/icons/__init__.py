"""Shared icon registry: FA glyph SVG → PNG renderer.

Used by build-pptx, build-xlsx, and any other skill that needs FA icons.
"""
from .registry import render_icon, resolve_svg_path

__all__ = ["render_icon", "resolve_svg_path"]
