"""Tests for plan.py — slide-ID derivation + Plan JSON round-trip."""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Wire the import path the same way build.py does
SKILL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_DIR))

from plan import (
    _slug,
    derive_slide_id,
    derive_slide_ids_from_chunks,
    Plan,
    SlideEntry,
    hash_text,
)


def test_slug_basic():
    assert _slug("Executive Summary") == "executive-summary"
    assert _slug("Methodology overview") == "methodology-overview"
    assert _slug("Part I — Headline · Site-mixed") == "part-i-headline-site-mixed"
    assert _slug("") == ""
    assert _slug("   leading and trailing   ") == "leading-and-trailing"
    # Strip non-alphanumeric edges
    assert _slug("--foo-bar--") == "foo-bar"


def test_derive_slide_id_h1_only():
    assert derive_slide_id(h1="Executive summary", h2=None,
                           auto_index=0) == "h1-executive-summary"


def test_derive_slide_id_h1_h2():
    assert derive_slide_id(h1="Methods", h2="Cohorts",
                           auto_index=0) == "h1-methods/h2-cohorts"


def test_derive_slide_id_h2_only():
    assert derive_slide_id(h1=None, h2="Headline numbers",
                           auto_index=0) == "h2-headline-numbers"


def test_derive_slide_id_neither_uses_auto():
    assert derive_slide_id(h1=None, h2=None, auto_index=3) == "auto-3"


def test_derive_slide_ids_from_chunks_walks_h1_h2():
    chunks = [
        "<h1>Executive summary</h1><p>This is the lede.</p>",
        "<h1>Methods</h1>",
        "<h2>Cohorts</h2><p>UCSF and PNOC.</p>",
        "<h2>Targets</h2><p>histone, TP53, ...</p>",
        "<h1>Results</h1>",
        "<h2>Headline</h2><p>AUC 0.91.</p>",
    ]
    ids = derive_slide_ids_from_chunks(chunks)
    assert ids == [
        "h1-executive-summary",
        "h1-methods",
        "h1-methods/h2-cohorts",
        "h1-methods/h2-targets",
        "h1-results",
        "h1-results/h2-headline",
    ]


def test_derive_slide_ids_disambiguates_duplicates():
    chunks = [
        "<h2>Background</h2>",
        "<h2>Background</h2>",
        "<h2>Background</h2>",
    ]
    ids = derive_slide_ids_from_chunks(chunks)
    assert ids[0] == "h2-background"
    assert ids[1] == "h2-background-2"
    assert ids[2] == "h2-background-3"


def test_plan_round_trip():
    p = Plan(
        version=1,
        deck_md_hash="abc123",
        shake_seed=None,
        slides=[
            SlideEntry(slide_id="h1-exec",
                       kind="content-text",
                       params={"title": "Executive Summary",
                               "lede": "Headline.",
                               "body": []},
                       content_hash="def456"),
            SlideEntry(slide_id="h1-methods/h2-cohorts",
                       kind="cards-grid",
                       params={"title": "Cohorts", "cards": [
                           {"label": "UCSF", "body": "n=100"},
                           {"label": "PNOC", "body": "n=65"},
                       ]},
                       content_hash="789abc"),
        ],
    )
    s = p.to_json()
    # Parses cleanly as JSON
    parsed = json.loads(s)
    assert parsed["version"] == 1
    assert len(parsed["slides"]) == 2

    # Round trip
    p2 = Plan.from_json(s)
    assert p2.version == p.version
    assert p2.deck_md_hash == p.deck_md_hash
    assert len(p2.slides) == 2
    assert p2.slides[0].slide_id == "h1-exec"
    assert p2.slides[1].kind == "cards-grid"
    assert p2.slides[1].params["cards"][0]["label"] == "UCSF"


def test_plan_from_json_tolerates_missing_optional_fields():
    """A minimal plan should parse without errors."""
    minimal = '{"version": 1, "slides": []}'
    p = Plan.from_json(minimal)
    assert p.version == 1
    assert p.deck_md_hash == ""
    assert p.shake_seed is None
    assert p.slides == []


def test_hash_text_is_stable():
    assert hash_text("hello") == hash_text("hello")
    assert hash_text("hello") != hash_text("hello!")
    # SHA256 always produces 64 hex chars
    assert len(hash_text("anything")) == 64


def test_assemble_plan_prompt_includes_catalog_and_chunks():
    """The assembled prompt should include the static catalog AND the per-deck slide input."""
    from plan import assemble_plan_prompt
    md = "# Hello\n\nworld"
    records = [
        {"slide_id": "h1-hello", "content_hash": "abc",
         "h1": "Hello", "h2": None,
         "chunk_html": "<h1>Hello</h1><p>world</p>"},
    ]
    prompt = assemble_plan_prompt(md_text=md, slide_records=records)
    # Catalog section is in the static template
    assert "cards-grid" in prompt
    assert "stat-callouts-right" in prompt
    # Per-slide input is appended
    assert "slide_id: h1-hello" in prompt
    assert "content_hash: abc" in prompt
    assert "<h1>Hello</h1>" in prompt
    # The closing instruction
    assert "Output the JSON" in prompt


def test_merge_with_existing_preserves_unchanged_entries():
    from plan import Plan, SlideEntry, merge_with_existing
    existing = Plan(deck_md_hash="old_deck",
                    slides=[SlideEntry(slide_id="h1-exec",
                                       kind="bg-flip",  # user-chosen layout
                                       params={"title": "Exec"},
                                       content_hash="contentA")])
    fresh = Plan(deck_md_hash="new_deck",
                 slides=[SlideEntry(slide_id="h1-exec",
                                    kind="content-text",  # default
                                    params={"title": "Exec"},
                                    content_hash="contentA")])
    merged = merge_with_existing(fresh, existing)
    # The bg-flip choice is preserved because content_hash matched
    assert merged.slides[0].kind == "bg-flip"
    # New deck_md_hash is taken from fresh
    assert merged.deck_md_hash == "new_deck"


def test_merge_with_existing_replaces_when_content_changed():
    from plan import Plan, SlideEntry, merge_with_existing
    existing = Plan(slides=[SlideEntry(slide_id="h1-exec",
                                       kind="bg-flip",
                                       params={},
                                       content_hash="contentA")])
    fresh = Plan(slides=[SlideEntry(slide_id="h1-exec",
                                    kind="content-text",
                                    params={},
                                    content_hash="contentB")])
    merged = merge_with_existing(fresh, existing)
    # content_hash differs → take fresh choice
    assert merged.slides[0].kind == "content-text"


def test_merge_with_existing_drops_removed_slides():
    from plan import Plan, SlideEntry, merge_with_existing
    existing = Plan(slides=[SlideEntry(slide_id="h1-exec", kind="content-text",
                                       params={}, content_hash="x"),
                            SlideEntry(slide_id="h1-removed", kind="content-text",
                                       params={}, content_hash="y")])
    fresh = Plan(slides=[SlideEntry(slide_id="h1-exec", kind="content-text",
                                    params={}, content_hash="x")])
    merged = merge_with_existing(fresh, existing)
    # h1-removed is gone
    assert len(merged.slides) == 1
    assert merged.slides[0].slide_id == "h1-exec"


def test_merge_with_existing_handles_no_existing():
    from plan import Plan, SlideEntry, merge_with_existing
    fresh = Plan(slides=[SlideEntry(slide_id="x", kind="content-text",
                                    params={}, content_hash="x")])
    merged = merge_with_existing(fresh, None)
    assert merged is fresh or merged.slides == fresh.slides


def test_build_slide_records_extracts_h1_h2():
    from plan import build_slide_records
    chunks = [
        "<h1>Methods</h1><p>intro</p>",
        "<h2>Cohorts</h2><p>UCSF</p>",
    ]
    ids = ["h1-methods", "h1-methods/h2-cohorts"]
    recs = build_slide_records(chunks=chunks, slide_ids=ids)
    assert len(recs) == 2
    assert recs[0]["h1"] == "Methods"
    assert recs[0]["h2"] is None
    assert recs[1]["h1"] == "Methods"  # carried over from previous slide
    assert recs[1]["h2"] == "Cohorts"
    # content_hash differs per chunk
    assert recs[0]["content_hash"] != recs[1]["content_hash"]
