"""Markdown loader: frontmatter parsing + HTML conversion with smartypants."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import md_loader

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "sample.md"


def test_load_returns_meta_and_body():
    result = md_loader.load_markdown(FIXTURE)
    assert "meta" in result
    assert "body_html" in result


def test_meta_extracts_frontmatter_fields():
    result = md_loader.load_markdown(FIXTURE)
    meta = result["meta"]
    assert meta["title"] == "Sample Document"
    assert meta["eyebrow"] == "TEST FIXTURE"
    assert meta["subtitle"] == "for the markdown loader test"
    assert meta["name"] == "Jinchi Wei"
    assert meta["org"] == "UCSF"
    assert meta["date"] == "2026-05-01"


def test_body_html_renders_h1_and_h2():
    result = md_loader.load_markdown(FIXTURE)
    html = result["body_html"]
    assert "<h1>Section One</h1>" in html
    assert "<h2>Subsection</h2>" in html


def test_body_html_renders_bullets():
    html = md_loader.load_markdown(FIXTURE)["body_html"]
    assert "<ul>" in html
    assert "<li>First bullet</li>" in html


def test_body_html_renders_code_blocks_and_inline():
    html = md_loader.load_markdown(FIXTURE)["body_html"]
    assert "<pre>" in html
    assert "<code>" in html
    # 'inline code' was wrapped in backticks → should be in <code>
    assert "<code>inline code</code>" in html


def test_smartypants_converts_em_dash():
    """Three hyphens → em dash (smartypants ON)."""
    html = md_loader.load_markdown(FIXTURE)["body_html"]
    assert "—" in html  # em dash
    assert "Triple-dash --- becomes" not in html  # raw form should be gone


def test_smartypants_converts_curly_quotes():
    """Straight double quotes → typographic curly quotes."""
    html = md_loader.load_markdown(FIXTURE)["body_html"]
    # U+201C left curly + U+201D right curly
    assert "“should be curly”" in html


def test_load_handles_missing_frontmatter(tmp_path):
    """Markdown without frontmatter still loads; meta is empty dict."""
    f = tmp_path / "plain.md"
    f.write_text("# Just a heading\n\nBody.\n")
    result = md_loader.load_markdown(f)
    assert result["meta"] == {}
    assert "<h1>Just a heading</h1>" in result["body_html"]


def test_extract_h1_fallback_when_no_title_in_meta(tmp_path):
    """If no frontmatter `title`, extract_title() returns first H1 from body."""
    f = tmp_path / "h1only.md"
    f.write_text("# Fallback Title\n\nbody\n")
    result = md_loader.load_markdown(f)
    assert md_loader.extract_title(result) == "Fallback Title"


def test_extract_title_uses_frontmatter_when_present():
    result = md_loader.load_markdown(FIXTURE)
    assert md_loader.extract_title(result) == "Sample Document"
