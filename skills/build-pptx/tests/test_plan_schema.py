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
