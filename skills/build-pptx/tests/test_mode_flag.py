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


def test_mode_persists_across_shake(tmp_path):
    import subprocess
    skill_dir = Path(__file__).resolve().parents[1]
    md = tmp_path / "deck.md"
    md.write_text("---\ntitle: T\n---\n\n# A\n\nsome text\n", encoding="utf-8")
    # Drive through the deepdream interpreter explicitly so the subprocess
    # uses the same environment as the test runner regardless of sys.executable.
    py = str(Path.home() / "miniconda3/envs/deepdream/bin/python")
    if not Path(py).exists():
        py = sys.executable
    # First build in strict mode.
    subprocess.run([py, "build.py", "--input", str(md), "--output",
                    str(tmp_path / "a.pptx"), "--mode", "strict"],
                   cwd=skill_dir, check=True, capture_output=True)
    sidecar = md.with_suffix(md.suffix + ".layout.json")
    assert json.loads(sidecar.read_text())["mode"] == "strict"
    # Now --shake WITHOUT --mode: mode must remain strict.
    subprocess.run([py, "build.py", "--input", str(md), "--output",
                    str(tmp_path / "b.pptx"), "--shake"],
                   cwd=skill_dir, check=True, capture_output=True)
    assert json.loads(sidecar.read_text())["mode"] == "strict"
