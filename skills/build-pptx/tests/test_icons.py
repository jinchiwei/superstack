"""Tests for the glyph icon registry and render_icon function."""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parents[1]
ICONS_DIR = SKILL_DIR / "icons"

# Ensure icons package is importable
sys.path.insert(0, str(SKILL_DIR))


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------

def test_fa_dna_resolves_to_svg():
    """FaDna resolves to the dna.svg path."""
    from icons.registry import resolve_svg_path
    path = resolve_svg_path("FaDna")
    assert path is not None
    assert path.exists()
    assert path.name == "dna.svg"


def test_fa_brain_resolves():
    from icons.registry import resolve_svg_path
    path = resolve_svg_path("FaBrain")
    assert path is not None and path.exists()


def test_fa_chart_line_resolves():
    from icons.registry import resolve_svg_path
    path = resolve_svg_path("FaChartLine")
    assert path is not None and path.exists()


def test_fa_university_resolves_via_remap():
    """FaUniversity is remapped to building-columns (FA6 rename)."""
    from icons.registry import resolve_svg_path
    path = resolve_svg_path("FaUniversity")
    assert path is not None
    assert path.exists()
    assert path.name == "building-columns.svg"


def test_fa_search_resolves_via_remap():
    """FaSearch → magnifying-glass via remap."""
    from icons.registry import resolve_svg_path
    path = resolve_svg_path("FaSearch")
    assert path is not None and path.exists()


def test_unknown_icon_returns_none():
    """An unknown icon name returns None without raising."""
    from icons.registry import resolve_svg_path
    path = resolve_svg_path("FaThisDoesNotExist99")
    assert path is None


def test_raw_kebab_name_resolves():
    """Plain kebab names (no Fa prefix) also work."""
    from icons.registry import resolve_svg_path
    path = resolve_svg_path("dna")
    assert path is not None and path.exists()


# ---------------------------------------------------------------------------
# render_icon tests
# ---------------------------------------------------------------------------

def test_render_icon_produces_png():
    """render_icon returns a PNG path that exists."""
    from icons.registry import render_icon
    png = render_icon("FaDna", "#40E0D0", size_px=64)
    assert png is not None
    assert Path(png).exists()
    assert Path(png).suffix == ".png"
    assert Path(png).stat().st_size > 100


def test_render_icon_cache_hit(tmp_path):
    """Second call returns same path; file mtime unchanged."""
    from icons.registry import render_icon
    # First call — cold
    png1 = render_icon("FaBrain", "#FF1493", size_px=64)
    assert png1 is not None
    mtime1 = Path(png1).stat().st_mtime

    # Second call — should be cache hit (same path, no re-render)
    time.sleep(0.05)
    png2 = render_icon("FaBrain", "#FF1493", size_px=64)
    assert png2 is not None
    assert png1 == png2
    mtime2 = Path(png2).stat().st_mtime
    assert mtime1 == mtime2, "mtime changed — cache was not used"


def test_render_icon_different_colors_different_files():
    """Different color_hex values produce different cache files."""
    from icons.registry import render_icon
    png_a = render_icon("FaFlask", "#40E0D0", size_px=64)
    png_b = render_icon("FaFlask", "#FF1493", size_px=64)
    assert png_a is not None and png_b is not None
    assert png_a != png_b


def test_render_icon_color_injection():
    """The rendered PNG has pixels matching the requested color (smoke test).

    We check that the PNG is non-trivially sized; full pixel comparison
    requires PIL and is expensive for CI, so we just assert the file is
    a real PNG with content.
    """
    from icons.registry import render_icon
    png = render_icon("FaDna", "#F0C840", size_px=128)
    assert png is not None
    data = Path(png).read_bytes()
    # PNG magic bytes
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(data) > 500


def test_render_icon_unknown_returns_none():
    """render_icon on an unknown name returns None without raising."""
    from icons.registry import render_icon
    result = render_icon("FaNoSuchIcon999", "#40E0D0", size_px=64)
    assert result is None


def test_render_icon_size_variants_cached_separately():
    """Same name + color at different sizes get different cache files."""
    from icons.registry import render_icon
    png_small = render_icon("FaGlobe", "#40E0D0", size_px=32)
    png_large = render_icon("FaGlobe", "#40E0D0", size_px=256)
    assert png_small is not None and png_large is not None
    assert png_small != png_large


# ---------------------------------------------------------------------------
# Coverage of all bundled icons
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fa_name", [
    "FaDna", "FaBrain", "FaFlask", "FaChartLine", "FaChartBar", "FaChartPie",
    "FaUser", "FaUsers", "FaCalendar", "FaCheck", "FaSearch",
    "FaCrosshairs", "FaExclamationTriangle", "FaArrowRight",
    "FaLayerGroup", "FaMicroscope", "FaVials",
    "FaHospital", "FaUniversity", "FaGlobe", "FaCode", "FaDatabase",
    "FaCog", "FaLightbulb", "FaKey", "FaLock", "FaEye", "FaHeart",
    "FaStar", "FaBell",
])
def test_bundled_icons_resolve(fa_name):
    """All core bundled icons resolve to an existing SVG."""
    from icons.registry import resolve_svg_path
    path = resolve_svg_path(fa_name)
    assert path is not None, f"{fa_name} did not resolve"
    assert path.exists(), f"{fa_name} → {path} does not exist"
