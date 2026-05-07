"""Tests for skills/autoresearch/templates/_build_pptx.py.

Covers the deck-markdown synthesizer (synthesize_deck_md) and a few small
helpers (_iter_figures, _iter_dirs, _extract_headline). The actual rendering
is delegated to the build-pptx skill, which has its own test suite — we
don't re-test that here.

Asserts the structural contract of the synthesized markdown:
  - YAML frontmatter present, no body H1 (build-pptx adds the cover)
  - Each iter dir produces exactly one slide (separated by ---)
  - Each iter slide has at most one figure embedded
  - Image paths are relative to the deck.md location, not project root
  - Iter dirs without figures still produce a slide (with a placeholder)
  - No trailing "## Thanks" — build-pptx adds the closing slide
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest

_TEMPLATES = Path(__file__).resolve().parents[1] / "templates"
sys.path.insert(0, str(_TEMPLATES))

import _build_pptx as bp  # noqa: E402


# ---------------------------------------------------------------------------
# Fixture builder
# ---------------------------------------------------------------------------

def _png_bytes() -> bytes:
    """A 1×1 transparent PNG. Smallest valid PNG, enough for synthesis to
    "find" a figure file without needing a real image."""
    return (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR"
        b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
        b"\x1f\x15\xc4\x89"
        b"\x00\x00\x00\rIDATx\x9cc````\x00\x00\x00\x05\x00\x01"
        b"\r\n-\xb4"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )


@pytest.fixture
def session_root(tmp_path):
    """Build a synthetic results/<date>_<scope>/ tree:
      iter-01_per_site_3site/  - has summary.md + fig_per_site_roc.png
      iter-02_calibration/     - has summary.md + fig_calibration.png + fig_extra.png
      iter-03_no_figs/         - has summary.md but NO figures
      README.md                - session preamble
    """
    root = tmp_path / "results" / "2026-05-07_my-scope"
    root.mkdir(parents=True)

    (root / "README.md").write_text(
        "# my-scope\n\n"
        "**Scope:** Test session for pptx synthesizer\n"
        "**Target:** maximize AUC on bact_pos\n"
    )

    iter1 = root / "iter-01_per_site_3site"
    iter1.mkdir()
    (iter1 / "summary.md").write_text(
        "# per_site · 3site\n\n"
        "**Headline metric (overall AUC):** 0.9698 [boot 95% CI 0.956, 0.981]\n"
        "**N:** 1648 patients (154 bact+)\n\n"
        "## Per-site AUC\n\n"
        "| Site | n | AUC |\n|---|---|---|\n| jhu | 1175 | 0.974 |\n"
    )
    (iter1 / "fig_per_site_roc.png").write_bytes(_png_bytes())

    iter2 = root / "iter-02_calibration"
    iter2.mkdir()
    (iter2 / "summary.md").write_text(
        "# calibration · 3site\n\n"
        "**Headline metric (best ECE):** 0.0139 (temperature)\n\n"
        "## Methods\n\n"
        "| Method | ECE |\n|---|---|\n| raw | 0.0147 |\n"
    )
    (iter2 / "fig_calibration.png").write_bytes(_png_bytes())
    (iter2 / "fig_extra.png").write_bytes(_png_bytes())

    iter3 = root / "iter-03_no_figs"
    iter3.mkdir()
    (iter3 / "summary.md").write_text(
        "# no_figs · 3site\n\n"
        "**Headline metric (mean):** 0.85\n\n"
        "Some prose without a figure.\n"
    )

    return root


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def test_iter_dirs_returns_iter_only_in_order(session_root):
    dirs = bp._iter_dirs(session_root)
    names = [d.name for d in dirs]
    assert names == ["iter-01_per_site_3site",
                     "iter-02_calibration",
                     "iter-03_no_figs"]


def test_iter_figures_finds_only_fig_pngs(session_root):
    iter2 = session_root / "iter-02_calibration"
    figs = bp._iter_figures(iter2)
    names = [f.name for f in figs]
    assert names == ["fig_calibration.png", "fig_extra.png"]


def test_iter_figures_handles_no_figures(session_root):
    iter3 = session_root / "iter-03_no_figs"
    assert bp._iter_figures(iter3) == []


def test_extract_headline_pulls_metric_line():
    s = ("**Headline metric (overall AUC):** 0.97 [0.95, 0.98]\n"
         "**N:** 1648 patients\n")
    h = bp._extract_headline(s)
    assert "0.97" in h
    assert "Headline metric" not in h  # wrapper stripped


def test_extract_headline_falls_back_to_first_line():
    s = "Some prose paragraph.\n\nSecond paragraph.\n"
    h = bp._extract_headline(s)
    assert h == "Some prose paragraph."


def test_extract_headline_empty():
    assert bp._extract_headline("") == ""


def test_humanize_strips_iter_prefix():
    assert bp._humanize("iter-08_fusion_variant_3site") == "Fusion Variant 3site"


# ---------------------------------------------------------------------------
# synthesize_deck_md
# ---------------------------------------------------------------------------

def test_deck_has_yaml_frontmatter(session_root):
    md = bp.synthesize_deck_md(session_root, date="2026-05-07", scope="my-scope")
    assert md.startswith("---\n")
    # Frontmatter closes within first 6 lines
    second_dash = md.find("\n---\n", 4)
    assert 0 < second_dash < 200
    assert 'title:' in md[:second_dash]


def test_deck_has_no_body_h1(session_root):
    """build-pptx renders the cover from frontmatter; a body H1 produces a
    duplicate title slide. We must not emit one."""
    md = bp.synthesize_deck_md(session_root, date="2026-05-07", scope="my-scope")
    body = md.split("\n---\n", 2)[2]  # everything after frontmatter
    assert not any(line.startswith("# ") for line in body.splitlines()), \
        "synthesizer must not emit a body H1"


def test_deck_has_no_trailing_thanks(session_root):
    """build-pptx auto-adds an end slide. We must not emit our own."""
    md = bp.synthesize_deck_md(session_root, date="2026-05-07", scope="my-scope")
    assert "## Thanks" not in md, \
        "synthesizer must not emit its own Thanks slide (build-pptx adds one)"


def test_deck_one_slide_per_iter(session_root):
    md = bp.synthesize_deck_md(session_root, date="2026-05-07", scope="my-scope")
    iter_titles = [ln for ln in md.splitlines() if ln.startswith("## iter-")]
    assert len(iter_titles) == 3, \
        f"expected 1 slide per iter dir (3), got {len(iter_titles)}: {iter_titles}"


def test_deck_iter_titles_humanized(session_root):
    md = bp.synthesize_deck_md(session_root, date="2026-05-07", scope="my-scope")
    assert "## iter-1 — Per Site 3site" in md
    assert "## iter-2 — Calibration" in md
    assert "## iter-3 — No Figs" in md


def test_deck_image_paths_relative_to_session_root(session_root):
    """Image paths must be relative to the deck.md location (= session_root),
    not relative to project root, since build-pptx resolves them relative to
    the markdown file's parent dir."""
    md = bp.synthesize_deck_md(session_root, date="2026-05-07", scope="my-scope")
    img_lines = [ln for ln in md.splitlines() if ln.startswith("![")]
    assert len(img_lines) == 2  # iter-01 and iter-02 have figures; iter-03 doesn't
    for line in img_lines:
        # Should look like `![fig_xxx](iter-NN_xxx/fig_xxx.png)` — no leading
        # `results/` and no absolute path component.
        assert "iter-" in line
        assert "results/" not in line, \
            f"path should be relative to session root, got: {line}"
        assert not line.startswith("![") or "/" not in line.split("(")[1].split(")")[0].split("/")[0], \
            "first path segment should be the iter dir, not a parent"


def test_deck_one_figure_per_iter_max(session_root):
    """iter-02 has 2 figures but the synthesizer should embed only the first
    (multiple figures on one slide forces content-image-only and drops the
    headline caption)."""
    md = bp.synthesize_deck_md(session_root, date="2026-05-07", scope="my-scope")
    # Find the iter-02 chunk
    chunks = md.split("\n---\n")
    iter2_chunk = next(c for c in chunks if "iter-2 — Calibration" in c)
    img_lines = [ln for ln in iter2_chunk.splitlines() if ln.startswith("![")]
    assert len(img_lines) == 1, \
        f"iter-2 has 2 fig_*.png files but synthesizer should embed only 1; got {img_lines}"
    assert "fig_calibration.png" in img_lines[0]


def test_deck_iter_without_figure_still_produces_slide(session_root):
    md = bp.synthesize_deck_md(session_root, date="2026-05-07", scope="my-scope")
    chunks = md.split("\n---\n")
    iter3_chunk = next((c for c in chunks if "iter-3 — No Figs" in c), None)
    assert iter3_chunk is not None
    # Must have headline content even without a figure
    assert "0.85" in iter3_chunk or "no figure produced" in iter3_chunk


def test_deck_includes_session_overview_when_readme_has_meta(session_root):
    md = bp.synthesize_deck_md(session_root, date="2026-05-07", scope="my-scope")
    assert "## Session overview" in md
    assert "Test session for pptx synthesizer" in md
    assert "maximize AUC on bact_pos" in md


def test_deck_omits_overview_when_readme_missing(tmp_path):
    """If README.md has no Scope/Target lines, skip the overview slide."""
    root = tmp_path / "results" / "2026-05-07_bare"
    root.mkdir(parents=True)
    iter1 = root / "iter-01_x"
    iter1.mkdir()
    (iter1 / "summary.md").write_text("# x\nSome content\n")
    md = bp.synthesize_deck_md(root, date="2026-05-07", scope="bare")
    assert "## Session overview" not in md


def test_deck_iter_slide_separator_present(session_root):
    md = bp.synthesize_deck_md(session_root, date="2026-05-07", scope="my-scope")
    # Count "---" slide separators that fall on their own line (not the YAML
    # frontmatter delimiters at the very top of the file).
    sep_count = md.count("\n---\n")
    # YAML close (1) + 1 before each of: overview, iter-1, iter-2, iter-3
    # = 5 total. Allow ≥ 4 to leave room for variations in trailing newline.
    assert sep_count >= 4, f"expected ≥4 slide separators, got {sep_count}"


# ---------------------------------------------------------------------------
# build-pptx-skill resolution
# ---------------------------------------------------------------------------

def test_find_build_pptx_returns_real_path():
    """The default search paths should locate build-pptx in a normal
    superstack checkout. If it can't, the helper raises SystemExit."""
    path = bp._find_build_pptx()
    assert path.is_file()
    assert path.name == "build.py"
