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
    subprocess.run([py, "build.py", "--allow-composed", "--input", str(md), "--output",
                    str(tmp_path / "a.pptx"), "--mode", "strict"],
                   cwd=skill_dir, check=True, capture_output=True)
    sidecar = md.with_suffix(md.suffix + ".layout.json")
    assert json.loads(sidecar.read_text())["mode"] == "strict"
    # Now --shake WITHOUT --mode: mode must remain strict.
    subprocess.run([py, "build.py", "--allow-composed", "--input", str(md), "--output",
                    str(tmp_path / "b.pptx"), "--shake"],
                   cwd=skill_dir, check=True, capture_output=True)
    assert json.loads(sidecar.read_text())["mode"] == "strict"


def _deepdream_py():
    py = str(Path.home() / "miniconda3/envs/deepdream/bin/python")
    if not Path(py).exists():
        py = sys.executable
    return py


def test_theme_frozen_and_persists_across_rerender(tmp_path):
    import subprocess, json
    skill_dir = Path(__file__).resolve().parents[1]
    md = tmp_path / "deck.md"
    md.write_text("---\ntitle: T\n---\n\n# A\n\nsome text here\n", encoding="utf-8")
    py = _deepdream_py()
    sidecar = md.with_suffix(md.suffix + ".layout.json")
    # First build (expressive default) freezes a theme + non-null seed.
    subprocess.run([py, "build.py", "--allow-composed", "--input", str(md), "--output",
                    str(tmp_path / "a.pptx")], cwd=skill_dir, check=True,
                   capture_output=True)
    d1 = json.loads(sidecar.read_text())
    assert d1["mode"] == "expressive"
    assert d1["theme"] is not None
    assert d1["shake_seed"]  # non-null/non-empty now
    t1 = d1["theme"]
    # Plain re-render (no --shake) must keep the SAME frozen theme.
    subprocess.run([py, "build.py", "--allow-composed", "--input", str(md), "--output",
                    str(tmp_path / "b.pptx")], cwd=skill_dir, check=True,
                   capture_output=True)
    d2 = json.loads(sidecar.read_text())
    assert d2["theme"] == t1


def test_shake_generates_new_seed(tmp_path):
    import subprocess, json
    skill_dir = Path(__file__).resolve().parents[1]
    md = tmp_path / "deck.md"
    md.write_text("---\ntitle: T\n---\n\n# A\n\nsome text here\n", encoding="utf-8")
    py = _deepdream_py()
    sidecar = md.with_suffix(md.suffix + ".layout.json")
    subprocess.run([py, "build.py", "--allow-composed", "--input", str(md), "--output",
                    str(tmp_path / "a.pptx")], cwd=skill_dir, check=True,
                   capture_output=True)
    seed1 = json.loads(sidecar.read_text())["shake_seed"]
    subprocess.run([py, "build.py", "--allow-composed", "--input", str(md), "--output",
                    str(tmp_path / "b.pptx"), "--shake"], cwd=skill_dir,
                   check=True, capture_output=True)
    seed2 = json.loads(sidecar.read_text())["shake_seed"]
    assert seed1 != seed2  # --shake rerolls the seed
