"""Branding constants are present and correct."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import branding


def test_canonical_priority_colors():
    assert branding.TURQUOISE == "#40E0D0"
    assert branding.DEEPPINK == "#FF1493"
    assert branding.AMBER == "#F0C840"
    assert branding.BLUEVIOLET == "#8A2BE2"


def test_neutrals():
    assert branding.INK == "#14141C"
    assert branding.WHITE == "#FFFFFF"
    assert branding.PAPER == "#FAFAFC"
    assert branding.MUTED == "#555560"
    assert branding.DIM == "#888888"
    assert branding.RULE == "#DDDDDD"


def test_dark_bg():
    assert branding.DARK_BG == "#0E1A35"


def test_semantic_role_aliases_match():
    """Semantic aliases (HEADING_1, METRIC, etc.) must point to canonical colors."""
    assert branding.HEADING_1 == branding.TURQUOISE
    assert branding.HEADING_2 == branding.DEEPPINK
    assert branding.HEADING_3 == branding.INK
    assert branding.NAME_COLOR == branding.TURQUOISE
    assert branding.ORG_COLOR == branding.DEEPPINK
    assert branding.METRIC_COLOR == branding.BLUEVIOLET
    assert branding.EYEBROW_LIGHT == branding.MUTED
    assert branding.EYEBROW_DARK == branding.TURQUOISE


def test_section_divider_cycle():
    """PPTX section dividers cycle through canonical priority order."""
    assert branding.SECTION_DIVIDER_CYCLE == [
        branding.TURQUOISE,
        branding.DEEPPINK,
        branding.AMBER,
        branding.BLUEVIOLET,
    ]


def test_font_chains_strings():
    """Font-family CSS strings include Geist first then Helvetica fallback."""
    assert branding.SANS_FONT_STACK.startswith("'Geist',")
    assert "Helvetica" in branding.SANS_FONT_STACK
    assert "Liberation Sans" in branding.SANS_FONT_STACK
    assert branding.MONO_FONT_STACK.startswith("'Geist Mono',")
    assert "Liberation Mono" in branding.MONO_FONT_STACK
    # CJK fallback present in sans chain
    assert "Hiragino" in branding.SANS_FONT_STACK or "Noto" in branding.SANS_FONT_STACK


def test_pick_section_color_cycles():
    """pick_section_color(n) cycles through 4 colors."""
    assert branding.pick_section_color(0) == branding.TURQUOISE
    assert branding.pick_section_color(1) == branding.DEEPPINK
    assert branding.pick_section_color(2) == branding.AMBER
    assert branding.pick_section_color(3) == branding.BLUEVIOLET
    assert branding.pick_section_color(4) == branding.TURQUOISE  # wraps
    assert branding.pick_section_color(7) == branding.BLUEVIOLET  # wraps


def test_section_text_color_for_amber_is_dark():
    """Amber needs dark text for contrast; others use white."""
    assert branding.section_text_color(branding.AMBER) == branding.INK
    assert branding.section_text_color(branding.TURQUOISE) == branding.WHITE
    assert branding.section_text_color(branding.DEEPPINK) == branding.WHITE
    assert branding.section_text_color(branding.BLUEVIOLET) == branding.WHITE


def test_plain_font_names_for_pptx_docx():
    """python-pptx and python-docx want a single font name, not a CSS chain."""
    assert branding.SANS_FONT == "Geist"
    assert branding.MONO_FONT == "Geist Mono"


def test_match_section_color_methods():
    assert branding.match_section_color("Methods") == branding.DEEPPINK
    assert branding.match_section_color("Methodology") == branding.DEEPPINK
    assert branding.match_section_color("approach and design") == branding.DEEPPINK


def test_match_section_color_results():
    assert branding.match_section_color("Results") == branding.AMBER
    assert branding.match_section_color("Findings") == branding.AMBER
    assert branding.match_section_color("Headline Performance") == branding.AMBER


def test_match_section_color_big_picture():
    assert branding.match_section_color("Background") == branding.TURQUOISE
    assert branding.match_section_color("Motivation") == branding.TURQUOISE
    assert branding.match_section_color("Conclusions") == branding.TURQUOISE
    assert branding.match_section_color("Next Steps") == branding.TURQUOISE


def test_match_section_color_validation():
    assert branding.match_section_color("Validation") == branding.BLUEVIOLET
    assert branding.match_section_color("Limitations") == branding.BLUEVIOLET
    assert branding.match_section_color("External Replication") == branding.BLUEVIOLET
    assert branding.match_section_color("Discussion") == branding.BLUEVIOLET


def test_match_section_color_unknown_falls_back_to_turquoise():
    assert branding.match_section_color("Random Title") == branding.TURQUOISE
    assert branding.match_section_color("") == branding.TURQUOISE


def test_match_section_color_case_insensitive():
    assert branding.match_section_color("METHODS") == branding.DEEPPINK
    assert branding.match_section_color("results") == branding.AMBER
