import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PROMPT = (ROOT / "plan_prompt.md").read_text(encoding="utf-8")


def test_has_design_principles_section():
    assert "## Design principles" in PROMPT


def test_documents_both_modes():
    assert "expressive" in PROMPT.lower()
    assert "strict" in PROMPT.lower()


def test_lists_anti_patterns():
    low = PROMPT.lower()
    assert "anti-pattern" in low
    assert "centered body text" in low or "center body text" in low
    assert "text-only" in low


def test_documents_supplementary_palette_in_sandbox():
    assert "THEME_RGBS" in PROMPT
    assert "ON_DARK" in PROMPT


def test_plan_prompt_still_assembles():
    from plan import assemble_plan_prompt
    out = assemble_plan_prompt(
        md_text="# A\n\ntext\n",
        slide_records=[{"slide_id": "h1-a", "content_hash": "x",
                        "h1": "A", "h2": None, "chunk_html": "<h1>A</h1>"}],
    )
    assert "## Design principles" in out
    assert "h1-a" in out
