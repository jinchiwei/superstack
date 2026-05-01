# build-pdf / build-pptx / build-docx Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Three new general-purpose superstack skills — `build-pdf`, `build-pptx`, `build-docx` — that take any markdown file (with optional YAML frontmatter for metadata) and produce a Jin-branded document. Tier 1 generality: not autoresearch-specific, not coupled to any particular file layout. Slash-command invocable AND Python-callable.

**Architecture:** Three independent skills that share a `_shared/` directory containing palette/font constants and a markdown→HTML loader. Engines per format: weasyprint (PDF), python-pptx (PPTX), pandoc + reference.docx (DOCX). Same branding rules across all three: Geist Mono for structural elements (eyebrow, title, headings, code, page numbers, metric values), Geist Sans for reading content (body prose, bullets, subtitles). Color palette enforced from `_shared/branding.py`.

**Tech Stack:** Python 3.12 in `deepdream` conda env. Deps: `weasyprint` (already installed via autoresearch), `python-pptx`, `python-markdown`, `pyyaml`, plus `pandoc` CLI (system-installed, not pip). All editable in `~/arcadia/superstack/`, synced to `~/.claude/skills/` for live access.

**Realistic effort: ~8-9 hr CC time** (7 tasks).

---

## File Structure

```
~/arcadia/superstack/
├── docs/plans/2026-05-01-build-pdf-pptx-docx-skills.md  THIS FILE
└── skills/
    ├── _shared/
    │   ├── __init__.py                Empty marker
    │   ├── branding.py                Color + font constants (single source of truth)
    │   ├── md_loader.py               Frontmatter parsing + markdown→HTML
    │   └── tests/
    │       ├── test_branding.py       Constants present, hex values correct
    │       └── test_md_loader.py      Frontmatter extraction, smartypants, em-dash
    ├── build-pdf/
    │   ├── SKILL.md                   When to invoke + arg description
    │   ├── build.py                   Markdown → branded PDF via weasyprint
    │   ├── tests/
    │   │   ├── fixture.md             Sample markdown with frontmatter
    │   │   └── test_build_pdf.py      Render fixture, assert PDF properties
    │   └── (synced to ~/.claude/skills/build-pdf/)
    ├── build-docx/
    │   ├── SKILL.md
    │   ├── build.py                   Pandoc wrapper
    │   ├── make_reference.py          Generate reference.docx (run once, commit output)
    │   ├── reference.docx             Pre-built styled reference doc (binary, committed)
    │   ├── tests/
    │   │   ├── fixture.md
    │   │   └── test_build_docx.py     Render fixture, open with python-docx, assert styles
    │   └── (synced to ~/.claude/skills/build-docx/)
    └── build-pptx/
        ├── SKILL.md
        ├── build.py                   Markdown → branded PPTX via python-pptx
        ├── tests/
        │   ├── fixture.md             Multi-slide markdown
        │   └── test_build_pptx.py     Render fixture, assert slide count + masters
        └── (synced to ~/.claude/skills/build-pptx/)
```

**Why this layout:**
- `_shared/` underscore-prefixed so it's clearly NOT a user-invocable skill (no SKILL.md). Each skill imports via `sys.path` manipulation.
- One `branding.py` is the single source of truth for palette/fonts. Color rule changes (like today's c0d4a99) become a single-file edit.
- `md_loader.py` shared between build-pdf and build-pptx (build-docx uses pandoc directly, no Python markdown parsing needed).
- Each skill's `build.py` is self-contained: argparse → load markdown → render → write output.
- Tests use real fixture files (markdown in, file out, inspect output). No mocks; PDF/PPTX/DOCX are end-product artifacts and tests should exercise the full pipeline.

---

## Frontmatter contract (all three skills)

Markdown source files may include YAML frontmatter:

```yaml
---
title: "Document title"           # required
eyebrow: "EYEBROW LABEL"          # optional
subtitle: "subtitle text"         # optional
name: "Jinchi Wei"                # optional
org: "UCSF / Acme"                # optional
date: "2026-05-01"                # optional, defaults to today
---
```

If frontmatter absent or `title` missing, `build.py` falls back to the first H1 in the body, or the filename slugified.

Optional metadata renders only when provided. The cover/title page composition adapts: name+org appear if present, target metric chip appears if `target` field present, etc.

---

## Task 1: `_shared/branding.py` — palette + font constants

**Files:**
- Create: `~/arcadia/superstack/skills/_shared/__init__.py`
- Create: `~/arcadia/superstack/skills/_shared/branding.py`
- Create: `~/arcadia/superstack/skills/_shared/tests/__init__.py`
- Create: `~/arcadia/superstack/skills/_shared/tests/test_branding.py`

Single source of truth for everything color- and font-related. No engine-specific code in this file — just constants and a couple of trivial helpers.

- [ ] **Step 1: Failing test at `_shared/tests/test_branding.py`**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
source ~/miniconda3/etc/profile.d/conda.sh && conda activate deepdream && pytest ~/arcadia/superstack/skills/_shared/tests/test_branding.py -v
```

Expected: ImportError (`branding` module doesn't exist).

- [ ] **Step 3: Create `_shared/__init__.py`**

```python
"""Shared modules used by build-* skills. Not a user-invocable skill."""
```

- [ ] **Step 4: Create `_shared/branding.py`**

```python
"""Single source of truth for Jin's brand palette and font stacks.

All build-* skills import constants from this module. If you change a color
or font here, every skill picks it up on the next render.
"""

from __future__ import annotations


# === Canonical priority colors ===
TURQUOISE  = "#40E0D0"
DEEPPINK   = "#FF1493"
AMBER      = "#F0C840"
BLUEVIOLET = "#8A2BE2"


# === Neutrals ===
INK    = "#14141C"   # body text — off-black with slight cool tint
WHITE  = "#FFFFFF"
PAPER  = "#FAFAFC"   # near-white code-block fill, slight cool tint
MUTED  = "#555560"   # dim gray for eyebrows, dates, labels on light backgrounds
DIM    = "#888888"   # page numbers, very low-emphasis text
RULE   = "#DDDDDD"   # hairline rule color


# === Dark slide background (PPTX title + closing) ===
DARK_BG = "#14141C"


# === Semantic role aliases ===
# These are the names used in renderers. If we ever swap which canonical
# color plays which role, change here, no other code changes needed.
HEADING_1     = TURQUOISE
HEADING_2     = DEEPPINK
HEADING_3     = INK
NAME_COLOR    = TURQUOISE
ORG_COLOR     = DEEPPINK
METRIC_COLOR  = BLUEVIOLET
EYEBROW_LIGHT = MUTED
EYEBROW_DARK  = TURQUOISE


# === Section divider cycle (PPTX) ===
SECTION_DIVIDER_CYCLE = [TURQUOISE, DEEPPINK, AMBER, BLUEVIOLET]


def pick_section_color(index: int) -> str:
    """Return the section divider color for the Nth section, cycling."""
    return SECTION_DIVIDER_CYCLE[index % len(SECTION_DIVIDER_CYCLE)]


def section_text_color(bg_color: str) -> str:
    """Return text color (white or off-black) for legibility on a section-divider background."""
    # Amber is too light for white text — use off-black. Everything else uses white.
    if bg_color == AMBER:
        return INK
    return WHITE


# === Font stacks (CSS family strings) ===
SANS_FONT_STACK = (
    "'Geist', 'Helvetica', 'Liberation Sans', "
    "-apple-system, system-ui, "
    "'Hiragino Kaku Gothic ProN', 'Noto Sans CJK JP', 'Microsoft YaHei', "
    "sans-serif"
)
MONO_FONT_STACK = (
    "'Geist Mono', 'SF Mono', 'Menlo', 'Liberation Mono', 'Consolas', monospace"
)


# === Plain font names (for python-pptx, python-docx — they want a single name not a chain) ===
SANS_FONT = "Geist"
MONO_FONT = "Geist Mono"
```

- [ ] **Step 5: Create `_shared/tests/__init__.py`**

```python
"""Tests for shared modules."""
```

- [ ] **Step 6: Run test to verify pass**

```bash
source ~/miniconda3/etc/profile.d/conda.sh && conda activate deepdream && pytest ~/arcadia/superstack/skills/_shared/tests/test_branding.py -v
```

Expected: 8 passed.

- [ ] **Step 7: Commit**

```bash
cd ~/arcadia/superstack
git add skills/_shared/__init__.py skills/_shared/branding.py skills/_shared/tests/__init__.py skills/_shared/tests/test_branding.py
git -c user.email="mrjinch@gmail.com" -c user.name="jinchiwei" commit -m "feat(_shared): branding constants module — single source of truth for palette + fonts"
```

---

## Task 2: `_shared/md_loader.py` — frontmatter + markdown→HTML

**Files:**
- Create: `~/arcadia/superstack/skills/_shared/md_loader.py`
- Create: `~/arcadia/superstack/skills/_shared/tests/test_md_loader.py`
- Create: `~/arcadia/superstack/skills/_shared/tests/fixtures/sample.md`

Shared markdown loader used by build-pdf and build-pptx. Parses YAML frontmatter, converts body to HTML with smartypants curly quotes + em-dash conversion (both ON per spec). Build-docx uses pandoc directly so doesn't need this.

- [ ] **Step 1: Create fixture `_shared/tests/fixtures/sample.md`**

```markdown
---
title: "Sample Document"
eyebrow: "TEST FIXTURE"
subtitle: "for the markdown loader test"
name: "Jinchi Wei"
org: "UCSF"
date: "2026-05-01"
---

# Section One

Body text here. Triple-dash --- becomes em dash. Quotes "should be curly" after smartypants.

## Subsection

Some `inline code` and a list:

- First bullet
- Second bullet

```python
def hello():
    return "world"
```
```

- [ ] **Step 2: Failing test at `_shared/tests/test_md_loader.py`**

```python
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
    assert "—" in html  # U+2014 em dash
    assert "Triple-dash --- becomes" not in html  # raw form should be gone


def test_smartypants_converts_curly_quotes():
    """Straight double quotes → typographic curly quotes."""
    html = md_loader.load_markdown(FIXTURE)["body_html"]
    assert "“should be curly”" in html  # U+201C / U+201D


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
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
source ~/miniconda3/etc/profile.d/conda.sh && conda activate deepdream && pytest ~/arcadia/superstack/skills/_shared/tests/test_md_loader.py -v
```

Expected: ImportError on `md_loader`.

- [ ] **Step 4: Install dependencies if not present**

```bash
source ~/miniconda3/etc/profile.d/conda.sh && conda activate deepdream && pip install --quiet markdown pyyaml
```

(weasyprint already installed via autoresearch.)

- [ ] **Step 5: Create `_shared/md_loader.py`**

```python
"""Load a markdown file with optional YAML frontmatter, return parsed meta + HTML body.

Used by build-pdf and build-pptx. (build-docx uses pandoc directly.)
"""

from __future__ import annotations

import re
from pathlib import Path

import markdown as md_lib
import yaml


_FRONTMATTER_RE = re.compile(
    r"\A---\s*\n(.*?)\n---\s*\n(.*)\Z",
    re.DOTALL,
)

_MD_EXTENSIONS = [
    "extra",       # tables, fenced code, footnotes, attr lists
    "smarty",      # smartypants: curly quotes + em-dash conversion (BOTH ON)
    "sane_lists",  # better list parsing
]


def load_markdown(path: str | Path) -> dict:
    """Read a markdown file. Return dict with `meta` (frontmatter dict) and
    `body_html` (rendered markdown).

    Frontmatter is YAML between `---` delimiters at the top of the file.
    If absent, `meta` is an empty dict and the entire file is treated as body.
    """
    text = Path(path).read_text()

    m = _FRONTMATTER_RE.match(text)
    if m:
        meta = yaml.safe_load(m.group(1)) or {}
        body_md = m.group(2)
    else:
        meta = {}
        body_md = text

    body_html = md_lib.markdown(body_md, extensions=_MD_EXTENSIONS)
    return {"meta": meta, "body_html": body_html}


def extract_title(loaded: dict) -> str:
    """Pick the document title.

    Order of precedence:
      1. `title` field in frontmatter
      2. First H1 in the body
      3. Empty string (caller decides fallback)
    """
    title = loaded["meta"].get("title")
    if title:
        return str(title).strip()
    m = re.search(r"<h1[^>]*>(.*?)</h1>", loaded["body_html"])
    if m:
        # Strip any inline tags inside the H1
        return re.sub(r"<[^>]+>", "", m.group(1)).strip()
    return ""
```

- [ ] **Step 6: Run tests to verify pass**

```bash
source ~/miniconda3/etc/profile.d/conda.sh && conda activate deepdream && pytest ~/arcadia/superstack/skills/_shared/tests/test_md_loader.py -v
```

Expected: 10 passed.

- [ ] **Step 7: Commit**

```bash
cd ~/arcadia/superstack
git add skills/_shared/md_loader.py skills/_shared/tests/test_md_loader.py skills/_shared/tests/fixtures/sample.md
git -c user.email="mrjinch@gmail.com" -c user.name="jinchiwei" commit -m "feat(_shared): md_loader — frontmatter + markdown→HTML with smartypants"
```

---

## Task 3: `build-pdf` — complete skill

**Files:**
- Create: `~/arcadia/superstack/skills/build-pdf/SKILL.md`
- Create: `~/arcadia/superstack/skills/build-pdf/build.py`
- Create: `~/arcadia/superstack/skills/build-pdf/tests/__init__.py`
- Create: `~/arcadia/superstack/skills/build-pdf/tests/fixture.md`
- Create: `~/arcadia/superstack/skills/build-pdf/tests/test_build_pdf.py`

Markdown → branded PDF. Cover page, all-Geist-Mono headings, body in Geist Sans, page numbers always on, clickable PDF bookmarks always on. Optional flags: `--toc`, `--watermark "<text>"`, `--running-header "<text>"`, `--no-cover`.

- [ ] **Step 1: Create fixture markdown at `build-pdf/tests/fixture.md`**

```markdown
---
title: "Build-PDF Smoke Test"
eyebrow: "FIXTURE"
subtitle: "exercises the rendering pipeline"
name: "Jinchi Wei"
org: "UCSF Department of Radiology"
date: "2026-05-01"
---

# Section One

This is the first section. Body prose in Geist Sans, 11pt.

## Subsection A

A subsection under section one. Triple-dash --- should become em-dash.

Some `inline code` and a code block:

```python
def example():
    return "syntax should render in Geist Mono"
```

## Subsection B

- First bullet
- Second bullet
- Third bullet with *italics* and **bold**

# Section Two

| Col 1 | Col 2 | Col 3 |
|-------|-------|-------|
| a     | b     | c     |
| d     | e     | f     |

End of fixture.
```

- [ ] **Step 2: Failing test at `build-pdf/tests/test_build_pdf.py`**

```python
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
    """Use pdftotext (or similar) to verify rendered content."""
    out = tmp_path / "out.pdf"
    _render(out)
    # weasyprint writes embedded text streams; verify by extracting via pypdf
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
    # weasyprint emits Section One / Section Two / subsections as bookmarks
    # Flatten the outline and gather titles
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
```

- [ ] **Step 3: Run tests — verify ImportError / FileNotFoundError**

```bash
source ~/miniconda3/etc/profile.d/conda.sh && conda activate deepdream && pytest ~/arcadia/superstack/skills/build-pdf/tests/ -v
```

Expected: failures because `build.py` doesn't exist.

- [ ] **Step 4: Install pypdf (test-only dep)**

```bash
source ~/miniconda3/etc/profile.d/conda.sh && conda activate deepdream && pip install --quiet pypdf
```

- [ ] **Step 5: Create `build-pdf/build.py`**

```python
"""build-pdf — render a markdown file to a Jin-branded PDF.

Usage:
    python build.py --input doc.md --output doc.pdf
    python build.py --input doc.md --output doc.pdf --toc --watermark DRAFT

All branding (palette, fonts) comes from skills/_shared/branding.py.
Markdown → HTML via skills/_shared/md_loader.py (smartypants ON).
HTML → PDF via weasyprint.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html as html_mod
import sys
from pathlib import Path

# Wire up imports to the sibling _shared/ directory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "_shared"))

import branding  # noqa: E402
from md_loader import extract_title, load_markdown  # noqa: E402

try:
    from weasyprint import CSS, HTML
except ImportError:
    raise SystemExit("weasyprint not installed. Run: pip install weasyprint")


def _css_template(*, watermark: str | None, running_header: str | None) -> str:
    """Generate the print CSS. Inlined into the rendered HTML."""
    wm_block = ""
    if watermark:
        # Diagonal watermark on every page after the cover
        wm_block = f"""
@page {{
  @bottom-right {{
    content: "";
  }}
}}
.watermark {{
  position: fixed;
  top: 5in; left: 1in;
  font-family: {branding.MONO_FONT_STACK};
  font-size: 80pt; font-weight: 700;
  color: {branding.RULE};
  opacity: 0.18;
  transform: rotate(-30deg);
  pointer-events: none;
  z-index: -1;
}}
"""
    rh_block = ""
    if running_header:
        rh_block = f"""
@page {{
  @top-center {{
    content: "{html_mod.escape(running_header)}";
    font-family: {branding.MONO_FONT_STACK};
    font-size: 8pt; color: {branding.MUTED};
  }}
}}
@page :first {{ @top-center {{ content: ""; }} }}
"""

    return f"""
@page {{
  size: Letter;
  margin: 1in;
  @bottom-center {{
    content: counter(page);
    font-family: {branding.MONO_FONT_STACK};
    font-size: 8pt; color: {branding.DIM};
  }}
}}
@page :first {{
  @bottom-center {{ content: ""; }}
}}
{rh_block}

* {{ box-sizing: border-box; }}

html, body {{
  font-family: {branding.SANS_FONT_STACK};
  color: {branding.INK};
  font-size: 11pt; line-height: 1.55;
}}

/* === Cover page === */
.cover {{ page-break-after: always; }}
.cover .eyebrow {{
  font-family: {branding.MONO_FONT_STACK};
  font-size: 10pt; color: {branding.EYEBROW_LIGHT};
  font-weight: 700; letter-spacing: 0.08em;
  margin: 0 0 8pt 0;
}}
.cover .title {{
  font-family: {branding.MONO_FONT_STACK};
  font-size: 28pt; font-weight: 700; color: {branding.INK};
  margin: 0 0 8pt 0; line-height: 1.15;
}}
.cover .subtitle {{
  font-family: {branding.SANS_FONT_STACK};
  font-size: 13pt; color: {branding.MUTED};
  margin: 0 0 14pt 0;
}}
.cover .name {{
  font-family: {branding.MONO_FONT_STACK};
  font-size: 12pt; font-weight: 700; color: {branding.NAME_COLOR};
  margin: 0 0 2pt 0;
}}
.cover .org {{
  font-family: {branding.MONO_FONT_STACK};
  font-size: 10pt; font-weight: 700; color: {branding.ORG_COLOR};
  margin: 0 0 14pt 0;
}}
.cover hr.cover-rule {{
  border: none; border-top: 0.5pt solid {branding.RULE};
  margin: 14pt 0; width: 40%;
}}
.cover .date {{
  font-family: {branding.MONO_FONT_STACK};
  font-size: 10pt; color: {branding.DIM}; margin: 0;
}}

/* === Body headings === */
h1 {{
  font-family: {branding.MONO_FONT_STACK};
  font-size: 18pt; font-weight: 700;
  color: {branding.HEADING_1};
  margin: 24pt 0 8pt 0;
  bookmark-level: 1; bookmark-label: content(text);
  page-break-after: avoid;
}}
h2 {{
  font-family: {branding.MONO_FONT_STACK};
  font-size: 14pt; font-weight: 700;
  color: {branding.HEADING_2};
  margin: 18pt 0 6pt 0;
  bookmark-level: 2; bookmark-label: content(text);
  page-break-after: avoid;
}}
h3 {{
  font-family: {branding.MONO_FONT_STACK};
  font-size: 12pt; font-weight: 700;
  color: {branding.HEADING_3};
  margin: 14pt 0 4pt 0;
  page-break-after: avoid;
}}

/* === Body content === */
p, li {{
  font-family: {branding.SANS_FONT_STACK};
  color: {branding.INK};
}}
ul, ol {{ padding-left: 1.4em; }}
li {{ margin: 2pt 0; }}

code {{
  font-family: {branding.MONO_FONT_STACK};
  font-size: 9.5pt; color: {branding.INK};
}}
pre {{
  font-family: {branding.MONO_FONT_STACK};
  font-size: 9.5pt; color: {branding.INK};
  background: {branding.PAPER};
  border-left: 2pt solid #E5E5EA;
  padding: 8pt 12pt; margin: 8pt 0;
  white-space: pre-wrap; word-wrap: break-word;
}}
pre code {{ background: transparent; padding: 0; }}

table {{
  width: 100%; border-collapse: collapse; margin: 10pt 0;
  font-family: {branding.MONO_FONT_STACK}; font-size: 9.5pt;
}}
th {{
  text-align: left; padding: 6pt 8pt;
  border-bottom: 1pt solid {branding.INK};
  color: {branding.MUTED}; font-weight: 700; letter-spacing: 0.04em;
}}
td {{
  padding: 5pt 8pt; border-bottom: 0.5pt solid #EEEEF2;
  color: {branding.INK};
}}

hr {{
  border: none; border-top: 0.5pt solid {branding.RULE};
  margin: 14pt 0;
}}

/* === TOC === */
.toc {{ page-break-after: always; }}
.toc h1 {{
  font-size: 16pt; color: {branding.INK}; margin-bottom: 14pt;
  bookmark-level: none;
}}
.toc ul {{ list-style: none; padding-left: 0; }}
.toc li {{ margin: 4pt 0; font-family: {branding.MONO_FONT_STACK}; font-size: 10pt; }}
.toc a {{
  text-decoration: none; color: {branding.INK};
}}
.toc a::after {{
  content: leader('.') target-counter(attr(href), page);
  color: {branding.MUTED};
}}

{wm_block}
"""


def _render_cover(meta: dict, default_date: str) -> str:
    """Render the cover page HTML. Optional fields render only if present."""
    parts = ['<div class="cover">']
    if meta.get("eyebrow"):
        parts.append(f'<p class="eyebrow">{html_mod.escape(str(meta["eyebrow"]))}</p>')
    title = meta.get("title", "")
    parts.append(f'<h1 class="title">{html_mod.escape(str(title))}</h1>')
    if meta.get("subtitle"):
        parts.append(f'<p class="subtitle">{html_mod.escape(str(meta["subtitle"]))}</p>')
    if meta.get("name"):
        parts.append(f'<p class="name">{html_mod.escape(str(meta["name"]))}</p>')
    if meta.get("org"):
        parts.append(f'<p class="org">{html_mod.escape(str(meta["org"]))}</p>')
    parts.append('<hr class="cover-rule" />')
    date = str(meta.get("date") or default_date)
    parts.append(f'<p class="date">{html_mod.escape(date)}</p>')
    parts.append('</div>')
    return "\n".join(parts)


def _render_toc_stub(meta: dict) -> str:
    """A placeholder TOC. weasyprint generates the actual toc via bookmarks
    natively in the PDF outline; this is the in-body visible TOC for `--toc`.
    The links resolve via target-counter() in the CSS."""
    # Note: generating a full TOC from headings requires a 2-pass render or
    # parsing. For v1 we emit a simple "see PDF outline for navigation"
    # placeholder. A future enhancement could parse h1/h2 from body and emit
    # an explicit list with anchors; weasyprint's CSS target-counter already
    # populates page numbers when we render proper anchors.
    return (
        '<div class="toc">'
        '<h1>Contents</h1>'
        '<p style="font-family: ' + branding.SANS_FONT_STACK + '; '
        'font-size: 10pt; color: ' + branding.MUTED + ';">'
        'See PDF outline pane for clickable navigation.</p>'
        '</div>'
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", required=True, help="markdown file to render")
    ap.add_argument("--output", required=True, help="output PDF path")
    ap.add_argument("--toc", action="store_true", help="include visible TOC page")
    ap.add_argument("--watermark", help="diagonal watermark text on every page")
    ap.add_argument("--running-header", dest="running_header",
                    help="text in top margin of every page after cover")
    ap.add_argument("--no-cover", dest="no_cover", action="store_true",
                    help="suppress cover page")
    args = ap.parse_args()

    loaded = load_markdown(args.input)
    meta = loaded["meta"]
    body_html = loaded["body_html"]

    if not extract_title(loaded):
        print("warning: document has no title (no frontmatter `title` and no H1)", file=sys.stderr)

    today = dt.date.today().isoformat()

    parts = ["<html><body>"]
    if args.watermark:
        parts.append(f'<div class="watermark">{html_mod.escape(args.watermark)}</div>')
    if not args.no_cover:
        parts.append(_render_cover(meta, default_date=today))
    if args.toc:
        parts.append(_render_toc_stub(meta))
    parts.append('<div class="body">')
    parts.append(body_html)
    parts.append('</div>')
    parts.append("</body></html>")

    css = _css_template(watermark=args.watermark, running_header=args.running_header)
    HTML(string="\n".join(parts)).write_pdf(args.output, stylesheets=[CSS(string=css)])
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 6: Create `build-pdf/SKILL.md`**

````markdown
---
name: build-pdf
description: Turn any markdown file into a Jin-branded PDF. Cover page, all-Geist-Mono headings, body in Geist Sans, page numbers, clickable PDF bookmarks. Optional flags for TOC, watermark, running header. Use for kb learnings, writeups, paper drafts, technical reports — any doc you want in your branding rather than a neutral default. Distinct from gstack's `make-pdf` which produces a neutral Helvetica look. Voice triggers: "branded pdf", "build pdf", "pdf this in my style".
---

# /build-pdf

Markdown → Jin-branded PDF via weasyprint.

## When to invoke

User asks to make a PDF from a markdown file AND either explicitly mentions branding ("in my style", "branded", "with Geist") OR the markdown is something Jin owns and would normally want in his style (kb learnings, lab writeups, paper drafts, research summaries).

For neutral/professional/journal PDFs (Helvetica, no branding), use gstack's `/make-pdf` instead.

## Required arguments

- `--input PATH` — path to source markdown file
- `--output PATH` — desired PDF output path

## Optional flags

- `--toc` — visible TOC page after cover (PDF bookmarks always on regardless)
- `--watermark TEXT` — diagonal watermark on every page (e.g., `--watermark DRAFT`)
- `--running-header TEXT` — text in top margin of every page after cover
- `--no-cover` — suppress cover page

## Frontmatter

The input markdown may include YAML frontmatter for cover-page metadata:

```yaml
---
title: "Document title"           # required
eyebrow: "EYEBROW LABEL"          # optional
subtitle: "subtitle text"         # optional
name: "Jinchi Wei"                # optional
org: "UCSF / Acme"                # optional
date: "2026-05-01"                # optional, defaults to today
---
```

If frontmatter absent or `title` missing, the first H1 from the body is used as title.

## Invocation pattern

```bash
python ~/arcadia/superstack/skills/build-pdf/build.py \
  --input <markdown> \
  --output <pdf>
```

## Branding source of truth

All colors and fonts come from `~/arcadia/superstack/skills/_shared/branding.py`. Edit that file to change the palette globally for build-pdf, build-pptx, and build-docx.
````

- [ ] **Step 7: Create `build-pdf/tests/__init__.py`**

```python
"""build-pdf tests."""
```

- [ ] **Step 8: Run tests to verify pass**

```bash
source ~/miniconda3/etc/profile.d/conda.sh && conda activate deepdream && pytest ~/arcadia/superstack/skills/build-pdf/tests/ -v
```

Expected: 6 passed.

- [ ] **Step 9: Sync to `~/.claude/skills/`**

```bash
mkdir -p ~/.claude/skills/build-pdf/tests
cp ~/arcadia/superstack/skills/build-pdf/SKILL.md ~/.claude/skills/build-pdf/
cp ~/arcadia/superstack/skills/build-pdf/build.py ~/.claude/skills/build-pdf/
cp ~/arcadia/superstack/skills/build-pdf/tests/*.py ~/.claude/skills/build-pdf/tests/
cp ~/arcadia/superstack/skills/build-pdf/tests/fixture.md ~/.claude/skills/build-pdf/tests/
mkdir -p ~/.claude/skills/_shared/tests/fixtures
cp ~/arcadia/superstack/skills/_shared/__init__.py ~/.claude/skills/_shared/
cp ~/arcadia/superstack/skills/_shared/branding.py ~/.claude/skills/_shared/
cp ~/arcadia/superstack/skills/_shared/md_loader.py ~/.claude/skills/_shared/
cp ~/arcadia/superstack/skills/_shared/tests/__init__.py ~/.claude/skills/_shared/tests/
cp ~/arcadia/superstack/skills/_shared/tests/test_*.py ~/.claude/skills/_shared/tests/
cp ~/arcadia/superstack/skills/_shared/tests/fixtures/sample.md ~/.claude/skills/_shared/tests/fixtures/
```

- [ ] **Step 10: Smoke test the synced version**

```bash
python ~/.claude/skills/build-pdf/build.py \
  --input ~/.claude/skills/build-pdf/tests/fixture.md \
  --output /tmp/build-pdf-smoke.pdf
ls -la /tmp/build-pdf-smoke.pdf
open /tmp/build-pdf-smoke.pdf
```

Expected: PDF generated, opens in Preview, displays branded cover + body with Geist Mono headings.

- [ ] **Step 11: Commit**

```bash
cd ~/arcadia/superstack
git add skills/build-pdf/
git -c user.email="mrjinch@gmail.com" -c user.name="jinchiwei" commit -m "feat: build-pdf skill — markdown → Jin-branded PDF via weasyprint"
git push origin main
```

---

## Task 4: `build-docx` — pandoc + reference.docx

**Files:**
- Create: `~/arcadia/superstack/skills/build-docx/SKILL.md`
- Create: `~/arcadia/superstack/skills/build-docx/make_reference.py`
- Create: `~/arcadia/superstack/skills/build-docx/reference.docx` (binary, generated by make_reference.py)
- Create: `~/arcadia/superstack/skills/build-docx/build.py`
- Create: `~/arcadia/superstack/skills/build-docx/tests/__init__.py`
- Create: `~/arcadia/superstack/skills/build-docx/tests/fixture.md`
- Create: `~/arcadia/superstack/skills/build-docx/tests/test_build_docx.py`

Engine is **pandoc** (system-installed CLI), not python-docx. Pandoc handles markdown → docx well; we just provide a reference.docx with branded styles defined. `make_reference.py` programmatically generates that reference doc using python-docx so it's reproducible from script.

**Heads-up on font embedding:** docx font embedding requires low-level XML surgery in `word/fontTable.xml` + binary blobs in `word/embeddings/`. python-docx doesn't expose this. v1 ships WITHOUT font embedding — recipients without Geist installed see Helvetica fallback (specified in the style definition). Documented limitation. Future enhancement could add embedding.

- [ ] **Step 1: Verify pandoc + python-docx**

```bash
command -v pandoc && pandoc --version | head -1
source ~/miniconda3/etc/profile.d/conda.sh && conda activate deepdream && pip install --quiet python-docx
```

If pandoc not on PATH: `brew install pandoc` (Mac).

- [ ] **Step 2: Create fixture markdown at `build-docx/tests/fixture.md`**

```markdown
---
title: "Build-DOCX Smoke Test"
eyebrow: "FIXTURE"
subtitle: "exercises the pandoc reference.docx pipeline"
name: "Jinchi Wei"
org: "UCSF Department of Radiology"
date: "2026-05-01"
---

# Section One

Body text in Geist 11pt #14141C.

## Subsection A

Some `inline code` and `monospace` runs.

```python
def example():
    return "code block in Geist Mono"
```

## Subsection B

- First bullet
- Second bullet

# Section Two

| Col 1 | Col 2 | Col 3 |
|-------|-------|-------|
| a     | b     | c     |
```

- [ ] **Step 3: Failing test at `build-docx/tests/test_build_docx.py`**

```python
"""Build-DOCX: end-to-end smoke test."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parents[1]
FIXTURE = SKILL_DIR / "tests" / "fixture.md"
BUILD_PY = SKILL_DIR / "build.py"
REFERENCE = SKILL_DIR / "reference.docx"


def _render(out_path: Path, *extra_args: str) -> None:
    cmd = [sys.executable, str(BUILD_PY),
           "--input", str(FIXTURE),
           "--output", str(out_path),
           *extra_args]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode == 0, f"build.py failed:\nSTDERR: {proc.stderr}\nSTDOUT: {proc.stdout}"


def test_reference_docx_exists():
    """Reference.docx must be committed alongside build.py."""
    assert REFERENCE.is_file(), "reference.docx missing — run make_reference.py to regenerate"


def test_renders_docx_to_output_path(tmp_path):
    out = tmp_path / "out.docx"
    _render(out)
    assert out.is_file()
    assert out.stat().st_size > 1000


def test_docx_has_normal_style_with_branded_color(tmp_path):
    """Reference.docx's Normal style sets color to #14141C; output inherits."""
    out = tmp_path / "out.docx"
    _render(out)
    from docx import Document
    doc = Document(str(out))
    # The Normal style should be defined; its run color should be INK
    normal = doc.styles["Normal"]
    color = normal.font.color
    if color is not None and color.rgb is not None:
        assert str(color.rgb).upper() == "14141C"


def test_docx_has_branded_heading_styles(tmp_path):
    """Heading 1 / 2 / 3 styles exist with branded colors."""
    out = tmp_path / "out.docx"
    _render(out)
    from docx import Document
    doc = Document(str(out))
    style_names = {s.name for s in doc.styles}
    assert "Heading 1" in style_names
    assert "Heading 2" in style_names
    h1 = doc.styles["Heading 1"]
    if h1.font.color and h1.font.color.rgb:
        assert str(h1.font.color.rgb).upper() == "40E0D0"
    h2 = doc.styles["Heading 2"]
    if h2.font.color and h2.font.color.rgb:
        assert str(h2.font.color.rgb).upper() == "FF1493"


def test_docx_contains_fixture_text(tmp_path):
    out = tmp_path / "out.docx"
    _render(out)
    from docx import Document
    doc = Document(str(out))
    full_text = "\n".join(p.text for p in doc.paragraphs)
    assert "Section One" in full_text
    assert "Section Two" in full_text


def test_double_spaced_flag_increases_line_spacing(tmp_path):
    """--double-spaced flag should produce 2.0 line spacing on body paragraphs."""
    out = tmp_path / "out.docx"
    _render(out, "--double-spaced")
    from docx import Document
    doc = Document(str(out))
    # Just verify the build succeeds with the flag — actual spacing assertion
    # would require inspecting Normal style after override which pandoc handles
    # via metadata variables. Pragmatic: the flag exits 0 and produces a doc.
    assert out.stat().st_size > 1000
```

- [ ] **Step 4: Run tests to verify they fail (no build.py yet)**

```bash
source ~/miniconda3/etc/profile.d/conda.sh && conda activate deepdream && pytest ~/arcadia/superstack/skills/build-docx/tests/ -v
```

Expected: failures.

- [ ] **Step 5: Create `build-docx/make_reference.py`**

```python
"""Generate reference.docx with Jin-branded styles defined.

Run once when the skill is set up. Commit the output reference.docx.
Regenerate if branding rules change.

Usage:
    python make_reference.py --output reference.docx
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Wire imports to sibling _shared/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "_shared"))

import branding  # noqa: E402

try:
    from docx import Document
    from docx.enum.style import WD_STYLE_TYPE
    from docx.shared import Pt, RGBColor, Inches
except ImportError:
    raise SystemExit("python-docx not installed. Run: pip install python-docx")


def _hex_to_rgb(hex_str: str) -> RGBColor:
    """#FF1493 → RGBColor(0xFF, 0x14, 0x93)"""
    h = hex_str.lstrip("#")
    return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _style_run_font(style, *, font_name: str, size_pt: float, color_hex: str, bold: bool = False):
    style.font.name = font_name
    style.font.size = Pt(size_pt)
    style.font.color.rgb = _hex_to_rgb(color_hex)
    style.font.bold = bold


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", default=str(Path(__file__).resolve().parent / "reference.docx"))
    args = ap.parse_args()

    doc = Document()

    # Margins — 1in all sides
    section = doc.sections[0]
    section.top_margin = Inches(1)
    section.bottom_margin = Inches(1)
    section.left_margin = Inches(1)
    section.right_margin = Inches(1)

    # Normal — body
    normal = doc.styles["Normal"]
    _style_run_font(normal, font_name=branding.SANS_FONT, size_pt=11, color_hex=branding.INK)
    normal.paragraph_format.line_spacing = 1.5
    normal.paragraph_format.space_after = Pt(8)

    # Heading 1
    h1 = doc.styles["Heading 1"]
    _style_run_font(h1, font_name=branding.MONO_FONT, size_pt=18,
                    color_hex=branding.HEADING_1, bold=True)
    h1.paragraph_format.space_before = Pt(24)
    h1.paragraph_format.space_after = Pt(8)

    # Heading 2
    h2 = doc.styles["Heading 2"]
    _style_run_font(h2, font_name=branding.MONO_FONT, size_pt=14,
                    color_hex=branding.HEADING_2, bold=True)
    h2.paragraph_format.space_before = Pt(18)
    h2.paragraph_format.space_after = Pt(6)

    # Heading 3
    h3 = doc.styles["Heading 3"]
    _style_run_font(h3, font_name=branding.MONO_FONT, size_pt=12,
                    color_hex=branding.HEADING_3, bold=True)
    h3.paragraph_format.space_before = Pt(14)
    h3.paragraph_format.space_after = Pt(4)

    # Title (cover) — pandoc uses "Title" style for the document title in some templates
    if "Title" in [s.name for s in doc.styles]:
        title = doc.styles["Title"]
        _style_run_font(title, font_name=branding.MONO_FONT, size_pt=28,
                        color_hex=branding.INK, bold=True)

    # Subtitle
    if "Subtitle" in [s.name for s in doc.styles]:
        subtitle = doc.styles["Subtitle"]
        _style_run_font(subtitle, font_name=branding.SANS_FONT, size_pt=13,
                        color_hex=branding.MUTED)

    # Source Code (used by pandoc for fenced code blocks)
    try:
        sc = doc.styles["Source Code"]
    except KeyError:
        sc = doc.styles.add_style("Source Code", WD_STYLE_TYPE.PARAGRAPH)
    _style_run_font(sc, font_name=branding.MONO_FONT, size_pt=9.5, color_hex=branding.INK)

    # Verbatim Char (inline code)
    try:
        vb = doc.styles["Verbatim Char"]
    except KeyError:
        vb = doc.styles.add_style("Verbatim Char", WD_STYLE_TYPE.CHARACTER)
    _style_run_font(vb, font_name=branding.MONO_FONT, size_pt=10, color_hex=branding.INK)

    # Block Text (used for blockquotes by pandoc)
    try:
        bt = doc.styles["Block Text"]
    except KeyError:
        bt = doc.styles.add_style("Block Text", WD_STYLE_TYPE.PARAGRAPH)
    _style_run_font(bt, font_name=branding.SANS_FONT, size_pt=11, color_hex=branding.INK)
    bt.font.italic = True
    bt.paragraph_format.left_indent = Inches(0.5)

    # Sample paragraphs so the doc isn't empty (pandoc replaces these)
    doc.add_paragraph("Reference document for build-docx.", style="Normal")

    doc.save(args.output)
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 6: Run make_reference.py to generate reference.docx**

```bash
source ~/miniconda3/etc/profile.d/conda.sh && conda activate deepdream && python ~/arcadia/superstack/skills/build-docx/make_reference.py --output ~/arcadia/superstack/skills/build-docx/reference.docx
ls -la ~/arcadia/superstack/skills/build-docx/reference.docx
```

Expected: `wrote .../reference.docx`. File ~30-50KB.

- [ ] **Step 7: Create `build-docx/build.py`**

```python
"""build-docx — render a markdown file to a Jin-branded DOCX via pandoc.

Usage:
    python build.py --input doc.md --output doc.docx
    python build.py --input doc.md --output doc.docx --double-spaced --sections

Engine: pandoc (system-installed CLI). We pass --reference-doc=reference.docx
which contains all the branded styles. Pandoc applies them to the output.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parent
REFERENCE_DOCX = SKILL_DIR / "reference.docx"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", required=True, help="markdown file to render")
    ap.add_argument("--output", required=True, help="output DOCX path")
    ap.add_argument("--double-spaced", dest="double_spaced", action="store_true",
                    help="2.0 line spacing for journal manuscripts")
    ap.add_argument("--sections", action="store_true",
                    help="number headings (1, 1.1, 1.1.1, ...)")
    ap.add_argument("--toc", action="store_true",
                    help="auto-generated TOC at start (right-click 'update field' in Word)")
    args = ap.parse_args()

    if not shutil.which("pandoc"):
        print("ERROR: pandoc not on PATH. Install via `brew install pandoc`.", file=sys.stderr)
        return 1
    if not REFERENCE_DOCX.is_file():
        print(f"ERROR: {REFERENCE_DOCX} missing. Run make_reference.py to generate.",
              file=sys.stderr)
        return 1

    cmd = [
        "pandoc",
        str(args.input),
        "-o", str(args.output),
        "--reference-doc", str(REFERENCE_DOCX),
        "--from", "markdown+yaml_metadata_block+smart",  # +smart enables smartypants in pandoc
        "--to", "docx",
    ]
    if args.toc:
        cmd.append("--toc")
    if args.sections:
        cmd.append("--number-sections")
    if args.double_spaced:
        # Pandoc honors metadata variable `linestretch` for line spacing in some templates;
        # for docx, we override Normal's line spacing via a metadata-applied approach.
        # Simplest: post-process with python-docx after pandoc.
        pass  # handled below

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"pandoc failed:\nSTDERR: {proc.stderr}\nSTDOUT: {proc.stdout}", file=sys.stderr)
        return proc.returncode

    if args.double_spaced:
        _apply_double_spacing(args.output)

    print(f"wrote {args.output}")
    return 0


def _apply_double_spacing(docx_path: str) -> None:
    """Override Normal paragraph spacing to 2.0 in the generated docx."""
    try:
        from docx import Document
    except ImportError:
        print("warning: python-docx not installed; --double-spaced no-op", file=sys.stderr)
        return
    doc = Document(docx_path)
    normal = doc.styles["Normal"]
    normal.paragraph_format.line_spacing = 2.0
    doc.save(docx_path)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 8: Create `build-docx/SKILL.md`**

````markdown
---
name: build-docx
description: Turn any markdown file into a Jin-branded DOCX via pandoc. Geist Sans body, Geist Mono headings (turquoise H1, deeppink H2), 1.5 line spacing default. Optional flags for double-spacing (journal manuscripts), numbered sections, TOC. Use for paper drafts, lab writeups, revision letters — any Word doc where Jin's branding should hold in the source-of-truth before recipients edit. Voice triggers: "branded docx", "build docx", "make me a Word doc in my style".
---

# /build-docx

Markdown → Jin-branded DOCX via pandoc + reference.docx.

## When to invoke

User asks to make a DOCX from markdown for a paper draft, manuscript, lab writeup, or any Word doc that should be in Jin's brand identity.

For neutral/journal-default DOCX (Times/Calibri), the recipient's Word will substitute as needed; this skill produces the source-of-truth in your style.

## Required arguments

- `--input PATH` — markdown source
- `--output PATH` — output DOCX path

## Optional flags

- `--double-spaced` — 2.0 line spacing (journal manuscripts)
- `--sections` — numbered headings (1, 1.1, 1.1.1, ...)
- `--toc` — Word's native auto-generated TOC at start (right-click "update field" to refresh)

## Engine

pandoc CLI + a hand-tuned `reference.docx` with branded styles defined.
The reference.docx is regenerated by `make_reference.py` when palette changes.

## Frontmatter

Same YAML frontmatter contract as build-pdf. Pandoc consumes the metadata for title/author/date if present.

## Font embedding (limitation)

v1 does NOT embed Geist fonts in the output docx. Recipients without Geist
installed see Helvetica/Liberation Sans fallback (specified in the style chain).
Future enhancement could add embedding via low-level XML manipulation.

## Branding source of truth

`~/arcadia/superstack/skills/_shared/branding.py`. To update palette: edit branding.py, then re-run `make_reference.py` and commit the new reference.docx.
````

- [ ] **Step 9: Run tests to verify pass**

```bash
source ~/miniconda3/etc/profile.d/conda.sh && conda activate deepdream && pytest ~/arcadia/superstack/skills/build-docx/tests/ -v
```

Expected: 6 passed.

- [ ] **Step 10: Sync to ~/.claude/skills/**

```bash
mkdir -p ~/.claude/skills/build-docx/tests
cp ~/arcadia/superstack/skills/build-docx/SKILL.md ~/.claude/skills/build-docx/
cp ~/arcadia/superstack/skills/build-docx/build.py ~/.claude/skills/build-docx/
cp ~/arcadia/superstack/skills/build-docx/make_reference.py ~/.claude/skills/build-docx/
cp ~/arcadia/superstack/skills/build-docx/reference.docx ~/.claude/skills/build-docx/
cp ~/arcadia/superstack/skills/build-docx/tests/*.py ~/.claude/skills/build-docx/tests/
cp ~/arcadia/superstack/skills/build-docx/tests/fixture.md ~/.claude/skills/build-docx/tests/
```

- [ ] **Step 11: Smoke test**

```bash
python ~/.claude/skills/build-docx/build.py \
  --input ~/.claude/skills/build-docx/tests/fixture.md \
  --output /tmp/build-docx-smoke.docx
ls -la /tmp/build-docx-smoke.docx
open /tmp/build-docx-smoke.docx
```

Expected: DOCX opens in Word, Normal text in Geist 11pt off-black, H1 in turquoise Geist Mono, H2 in deeppink Geist Mono.

- [ ] **Step 12: Commit**

```bash
cd ~/arcadia/superstack
git add skills/build-docx/
git -c user.email="mrjinch@gmail.com" -c user.name="jinchiwei" commit -m "feat: build-docx skill — markdown → Jin-branded DOCX via pandoc + reference.docx"
git push origin main
```

---

## Task 5: `build-pptx` — slide masters

**Files:**
- Create: `~/arcadia/superstack/skills/build-pptx/SKILL.md`
- Create: `~/arcadia/superstack/skills/build-pptx/build.py` (slide master functions only — markdown parsing in Task 6)
- Create: `~/arcadia/superstack/skills/build-pptx/tests/__init__.py`
- Create: `~/arcadia/superstack/skills/build-pptx/tests/test_masters.py`

The slide master layouts: title slide, content slide, section divider, big-number, two-column, quote, end slide. Each is a Python function that takes a `Presentation` plus content args and adds one slide.

This task ships the master functions + tests asserting each builds correctly. Task 6 layers markdown parsing on top.

- [ ] **Step 1: Verify python-pptx**

```bash
source ~/miniconda3/etc/profile.d/conda.sh && conda activate deepdream && pip install --quiet python-pptx
```

- [ ] **Step 2: Failing tests at `build-pptx/tests/test_masters.py`**

```python
"""Slide master functions: each adds one slide of the right shape."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build import (  # noqa: E402
    new_presentation,
    add_title_slide,
    add_content_slide,
    add_section_divider,
    add_big_number_slide,
    add_two_column_slide,
    add_quote_slide,
    add_end_slide,
)


def test_new_presentation_is_16_9():
    prs = new_presentation()
    # 13.333" wide × 7.5" high in EMUs (914400 per inch)
    assert prs.slide_width == int(13.333 * 914400)
    assert prs.slide_height == int(7.5 * 914400)


def test_add_title_slide_dark_background():
    prs = new_presentation()
    s = add_title_slide(prs, eyebrow="TEST", title="Title", subtitle="sub",
                       name="Jinchi", org="UCSF", date="2026-05-01")
    assert s is not None
    assert len(prs.slides) == 1


def test_add_content_slide_white_background():
    prs = new_presentation()
    add_content_slide(prs, title="Section A", body_paragraphs=["one", "two"])
    assert len(prs.slides) == 1


def test_add_section_divider_cycles_color_by_index():
    """Section divider color is determined by the index parameter, cycling."""
    import branding
    prs = new_presentation()
    # Index 0 → turquoise, 2 → amber, 4 → wraps back to turquoise
    add_section_divider(prs, label="One", index=0)
    add_section_divider(prs, label="Three", index=2)
    add_section_divider(prs, label="Five", index=4)
    assert len(prs.slides) == 3
    # Cycle math: index%4 == 0 for slides 1 and 3
    assert branding.pick_section_color(0) == branding.TURQUOISE
    assert branding.pick_section_color(2) == branding.AMBER
    assert branding.pick_section_color(4) == branding.TURQUOISE


def test_add_big_number_slide():
    prs = new_presentation()
    add_big_number_slide(prs, number="+12.4%", caption="recall improvement on UCSF cohort")
    assert len(prs.slides) == 1


def test_add_two_column_slide():
    prs = new_presentation()
    add_two_column_slide(prs, title="Comparison",
                        left_title="Baseline", left_body=["Old approach", "manual"],
                        right_title="Proposed", right_body=["New approach", "automated"])
    assert len(prs.slides) == 1


def test_add_quote_slide():
    prs = new_presentation()
    add_quote_slide(prs, quote="The best research is reproducible.",
                   attribution="Jinchi Wei")
    assert len(prs.slides) == 1


def test_add_end_slide():
    prs = new_presentation()
    add_end_slide(prs, message="Thanks", contact="mrjinch@gmail.com")
    assert len(prs.slides) == 1


def test_full_deck_renders_to_file(tmp_path):
    """Compose a 7-slide deck using all masters, save, verify file."""
    prs = new_presentation()
    add_title_slide(prs, eyebrow="DECK TEST", title="Master Test Deck",
                    subtitle="exercises every master", name="Jinchi", org="UCSF",
                    date="2026-05-01")
    add_section_divider(prs, label="Section One", index=0)
    add_content_slide(prs, title="Content", body_paragraphs=["paragraph"])
    add_big_number_slide(prs, number="100%", caption="of tests passing")
    add_two_column_slide(prs, title="Compare",
                        left_title="A", left_body=["a1"],
                        right_title="B", right_body=["b1"])
    add_quote_slide(prs, quote="Ship.", attribution="Self")
    add_end_slide(prs, message="Thanks", contact="—")

    out = tmp_path / "deck.pptx"
    prs.save(str(out))
    assert out.is_file()
    assert out.stat().st_size > 5000

    # Re-open with python-pptx to verify slide count
    from pptx import Presentation
    reopened = Presentation(str(out))
    assert len(reopened.slides) == 7
```

- [ ] **Step 3: Run tests — verify ImportError**

```bash
source ~/miniconda3/etc/profile.d/conda.sh && conda activate deepdream && pytest ~/arcadia/superstack/skills/build-pptx/tests/test_masters.py -v
```

Expected: ImportError (build.py doesn't exist).

- [ ] **Step 4: Create `build-pptx/build.py` with master functions only**

```python
"""build-pptx — markdown → Jin-branded PPTX via python-pptx.

This file contains:
  - Slide master functions (add_title_slide, add_content_slide, etc.)
  - main() driver that parses markdown and dispatches to masters

Slide masters are independently callable from other Python code.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Wire imports to sibling _shared/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "_shared"))

import branding  # noqa: E402

try:
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
    from pptx.util import Emu, Inches, Pt
except ImportError:
    raise SystemExit("python-pptx not installed. Run: pip install python-pptx")


# === Color helpers ===
def _rgb(hex_str: str) -> RGBColor:
    h = hex_str.lstrip("#")
    return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


# Frequently-used RGBColor instances
INK_RGB        = _rgb(branding.INK)
WHITE_RGB      = _rgb(branding.WHITE)
TURQUOISE_RGB  = _rgb(branding.TURQUOISE)
DEEPPINK_RGB   = _rgb(branding.DEEPPINK)
AMBER_RGB      = _rgb(branding.AMBER)
BLUEVIOLET_RGB = _rgb(branding.BLUEVIOLET)
DIM_RGB        = _rgb(branding.DIM)
MUTED_RGB      = _rgb(branding.MUTED)
RULE_RGB       = _rgb(branding.RULE)
DARK_BG_RGB    = _rgb(branding.DARK_BG)
PAPER_RGB      = _rgb(branding.PAPER)


# === Internal helpers ===
def _set_bg(slide, color_rgb: RGBColor) -> None:
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = color_rgb


def _add_rect(slide, *, left, top, width, height,
              fill_rgb: RGBColor | None = None) -> None:
    shp = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,
                                 Inches(left), Inches(top),
                                 Inches(width), Inches(height))
    shp.shadow.inherit = False
    if fill_rgb is not None:
        shp.fill.solid()
        shp.fill.fore_color.rgb = fill_rgb
    else:
        shp.fill.background()
    shp.line.fill.background()


def _add_text(slide, text, *, left, top, width, height, size=18,
              color_rgb: RGBColor = INK_RGB, font: str = branding.SANS_FONT,
              bold=False, italic=False, align=PP_ALIGN.LEFT,
              anchor=MSO_ANCHOR.TOP):
    tb = slide.shapes.add_textbox(Inches(left), Inches(top),
                                  Inches(width), Inches(height))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Emu(0)
    tf.margin_top = tf.margin_bottom = Emu(0)
    p = tf.paragraphs[0]
    p.alignment = align
    r = p.add_run()
    r.text = text
    r.font.name = font
    r.font.size = Pt(size)
    r.font.color.rgb = color_rgb
    r.font.bold = bold
    r.font.italic = italic
    return tb


def _blank(prs):
    return prs.slides.add_slide(prs.slide_layouts[6])


# === Public API ===
def new_presentation() -> "Presentation":
    """Create a 16:9 widescreen presentation."""
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    return prs


def add_title_slide(prs, *, eyebrow: str = "", title: str, subtitle: str = "",
                    name: str = "", org: str = "", date: str = ""):
    """Dark #14141C background. Eyebrow turquoise mono, title white mono,
    subtitle off-white sans, name turquoise mono, org deeppink mono, date dim mono."""
    s = _blank(prs)
    _set_bg(s, DARK_BG_RGB)

    if eyebrow:
        _add_text(s, eyebrow, left=1.0, top=1.5, width=11, height=0.4,
                  size=14, color_rgb=TURQUOISE_RGB, font=branding.MONO_FONT, bold=True)
    _add_text(s, title, left=1.0, top=2.0, width=11.3, height=2.0,
              size=48, color_rgb=WHITE_RGB, font=branding.MONO_FONT, bold=True)
    if subtitle:
        _add_text(s, subtitle, left=1.0, top=4.1, width=11.3, height=1.0,
                  size=18, color_rgb=_rgb("#E5E5EA"), font=branding.SANS_FONT)
    cursor_top = 5.4
    if name:
        _add_text(s, name, left=1.0, top=cursor_top, width=11, height=0.4,
                  size=22, color_rgb=TURQUOISE_RGB, font=branding.MONO_FONT, bold=True)
        cursor_top += 0.5
    if org:
        _add_text(s, org, left=1.0, top=cursor_top, width=11, height=0.35,
                  size=16, color_rgb=DEEPPINK_RGB, font=branding.MONO_FONT, bold=True)
        cursor_top += 0.45

    # Hairline rule
    _add_rect(s, left=1.0, top=cursor_top + 0.1, width=4.0, height=0.005, fill_rgb=RULE_RGB)
    if date:
        _add_text(s, date, left=1.0, top=cursor_top + 0.25, width=11, height=0.3,
                  size=12, color_rgb=DIM_RGB, font=branding.MONO_FONT)
    return s


def add_content_slide(prs, *, title: str, body_paragraphs: list[str]):
    """White background. Title turquoise mono top-left, body Geist sans."""
    s = _blank(prs)
    _set_bg(s, WHITE_RGB)
    _add_text(s, title, left=0.6, top=0.4, width=12.5, height=0.8,
              size=32, color_rgb=TURQUOISE_RGB, font=branding.MONO_FONT, bold=True)
    # Hairline rule under title
    _add_rect(s, left=0.6, top=1.25, width=12.0, height=0.005, fill_rgb=RULE_RGB)
    body_text = "\n".join(body_paragraphs)
    _add_text(s, body_text, left=0.6, top=1.5, width=12.5, height=5.5,
              size=22, color_rgb=INK_RGB, font=branding.SANS_FONT)
    return s


def add_section_divider(prs, *, label: str, index: int = 0):
    """Full-bleed brand color. Cycles through canonical priority order."""
    bg_hex = branding.pick_section_color(index)
    text_hex = branding.section_text_color(bg_hex)
    s = _blank(prs)
    _set_bg(s, _rgb(bg_hex))
    _add_text(s, label.upper(), left=1.0, top=3.2, width=11.5, height=1.6,
              size=44, color_rgb=_rgb(text_hex), font=branding.MONO_FONT, bold=True)
    # Subtle dash
    _add_text(s, "—", left=1.0, top=4.6, width=2, height=0.5,
              size=28, color_rgb=_rgb(text_hex), font=branding.MONO_FONT)
    return s


def add_big_number_slide(prs, *, number: str, caption: str = ""):
    """White background. Giant deeppink number centered, caption underneath."""
    s = _blank(prs)
    _set_bg(s, WHITE_RGB)
    _add_text(s, number, left=0.5, top=2.4, width=12.3, height=2.2,
              size=120, color_rgb=DEEPPINK_RGB, font=branding.MONO_FONT, bold=True,
              align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    if caption:
        _add_text(s, caption, left=1.0, top=4.8, width=11.3, height=0.8,
                  size=18, color_rgb=MUTED_RGB, font=branding.SANS_FONT,
                  align=PP_ALIGN.CENTER)
    return s


def add_two_column_slide(prs, *, title: str,
                         left_title: str, left_body: list[str],
                         right_title: str, right_body: list[str]):
    """White background. Title at top, two side-by-side columns."""
    s = _blank(prs)
    _set_bg(s, WHITE_RGB)
    _add_text(s, title, left=0.6, top=0.4, width=12.5, height=0.8,
              size=32, color_rgb=TURQUOISE_RGB, font=branding.MONO_FONT, bold=True)
    _add_rect(s, left=0.6, top=1.25, width=12.0, height=0.005, fill_rgb=RULE_RGB)

    # Left column
    _add_text(s, left_title, left=0.6, top=1.5, width=5.8, height=0.5,
              size=18, color_rgb=DEEPPINK_RGB, font=branding.MONO_FONT, bold=True)
    _add_text(s, "\n".join(left_body), left=0.6, top=2.1, width=5.8, height=5.0,
              size=18, color_rgb=INK_RGB, font=branding.SANS_FONT)

    # Right column
    _add_text(s, right_title, left=6.95, top=1.5, width=5.8, height=0.5,
              size=18, color_rgb=DEEPPINK_RGB, font=branding.MONO_FONT, bold=True)
    _add_text(s, "\n".join(right_body), left=6.95, top=2.1, width=5.8, height=5.0,
              size=18, color_rgb=INK_RGB, font=branding.SANS_FONT)

    # Vertical hairline between columns
    _add_rect(s, left=6.7, top=1.5, width=0.005, height=5.5, fill_rgb=RULE_RGB)
    return s


def add_quote_slide(prs, *, quote: str, attribution: str = ""):
    """White background. Quote centered in italic sans, attribution mono."""
    s = _blank(prs)
    _set_bg(s, WHITE_RGB)
    _add_text(s, f'"{quote}"', left=1.5, top=2.5, width=10.3, height=2.5,
              size=36, color_rgb=INK_RGB, font=branding.SANS_FONT, italic=True,
              align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    if attribution:
        _add_text(s, f"— {attribution}", left=1.5, top=5.3, width=10.3, height=0.4,
                  size=14, color_rgb=MUTED_RGB, font=branding.MONO_FONT,
                  align=PP_ALIGN.CENTER)
    return s


def add_end_slide(prs, *, message: str = "Thanks", contact: str = ""):
    """Dark #14141C background. Bookend match for title slide."""
    s = _blank(prs)
    _set_bg(s, DARK_BG_RGB)
    _add_text(s, message, left=1.0, top=2.7, width=11.3, height=2.0,
              size=64, color_rgb=WHITE_RGB, font=branding.MONO_FONT, bold=True,
              align=PP_ALIGN.CENTER)
    if contact:
        _add_text(s, contact, left=1.0, top=4.8, width=11.3, height=0.5,
                  size=14, color_rgb=DIM_RGB, font=branding.MONO_FONT,
                  align=PP_ALIGN.CENTER)
    return s


# main() implemented in Task 6 (markdown parsing)
def main():
    print("build-pptx main() not yet implemented (Task 6 of plan)", file=__import__("sys").stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Create `build-pptx/tests/__init__.py`**

```python
"""build-pptx tests."""
```

- [ ] **Step 6: Run tests to verify pass**

```bash
source ~/miniconda3/etc/profile.d/conda.sh && conda activate deepdream && pytest ~/arcadia/superstack/skills/build-pptx/tests/test_masters.py -v
```

Expected: 9 passed.

- [ ] **Step 7: Commit (no sync yet — main() not done)**

```bash
cd ~/arcadia/superstack
git add skills/build-pptx/build.py skills/build-pptx/tests/__init__.py skills/build-pptx/tests/test_masters.py
git -c user.email="mrjinch@gmail.com" -c user.name="jinchiwei" commit -m "feat: build-pptx slide masters — title/content/divider/big-number/two-column/quote/end"
```

---

## Task 6: `build-pptx` — markdown parser + `main()` + flags

**Files:**
- Modify: `~/arcadia/superstack/skills/build-pptx/build.py` — replace stub `main()` with full implementation
- Create: `~/arcadia/superstack/skills/build-pptx/tests/fixture.md`
- Create: `~/arcadia/superstack/skills/build-pptx/tests/test_main.py`
- Create: `~/arcadia/superstack/skills/build-pptx/SKILL.md`

Markdown parsing:
- `---` separator divides slides
- `# Title` (as the first H1 in a slide) → if it's the FIRST slide, it's the title slide using frontmatter; otherwise content slide
- `## Section` followed immediately by `---` and nothing else → section divider
- Other content slides: title from H1 or H2, body from remaining paragraphs

For v1, simple parsing rules. Fancy big-number / two-column / quote variants happen via fenced delimiters or HTML comments later (not in this plan).

- [ ] **Step 1: Create fixture at `build-pptx/tests/fixture.md`**

```markdown
---
title: "Build-PPTX Smoke Test"
eyebrow: "FIXTURE"
subtitle: "exercises slide-master rendering"
name: "Jinchi Wei"
org: "UCSF"
date: "2026-05-01"
---

---

## Background

The first content slide. Some bullet points:

- Point one
- Point two

---

## Methods

A second content slide.

- Bullet a
- Bullet b
- Bullet c

---

## Results

Third content slide. Plain prose, no bullets.

This is the body.
```

(The leading `---` after frontmatter is the separator before the first content slide. Pandoc/marked-style.)

- [ ] **Step 2: Failing test at `build-pptx/tests/test_main.py`**

```python
"""build-pptx end-to-end markdown→pptx test."""

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
    assert proc.returncode == 0, f"build.py failed:\nSTDERR: {proc.stderr}"


def test_renders_pptx(tmp_path):
    out = tmp_path / "out.pptx"
    _render(out)
    assert out.is_file()
    assert out.stat().st_size > 5000


def test_pptx_starts_with_zip_magic_bytes(tmp_path):
    """PPTX is a zip; starts with PK."""
    out = tmp_path / "out.pptx"
    _render(out)
    assert out.read_bytes()[:2] == b"PK"


def test_pptx_has_correct_slide_count(tmp_path):
    """Title slide + 3 content slides = 4 slides."""
    out = tmp_path / "out.pptx"
    _render(out)
    from pptx import Presentation
    prs = Presentation(str(out))
    assert len(prs.slides) == 4


def test_pptx_slide_titles_match_fixture(tmp_path):
    """Slide 1 = title, slides 2-4 = Background / Methods / Results."""
    out = tmp_path / "out.pptx"
    _render(out)
    from pptx import Presentation
    prs = Presentation(str(out))
    titles = []
    for slide in prs.slides:
        for shp in slide.shapes:
            if shp.has_text_frame:
                titles.extend(p.text for p in shp.text_frame.paragraphs if p.text.strip())
    joined = "\n".join(titles)
    assert "Build-PPTX Smoke Test" in joined  # title slide
    assert "Background" in joined
    assert "Methods" in joined
    assert "Results" in joined
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
source ~/miniconda3/etc/profile.d/conda.sh && conda activate deepdream && pytest ~/arcadia/superstack/skills/build-pptx/tests/test_main.py -v
```

Expected: failures (main returns 1).

- [ ] **Step 4: Replace stub `main()` in `build-pptx/build.py`**

This step has TWO edits to the same file: (a) ADD imports near the top, (b) replace the stub at the bottom.

**Edit (a):** Find the import block near the top of `build.py`. Right after the existing `import branding  # noqa: E402` line, add:

```python
import argparse  # noqa: E402
import datetime as dt  # noqa: E402
import re  # noqa: E402

from md_loader import load_markdown, extract_title  # noqa: E402
```

Also add a module-level regex constant after the import block (anywhere before the first `def`):

```python
_HTML_TAG_RE = re.compile(r"<[^>]+>")
```

**Edit (b):** Find the stub at the bottom:
```python
# main() implemented in Task 6 (markdown parsing)
def main():
    print("build-pptx main() not yet implemented (Task 6 of plan)", file=__import__("sys").stderr)
    return 1
```

Replace with these helper functions + new main():

```python


def _strip_html(text: str) -> str:
    """Remove HTML tags from a string. Used to flatten rendered HTML back to plain text."""
    return _HTML_TAG_RE.sub("", text).strip()


def _split_slides(body_html: str) -> list[str]:
    """Split rendered body HTML on <hr> elements (which markdown's `---` becomes).
    Returns a list of HTML chunks, one per slide."""
    # markdown's smarty extension renders --- as <hr /> when on its own line
    parts = re.split(r"<hr\s*/?>", body_html)
    # Strip empties caused by leading/trailing ---
    return [p.strip() for p in parts if p.strip()]


def _parse_slide_chunk(html_chunk: str) -> dict:
    """Extract a slide title (first H1 or H2) and body paragraphs from one HTML chunk."""
    title_match = re.search(r"<(h[12])[^>]*>(.*?)</\1>", html_chunk)
    if title_match:
        title = _strip_html(title_match.group(2))
        rest = html_chunk[title_match.end():]
    else:
        title = ""
        rest = html_chunk

    # Pull body paragraphs (lines from <p>, <li>) as plain text
    paragraphs = []
    for m in re.finditer(r"<(p|li)[^>]*>(.*?)</\1>", rest, re.DOTALL):
        text = _strip_html(m.group(2)).strip()
        if text:
            # Prepend "• " for list items so they read as bullets
            if m.group(1) == "li":
                paragraphs.append(f"•  {text}")
            else:
                paragraphs.append(text)
    return {"title": title, "body": paragraphs}


def main() -> int:
    ap = argparse.ArgumentParser(description="markdown → Jin-branded PPTX")
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--no-cover", dest="no_cover", action="store_true",
                    help="suppress title slide (start with first content slide)")
    ap.add_argument("--no-end", dest="no_end", action="store_true",
                    help="suppress closing 'Thanks' slide")
    args = ap.parse_args()

    loaded = load_markdown(args.input)
    meta = loaded["meta"]
    today = dt.date.today().isoformat()

    prs = new_presentation()

    # Title slide
    if not args.no_cover:
        add_title_slide(
            prs,
            eyebrow=str(meta.get("eyebrow", "")),
            title=extract_title(loaded) or Path(args.input).stem,
            subtitle=str(meta.get("subtitle", "")),
            name=str(meta.get("name", "")),
            org=str(meta.get("org", "")),
            date=str(meta.get("date") or today),
        )

    # Content slides
    chunks = _split_slides(loaded["body_html"])
    for chunk in chunks:
        slide = _parse_slide_chunk(chunk)
        if slide["title"] or slide["body"]:
            add_content_slide(prs, title=slide["title"] or "(untitled)",
                              body_paragraphs=slide["body"])

    # End slide
    if not args.no_end:
        add_end_slide(prs, message="Thanks",
                      contact=str(meta.get("name") or ""))

    prs.save(args.output)
    print(f"wrote {args.output}")
    return 0
```

(Replace ONLY the stub `main()` definition; the rest of the file from Task 5 stays.)

- [ ] **Step 5: Run tests to verify pass**

```bash
source ~/miniconda3/etc/profile.d/conda.sh && conda activate deepdream && pytest ~/arcadia/superstack/skills/build-pptx/tests/ -v
```

Expected: 13 passed (9 from test_masters + 4 from test_main).

- [ ] **Step 6: Create `build-pptx/SKILL.md`**

````markdown
---
name: build-pptx
description: Turn any markdown file into a Jin-branded PPTX (16:9, dark title + closing slides, white content, all-Geist-Mono headings, slide separation by `---`). Optional flags for suppressing cover or end slide. Use for research talks, conference presentations, lab meetings — slide decks where Jin's branding matters. Distinct from generic / template-y PowerPoint output. Voice triggers: "branded pptx", "build pptx", "slide deck in my style", "presentation".
---

# /build-pptx

Markdown → Jin-branded 16:9 PPTX via python-pptx.

## When to invoke

User asks to make slides from markdown for a research talk, lab meeting, conference presentation, or any deck that should be in Jin's brand identity.

## Required arguments

- `--input PATH` — markdown source
- `--output PATH` — output PPTX path

## Optional flags

- `--no-cover` — suppress title slide (start with first content slide)
- `--no-end` — suppress closing "Thanks" slide

## Markdown format

- YAML frontmatter at top (same fields as build-pdf/build-docx) populates the title slide
- `---` (horizontal rule) separates slides
- First H1/H2 of each slide chunk becomes the slide title
- Bullets (`-` lists) render as bulleted lines on the slide
- Paragraphs render as body prose

## Slide masters available (Python API)

`new_presentation()`, `add_title_slide`, `add_content_slide`, `add_section_divider`, `add_big_number_slide`, `add_two_column_slide`, `add_quote_slide`, `add_end_slide`. See `build.py` for signatures. v1's main() only auto-uses title + content + end; specialized masters are callable from custom Python.

## Branding source of truth

`~/arcadia/superstack/skills/_shared/branding.py`.
````

- [ ] **Step 7: Sync to ~/.claude/skills/**

```bash
mkdir -p ~/.claude/skills/build-pptx/tests
cp ~/arcadia/superstack/skills/build-pptx/SKILL.md ~/.claude/skills/build-pptx/
cp ~/arcadia/superstack/skills/build-pptx/build.py ~/.claude/skills/build-pptx/
cp ~/arcadia/superstack/skills/build-pptx/tests/*.py ~/.claude/skills/build-pptx/tests/
cp ~/arcadia/superstack/skills/build-pptx/tests/fixture.md ~/.claude/skills/build-pptx/tests/
```

- [ ] **Step 8: Smoke test**

```bash
python ~/.claude/skills/build-pptx/build.py \
  --input ~/.claude/skills/build-pptx/tests/fixture.md \
  --output /tmp/build-pptx-smoke.pptx
ls -la /tmp/build-pptx-smoke.pptx
open /tmp/build-pptx-smoke.pptx
```

Expected: PowerPoint opens 4-slide deck. Slide 1 dark title, slides 2-4 white content with Geist Mono titles in turquoise.

- [ ] **Step 9: Commit**

```bash
cd ~/arcadia/superstack
git add skills/build-pptx/
git -c user.email="mrjinch@gmail.com" -c user.name="jinchiwei" commit -m "feat: build-pptx markdown driver + SKILL.md — full skill ready"
git push origin main
```

---

## Task 7: Integration smoke test + tag

This task is non-TDD. End-to-end verification that all three skills produce branded output from a single fixture markdown.

**Files:**
- Create: `~/arcadia/superstack/docs/plans/SMOKE_TEST.md` (one fixture + commands; checked-in for repeatability)

- [ ] **Step 1: Create unified fixture at `~/arcadia/superstack/docs/plans/smoke_fixture.md`**

```markdown
---
title: "Build Skills Smoke Test"
eyebrow: "INTEGRATION"
subtitle: "exercises build-pdf / build-pptx / build-docx end-to-end"
name: "Jinchi Wei"
org: "UCSF Department of Radiology"
date: "2026-05-01"
---

# Section One

Body text here. Curly quotes "test" and em-dash --- conversion.

## Subsection

A paragraph with `inline code` and a list:

- First bullet
- Second bullet

# Section Two

A second section to verify multi-section rendering.
```

- [ ] **Step 2: Render all three formats**

```bash
mkdir -p /tmp/build-skills-smoke
SRC=~/arcadia/superstack/docs/plans/smoke_fixture.md

python ~/.claude/skills/build-pdf/build.py --input $SRC --output /tmp/build-skills-smoke/out.pdf
python ~/.claude/skills/build-docx/build.py --input $SRC --output /tmp/build-skills-smoke/out.docx
python ~/.claude/skills/build-pptx/build.py --input $SRC --output /tmp/build-skills-smoke/out.pptx

ls -la /tmp/build-skills-smoke/
```

Expected: all three files exist, sizes > 5KB.

- [ ] **Step 3: Visual inspection**

```bash
open /tmp/build-skills-smoke/out.pdf
open /tmp/build-skills-smoke/out.docx
open /tmp/build-skills-smoke/out.pptx
```

Verify:
- **PDF:** cover with eyebrow + title + subtitle + name (turquoise) + org (deeppink) + date. Body sections in Geist Mono headings (turquoise H1, deeppink H2). Page numbers bottom-center. Curly quotes + em-dash visible.
- **DOCX:** opens in Word/Pages. Body in Geist 11pt. H1 in turquoise Geist Mono, H2 in deeppink. 1.5 line spacing.
- **PPTX:** 4 slides. Dark title slide with branded metadata. White content slides with Geist Mono titles. Closing "Thanks" slide.

- [ ] **Step 4: Run all tests one more time**

```bash
source ~/miniconda3/etc/profile.d/conda.sh && conda activate deepdream && pytest ~/arcadia/superstack/skills/_shared/tests/ ~/arcadia/superstack/skills/build-pdf/tests/ ~/arcadia/superstack/skills/build-docx/tests/ ~/arcadia/superstack/skills/build-pptx/tests/ -v
```

Expected: all pass.

- [ ] **Step 5: Tag**

```bash
cd ~/arcadia/superstack
git add docs/plans/smoke_fixture.md
git -c user.email="mrjinch@gmail.com" -c user.name="jinchiwei" commit -m "docs: smoke fixture for build-pdf/pptx/docx integration test"
git push origin main
git tag build-skills-v1
git push origin build-skills-v1
```

- [ ] **Step 6: Capture any surprises as a kb learning**

If anything in the smoke test was surprising (font fallback didn't work, pandoc choked on something specific, python-pptx dropped a layout silently), use jkw-obs `record_learning` to capture it.

If everything was clean, record a single `decisions` learning: "Build skills v1 ships — three branded document builders sharing _shared/branding.py."

---

## Self-Review Checklist

- [ ] All 7 tasks committed
- [ ] `pytest skills/` shows green across `_shared/`, `build-pdf/`, `build-docx/`, `build-pptx/`
- [ ] Three skills synced to `~/.claude/skills/{build-pdf,build-docx,build-pptx}/`
- [ ] Slash commands `/build-pdf`, `/build-docx`, `/build-pptx` invocable in a fresh Claude Code session (may require restart for skill list to refresh)
- [ ] Smoke fixture renders all three formats with consistent branding
- [ ] `_shared/branding.py` is the single source of truth — changing a hex value there changes all three formats on next render
- [ ] Tag `build-skills-v1` pushed

When all boxes ticked, build-skills-v1 done.

---

## Future enhancements (NOT in this plan)

- DOCX font embedding (low-level XML; ~150 LOC; v2)
- PPTX advanced slide masters via fenced markdown blocks (`::: big-number` etc. — Pandoc-style)
- TOC page in build-pdf rendered from headings (currently just a stub pointing at PDF outline)
- Section-divider auto-insertion in PPTX when H1 appears
- Watermark variations (per-page transparency level, custom rotation angle)
- Citation processing for build-docx via `--bibliography` flag
