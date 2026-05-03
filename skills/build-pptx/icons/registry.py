"""Glyph icon registry — thin shim that delegates to skills/_shared/icons/registry.py.

The canonical implementation (including SVG assets, cache, and render_icon)
lives in skills/_shared/icons/ so that build-xlsx and other skills can share
the same FA icon pipeline without duplicating assets.

All existing callers that imported from this module continue to work unchanged.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SHARED_REGISTRY = Path(__file__).resolve().parents[2] / "_shared" / "icons" / "registry.py"

# Load the shared registry as a module, bypassing package import mechanics.
_spec = importlib.util.spec_from_file_location(
    "_shared_icons_registry", str(_SHARED_REGISTRY)
)
_mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]

# Re-export everything callers expect.
render_icon = _mod.render_icon
resolve_svg_path = _mod.resolve_svg_path
_fa_to_kebab = _mod._fa_to_kebab
_FA6_REMAP = _mod._FA6_REMAP

__all__ = ["render_icon", "resolve_svg_path", "_fa_to_kebab", "_FA6_REMAP"]
