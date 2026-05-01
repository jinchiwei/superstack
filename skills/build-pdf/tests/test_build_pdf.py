"""Build-PDF: end-to-end smoke test against fixture markdown."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parents[1]
FIXTURE = SKILL_DIR / "tests" / "fixture.md"
BUILD_PY = SKILL_DIR / "build.py"


def _render(out_path: Path, *extra_args: str) -> None:
    cmd = [sys.executable, str(BUILD_PY),
           "--input", str(FIXTURE),
           "--output", str(out_path),
           *extra_args]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode == 0, f"build.py failed:\nSTDERR: {proc.stderr}\nSTDOUT: {proc.stdout}"


def test_renders_pdf_to_output_path(tmp_path):
    out = tmp_path / "out.pdf"
    _render(out)
    assert out.is_file()
    assert out.stat().st_size > 1000  # not an empty/tiny PDF


def test_pdf_starts_with_pdf_magic_bytes(tmp_path):
    """Output is a real PDF (starts with %PDF-)."""
    out = tmp_path / "out.pdf"
    _render(out)
    head = out.read_bytes()[:5]
    assert head == b"%PDF-"


def test_pdf_contains_expected_text(tmp_path):
    """Use pypdf to verify rendered content."""
    out = tmp_path / "out.pdf"
    _render(out)
    try:
        from pypdf import PdfReader
    except ImportError:
        pytest.skip("pypdf not installed")
    reader = PdfReader(str(out))
    full_text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "Build-PDF Smoke Test" in full_text  # title
    assert "Section One" in full_text
    assert "Section Two" in full_text


def test_pdf_has_bookmarks(tmp_path):
    """Sections should appear as PDF outline (bookmarks) entries."""
    out = tmp_path / "out.pdf"
    _render(out)
    try:
        from pypdf import PdfReader
    except ImportError:
        pytest.skip("pypdf not installed")
    reader = PdfReader(str(out))
    outline = reader.outline or []
    titles = []
    def _flatten(items):
        for it in items:
            if isinstance(it, list):
                _flatten(it)
            elif hasattr(it, "title"):
                titles.append(it.title)
    _flatten(outline)
    assert any("Section One" in t for t in titles)
    assert any("Section Two" in t for t in titles)


def test_no_cover_flag_suppresses_cover(tmp_path):
    """With --no-cover, the title page is omitted (resulting PDF is shorter)."""
    out_with = tmp_path / "with_cover.pdf"
    out_without = tmp_path / "no_cover.pdf"
    _render(out_with)
    _render(out_without, "--no-cover")
    try:
        from pypdf import PdfReader
    except ImportError:
        pytest.skip("pypdf not installed")
    pages_with = len(PdfReader(str(out_with)).pages)
    pages_without = len(PdfReader(str(out_without)).pages)
    assert pages_without == pages_with - 1


def test_watermark_flag_renders_text(tmp_path):
    """--watermark text should appear in the rendered PDF."""
    out = tmp_path / "wm.pdf"
    _render(out, "--watermark", "DRAFT")
    try:
        from pypdf import PdfReader
    except ImportError:
        pytest.skip("pypdf not installed")
    reader = PdfReader(str(out))
    full_text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "DRAFT" in full_text
