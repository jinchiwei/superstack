"""Shared helpers for block primitives.

Thin wrappers over _common.py utilities that the individual block modules
call instead of importing _common directly. Also provides icon helpers.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure _common is importable when this module is loaded
_LAYOUTS_DIR = Path(__file__).resolve().parents[1]
_SKILL_DIR = _LAYOUTS_DIR.parent
_SHARED_DIR = _SKILL_DIR.parent / "_shared"
sys.path.insert(0, str(_SHARED_DIR))

from layouts._common import (  # noqa: E402
    _add_text,
    _add_rect,
    _add_card,
    _add_table,
    _render_paragraph_block,
    _estimate_paragraph_height,
    _get_image_aspect,
    INK_RGB, WHITE_RGB, MUTED_RGB, DIM_RGB, DARK_BG_RGB, PAPER_RGB, RULE_RGB,
)
import branding  # noqa: E402


def _rgb_to_hex(rgb) -> str:
    """Convert RGBColor to '#RRGGBB' string."""
    return "#{:02X}{:02X}{:02X}".format(rgb[0], rgb[1], rgb[2])


def _resolve_icon_path(icon_name: str | None, icon_path: str | None,
                       color_hex: str, size_px: int = 256) -> Path | None:
    """Resolve an icon to a PNG path.

    Priority:
      1. icon_name: FA-style name (e.g. "FaDna") → look up via registry
      2. icon_path: raw file path fallback
    Returns Path or None.
    """
    if icon_name:
        try:
            from icons.registry import render_icon
            result = render_icon(icon_name, color_hex, size_px=size_px)
            if result is not None:
                return Path(result)
        except Exception:
            pass
    if icon_path:
        p = Path(icon_path)
        if p.exists():
            return p
    return None


__all__ = [
    "_add_text", "_add_rect", "_add_card", "_add_table",
    "_render_paragraph_block", "_estimate_paragraph_height", "_get_image_aspect",
    "INK_RGB", "WHITE_RGB", "MUTED_RGB", "DIM_RGB", "DARK_BG_RGB",
    "PAPER_RGB", "RULE_RGB",
    "_resolve_icon_path", "_rgb_to_hex",
    "branding",
]
