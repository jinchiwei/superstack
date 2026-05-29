"""The bespoke-enforcement gate (cross-machine).

A real expressive render MUST abort (non-zero, no .pptx) unless every content
slide is handcrafted (`params._provenance == "agent"`) or the caller explicitly
opts into the agentless floor with --allow-composed. This is the mechanical
check that makes "always bespoke" enforceable; prose guidance was ignored.
"""

import json
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
BUILD_PY = SKILL_DIR / "build.py"

DECK = """---
title: "Gate"
name: "Jinchi Wei"
---
# Background
---
## A point
Body text.
- one
- two
"""


def _run(md, out, *extra):
    return subprocess.run(
        [sys.executable, str(BUILD_PY), "--input", str(md),
         "--output", str(out), *extra],
        capture_output=True, text=True,
    )


def _mk(tmp_path):
    md = tmp_path / "deck.md"
    md.write_text(DECK)
    return md, tmp_path / "out.pptx"


def test_fresh_expressive_render_aborts(tmp_path):
    md, out = _mk(tmp_path)
    p = _run(md, out)
    assert p.returncode != 0, "the gate must block a floor render"
    assert not out.exists(), "no .pptx may be written on a blocked render"
    assert "BESPOKE NOT SATISFIED" in p.stderr


def test_allow_composed_bypasses(tmp_path):
    md, out = _mk(tmp_path)
    p = _run(md, out, "--allow-composed")
    assert p.returncode == 0, p.stderr
    assert out.is_file()


def test_plan_only_is_exempt(tmp_path):
    """--plan-only is the scaffold step; it must never be blocked."""
    md, out = _mk(tmp_path)
    p = _run(md, out, "--plan-only", "--shake")
    assert p.returncode == 0, p.stderr
    assert not out.exists()  # plan-only writes no pptx


def test_agent_stamp_passes(tmp_path):
    """Handcrafting = stamping each content slide _provenance='agent'."""
    md, out = _mk(tmp_path)
    _run(md, out, "--plan-only", "--shake")  # scaffold (composer floor)
    side = md.with_suffix(md.suffix + ".layout.json")
    d = json.loads(side.read_text())
    for s in d["slides"]:
        if s["kind"] != "section-divider":
            s.setdefault("params", {})["_provenance"] = "agent"
    side.write_text(json.dumps(d))
    p = _run(md, out)  # no --allow-composed
    assert p.returncode == 0, p.stderr
    assert out.is_file()


def test_floor_sidecar_cannot_be_silently_rerendered(tmp_path):
    """The hole this closes: a floor sidecar from a prior run must STILL be
    blocked on a plain re-render (the composer stamp persists)."""
    md, out = _mk(tmp_path)
    _run(md, out, "--plan-only", "--shake")  # writes composer-stamped floor
    p = _run(md, out)  # plain re-render, no flag
    assert p.returncode != 0
    assert not out.exists()


def test_strict_mode_is_not_gated(tmp_path):
    """Strict mode is the deliberate named-layout revert path — not gated."""
    md, out = _mk(tmp_path)
    p = _run(md, out, "--mode", "strict")
    assert p.returncode == 0, p.stderr
    assert out.is_file()
