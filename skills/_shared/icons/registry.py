"""Glyph icon registry: FA name → SVG path, and render_icon() → PNG path.

Shared across build-pptx, build-xlsx, and any other skill needing FA icons.
SVG assets live in the `svgs/` sub-directory next to this file; PNGs are
cached in `cache/` for re-use across renders.

Usage:
    from skills._shared.icons.registry import render_icon
    png_path = render_icon("FaDna", "#40E0D0", size_px=256)

Name mapping: strips 'Fa' prefix, converts CamelCase to kebab-case.
  FaDna → dna
  FaChartLine → chart-line
  FaExclamationTriangle → triangle-exclamation  (FA6 renamed)

Falls back to None if the SVG is not bundled.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Pre-load libcairo if it's at the Homebrew path but not on DYLD_LIBRARY_PATH
# (macOS: Apple SIP strips DYLD_* in most contexts).
# ---------------------------------------------------------------------------
def _preload_cairo() -> None:
    import ctypes
    # Prefer the short-name dlopen — succeeds if libcairo is on the runtime
    # linker's search path. ctypes.util.find_library is unreliable here:
    # on Linux it can return the SONAME (e.g. "libcairo.so.2") via gcc
    # introspection even when the file isn't on LD_LIBRARY_PATH, so
    # downstream cairocffi.dlopen still fails. Attempt an actual load
    # instead, then fall back to explicit known paths.
    for short in ("libcairo.so.2", "libcairo.2.dylib", "libcairo-2.dll"):
        try:
            ctypes.CDLL(short, mode=ctypes.RTLD_GLOBAL)
            return
        except OSError:
            continue
    # Try common locations:
    #   macOS Homebrew: /opt/homebrew, /usr/local
    #   Linux conda:    /opt/conda/lib (SageMaker, CI containers), $CONDA_PREFIX/lib
    import os
    candidates = [
        "/opt/homebrew/lib/libcairo.2.dylib",
        "/opt/homebrew/lib/libcairo.dylib",
        "/usr/local/lib/libcairo.2.dylib",
        "/usr/local/lib/libcairo.dylib",
        "/opt/conda/lib/libcairo.so.2",
        "/opt/conda/lib/libcairo.so",
    ]
    if (cp := os.environ.get("CONDA_PREFIX")):
        candidates.extend([f"{cp}/lib/libcairo.so.2", f"{cp}/lib/libcairo.so"])
    for candidate in candidates:
        try:
            # RTLD_GLOBAL so symbols are visible to subsequent dlopen()s by
            # short name from cairocffi/libffi — without this the macOS
            # preload "works" but Linux still fails on cairocffi import.
            ctypes.CDLL(candidate, mode=ctypes.RTLD_GLOBAL)
            return
        except OSError:
            continue


_preload_cairo()

_ICONS_DIR = Path(__file__).resolve().parent
_SVG_DIR = _ICONS_DIR / "svgs"
_CACHE_DIR = _ICONS_DIR / "cache"

# ---------------------------------------------------------------------------
# FA6 name remaps: old FA5 / logical names → actual FA6 filename (kebab)
# ---------------------------------------------------------------------------
_FA6_REMAP: dict[str, str] = {
    # FA5 → FA6 renames
    "search":              "magnifying-glass",
    "exclamation-triangle":"triangle-exclamation",
    "university":          "building-columns",
    "cog":                 "gear",
    "check-circle":        "circle-check",
    "info-circle":         "circle-info",
    "question-circle":     "circle-question",
    "shield-alt":          "shield-halved",
    "magic":               "wand-magic-sparkles",
    "user-md":             "user-doctor",
    "calendar-alt":        "calendar-days",
    "project-diagram":     "diagram-project",
    # convenience aliases
    "chart-line":          "chart-line",
    "chart-bar":           "chart-bar",
    "chart-pie":           "chart-pie",
}


def _fa_to_kebab(fa_name: str) -> str:
    """Convert FaCamelCase → kebab-case, then apply FA6 remaps."""
    # Strip 'Fa' prefix if present
    name = fa_name
    if name.startswith("Fa"):
        name = name[2:]
    # CamelCase → kebab-case
    name = re.sub(r"([A-Z])", lambda m: "-" + m.group(1).lower(), name)
    name = name.lstrip("-")
    # Apply remap
    return _FA6_REMAP.get(name, name)


def resolve_svg_path(name: str) -> Path | None:
    """Return the SVG path for a name (FaCamelCase or raw kebab). None if not bundled."""
    kebab = _fa_to_kebab(name)
    candidate = _SVG_DIR / f"{kebab}.svg"
    if candidate.exists():
        return candidate
    # Try raw name as-is
    raw = _SVG_DIR / f"{name}.svg"
    if raw.exists():
        return raw
    return None


def render_icon(name: str, color_hex: str, size_px: int = 256) -> Path | None:
    """Render an icon SVG to a PNG with color injection. Returns PNG path or None.

    Caches by sha256(name + color_hex + size_px)[:16].
    """
    svg_path = resolve_svg_path(name)
    if svg_path is None:
        return None

    try:
        import cairosvg  # type: ignore
    except ImportError:
        return None

    _CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # Build cache key
    cache_key = hashlib.sha256(
        f"{name}:{color_hex}:{size_px}".encode()
    ).hexdigest()[:16]
    cache_path = _CACHE_DIR / f"{cache_key}.png"

    if cache_path.exists():
        return cache_path

    # Read + color-inject SVG
    svg_text = svg_path.read_text(encoding="utf-8")
    # Inject fill color on the root <svg> element
    svg_text = re.sub(
        r"(<svg\b[^>]*?)>",
        lambda m: m.group(1) + f' fill="{color_hex}">',
        svg_text,
        count=1,
    )
    svg_bytes = svg_text.encode("utf-8")

    cairosvg.svg2png(
        bytestring=svg_bytes,
        output_width=size_px,
        output_height=size_px,
        write_to=str(cache_path),
    )
    return cache_path
