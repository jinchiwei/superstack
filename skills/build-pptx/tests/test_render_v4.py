"""End-to-end tests for v4 plan→render."""

import sys
import json
import subprocess
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parents[1]
FIXTURE = SKILL_DIR / "tests" / "fixture.md"
BUILD_PY = SKILL_DIR / "build.py"


def test_plan_only_writes_sidecar_no_pptx(tmp_path):
    """--plan-only emits the JSON sidecar but no pptx."""
    md = tmp_path / "deck.md"
    md.write_text(FIXTURE.read_text())
    out = tmp_path / "out.pptx"
    proc = subprocess.run(
        [sys.executable, str(BUILD_PY),
         "--input", str(md), "--output", str(out),
         "--plan-only"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    sidecar = md.with_suffix(md.suffix + ".layout.json")
    assert sidecar.exists()
    plan = json.loads(sidecar.read_text())
    assert plan["version"] == 1
    assert isinstance(plan["slides"], list)
    assert len(plan["slides"]) > 0
    # pptx not written
    assert not out.exists()


def test_default_plan_renders_pptx(tmp_path):
    """Without --no-plan, the v4 path renders pptx using the inferred plan."""
    md = tmp_path / "deck.md"
    md.write_text(FIXTURE.read_text())
    out = tmp_path / "out.pptx"
    proc = subprocess.run(
        [sys.executable, str(BUILD_PY),
         "--input", str(md), "--output", str(out)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert out.exists()
    assert out.stat().st_size > 5000


def test_no_plan_falls_back_to_legacy(tmp_path):
    """--no-plan skips the sidecar and uses the v3 path."""
    md = tmp_path / "deck.md"
    md.write_text(FIXTURE.read_text())
    out = tmp_path / "out.pptx"
    proc = subprocess.run(
        [sys.executable, str(BUILD_PY),
         "--input", str(md), "--output", str(out),
         "--no-plan"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert out.exists()
    sidecar = md.with_suffix(md.suffix + ".layout.json")
    assert not sidecar.exists()  # no sidecar in legacy mode


def test_shake_regenerates_sidecar(tmp_path):
    """--shake replaces an existing sidecar."""
    md = tmp_path / "deck.md"
    md.write_text(FIXTURE.read_text())
    sidecar = md.with_suffix(md.suffix + ".layout.json")
    # Plant a stale sidecar
    sidecar.write_text('{"version": 1, "deck_md_hash": "stale", "shake_seed": null, "slides": []}')
    out = tmp_path / "out.pptx"
    proc = subprocess.run(
        [sys.executable, str(BUILD_PY),
         "--input", str(md), "--output", str(out),
         "--shake"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    plan = json.loads(sidecar.read_text())
    assert plan["deck_md_hash"] != "stale"
    assert len(plan["slides"]) > 0


def test_render_is_deterministic(tmp_path):
    """Same plan → same pptx bytes (modulo timestamp metadata in pptx)."""
    md = tmp_path / "deck.md"
    md.write_text(FIXTURE.read_text())
    out1 = tmp_path / "out1.pptx"
    out2 = tmp_path / "out2.pptx"
    cmd_base = [sys.executable, str(BUILD_PY), "--input", str(md)]
    for out in (out1, out2):
        proc = subprocess.run(
            cmd_base + ["--output", str(out)],
            capture_output=True, text=True,
        )
        assert proc.returncode == 0, proc.stderr
    # Bytes won't be EXACTLY identical because pptx embeds a timestamp.
    # Instead, assert slide count + slide titles are the same.
    from pptx import Presentation
    p1 = Presentation(str(out1))
    p2 = Presentation(str(out2))
    assert len(p1.slides) == len(p2.slides)
    titles1 = []
    titles2 = []
    for s in p1.slides:
        for shp in s.shapes:
            if shp.has_text_frame:
                t = shp.text_frame.text.strip()
                if t:
                    titles1.append(t[:50]); break
    for s in p2.slides:
        for shp in s.shapes:
            if shp.has_text_frame:
                t = shp.text_frame.text.strip()
                if t:
                    titles2.append(t[:50]); break
    assert titles1 == titles2
