import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from plan import Plan, SlideEntry


def test_plan_defaults_to_expressive():
    p = Plan(deck_md_hash="abc")
    assert p.mode == "expressive"
    assert p.theme is None


def test_plan_roundtrips_mode_and_theme():
    p = Plan(deck_md_hash="abc", mode="strict", theme="midnight",
             slides=[SlideEntry(slide_id="h1-x", kind="content-text")])
    restored = Plan.from_json(p.to_json())
    assert restored.mode == "strict"
    assert restored.theme == "midnight"
    assert restored.slides[0].slide_id == "h1-x"


def test_old_sidecar_without_mode_loads_with_defaults():
    legacy = json.dumps({
        "version": 1, "deck_md_hash": "abc", "shake_seed": None,
        "slides": [{"slide_id": "h1-x", "kind": "content-text",
                    "params": {}, "content_hash": ""}],
    })
    restored = Plan.from_json(legacy)
    assert restored.mode == "expressive"
    assert restored.theme is None
