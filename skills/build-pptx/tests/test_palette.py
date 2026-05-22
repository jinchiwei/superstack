import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from palette import LIGHT, Palette, palette_for_theme
from themes import get_theme
from layouts._common import INK_RGB, WHITE_RGB, MUTED_RGB, RULE_RGB, PAPER_RGB


def test_light_palette_equals_todays_constants():
    assert LIGHT.canvas_rgb == WHITE_RGB
    assert LIGHT.text_rgb == INK_RGB
    assert LIGHT.muted_rgb == MUTED_RGB
    assert LIGHT.surface_rgb == PAPER_RGB
    assert LIGHT.rule_rgb == RULE_RGB
    assert LIGHT.on_dark is False


def test_palette_for_none_theme_is_light():
    assert palette_for_theme(None) is LIGHT


def test_dark_theme_palette_inverts():
    p = palette_for_theme(get_theme("midnight"))
    assert p.on_dark is True
    assert str(p.canvas_rgb) == "14141C"
    assert p.text_rgb == WHITE_RGB
    assert str(p.surface_rgb) != "14141C"


def test_light_theme_palette_keeps_dark_text():
    p = palette_for_theme(get_theme("paper"))
    assert p.on_dark is False
    assert p.text_rgb == INK_RGB
    assert str(p.canvas_rgb) == "FFFFFF"
