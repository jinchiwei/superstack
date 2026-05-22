import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import inspect
from layouts import _common


def test_add_card_accepts_surface_and_text_overrides():
    sig = inspect.signature(_common._add_card)
    assert "surface_rgb" in sig.parameters
    assert "text_rgb" in sig.parameters
