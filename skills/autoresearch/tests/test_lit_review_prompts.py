"""Smoke tests for the lit-review prompt files.

These don't validate LLM output (no LLM is invoked) — they only check the
prompt files exist and reference the JSON keys the SKILL.md flow expects.
A regression here means a refactor to the prompt accidentally dropped a
documented contract field.
"""

from __future__ import annotations

from pathlib import Path

PROMPTS = Path(__file__).resolve().parent.parent / "prompts"


def test_classify_prompt_exists_and_documents_contract():
    p = PROMPTS / "lit-review-classify.md"
    assert p.is_file(), f"missing: {p}"
    text = p.read_text()
    # Skip path
    assert "skip" in text and "reason" in text, "skip-path keys missing"
    # Proceed path
    for key in ("queries", "sources", "focus"):
        assert key in text, f"proceed-path key {key!r} missing from prompt"
    # Source whitelist
    for src in ("pubmed", "arxiv", "semanticscholar"):
        assert src in text, f"source {src!r} not mentioned"
    # Permissive default rule must remain documented
    assert "Permissive default" in text, "permissive default rule lost"


def test_synthesize_prompt_exists_and_documents_contract():
    p = PROMPTS / "lit-review-synthesize.md"
    assert p.is_file(), f"missing: {p}"
    text = p.read_text()
    for key in (
        "prior_work_summary",
        "dominant_approaches",
        "gaps",
        "novelty_argument",
        "top_relevant",
        "axis_implications",
    ):
        assert key in text, f"output key {key!r} missing from prompt"
    # Honesty about novelty is load-bearing for the value of the whole feature.
    assert "Be honest about novelty" in text


def test_axis_enumeration_accepts_lit_review_summary():
    p = PROMPTS / "axis-enumeration.md"
    text = p.read_text()
    assert "lit_review_summary" in text, "axis-enumeration prompt should accept lit context"
