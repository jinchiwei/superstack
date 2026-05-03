"""Tests for skills/build-xlsx/md_parser.py.

Verifies that the markdown parser correctly extracts sheets, tables,
prose blocks, frontmatter metadata, and semantic markers.

sys.path is configured by conftest.py in this directory.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from md_parser import (
    parse_markdown,
    parse_cell_marker,
    MARKER_WINNER,
    MARKER_DEFERRED,
    MARKER_WARNING,
    MARKER_HEADLINE,
    SheetSpec,
    TableSpec,
    ProseBlock,
)

# ---------------------------------------------------------------------------
# Fixture paths
# ---------------------------------------------------------------------------
_FIXTURES = Path(__file__).resolve().parent
FIXTURE_SIMPLE   = _FIXTURES / "fixture_simple_table.md"
FIXTURE_MULTI    = _FIXTURES / "fixture_multi_sheet.md"
FIXTURE_MARKERS  = _FIXTURES / "fixture_markers.md"


# ---------------------------------------------------------------------------
# parse_cell_marker unit tests
# ---------------------------------------------------------------------------

class TestParseCellMarker:
    def test_winner_marker_extracted(self):
        marker, text = parse_cell_marker("[winner] Best model")
        assert marker == MARKER_WINNER
        assert text == "Best model"

    def test_deferred_marker_extracted(self):
        marker, text = parse_cell_marker("[deferred] Not yet done")
        assert marker == MARKER_DEFERRED
        assert text == "Not yet done"

    def test_warning_marker_extracted(self):
        marker, text = parse_cell_marker("[warning] Degraded performance")
        assert marker == MARKER_WARNING
        assert text == "Degraded performance"

    def test_headline_marker_extracted(self):
        marker, text = parse_cell_marker("[headline] Key finding")
        assert marker == MARKER_HEADLINE
        assert text == "Key finding"

    def test_no_marker_returns_none(self):
        marker, text = parse_cell_marker("plain cell value")
        assert marker is None
        assert text == "plain cell value"

    def test_case_insensitive(self):
        marker, text = parse_cell_marker("[WINNER] something")
        assert marker == MARKER_WINNER

    def test_empty_string(self):
        marker, text = parse_cell_marker("")
        assert marker is None

    def test_marker_with_no_trailing_text(self):
        marker, text = parse_cell_marker("[winner]")
        assert marker == MARKER_WINNER
        assert text == ""


# ---------------------------------------------------------------------------
# Frontmatter tests
# ---------------------------------------------------------------------------

class TestFrontmatter:
    def test_simple_table_frontmatter(self):
        result = parse_markdown(FIXTURE_SIMPLE.read_text())
        assert result.meta.get("title") == "Simple Table Fixture"
        assert result.meta.get("date") == "2026-04-22"

    def test_multi_sheet_frontmatter(self):
        result = parse_markdown(FIXTURE_MULTI.read_text())
        assert result.meta.get("title") == "Q3 Experiment Matrix"
        assert result.meta.get("subtitle") == "All-up status across initiatives"

    def test_no_frontmatter(self):
        result = parse_markdown("# Sheet One\n\n| A | B |\n|---|---|\n| 1 | 2 |\n")
        assert result.meta == {}


# ---------------------------------------------------------------------------
# Sheet structure tests
# ---------------------------------------------------------------------------

class TestSheetStructure:
    def test_simple_table_one_sheet(self):
        result = parse_markdown(FIXTURE_SIMPLE.read_text())
        assert len(result.sheets) == 1
        assert result.sheets[0].name == "Results"

    def test_multi_sheet_three_sheets(self):
        result = parse_markdown(FIXTURE_MULTI.read_text())
        assert len(result.sheets) == 3
        names = [s.name for s in result.sheets]
        assert "Architecture Sweep" in names
        assert "Hyperparameter Tuning" in names
        assert "Future Directions" in names

    def test_sheet_name_truncated_to_31_chars(self):
        long_name = "A" * 40
        result = parse_markdown(f"# {long_name}\n\n| col |\n|-----|\n| val |\n")
        assert len(result.sheets[0].name) <= 31

    def test_empty_markdown_produces_zero_sheets(self):
        result = parse_markdown("")
        assert result.sheets == []

    def test_content_before_h1_gets_default_sheet(self):
        md = "---\ntitle: My Doc\n---\n\nSome prose here.\n"
        result = parse_markdown(md)
        assert len(result.sheets) == 1
        assert result.sheets[0].name == "My Doc"


# ---------------------------------------------------------------------------
# Table parsing tests
# ---------------------------------------------------------------------------

class TestTableParsing:
    def test_simple_table_headers(self):
        result = parse_markdown(FIXTURE_SIMPLE.read_text())
        table = result.sheets[0].tables[0]
        assert table.headers == ["Model", "Accuracy", "F1", "Notes"]

    def test_simple_table_row_count(self):
        result = parse_markdown(FIXTURE_SIMPLE.read_text())
        table = result.sheets[0].tables[0]
        assert len(table.rows) == 3

    def test_simple_table_cell_values(self):
        result = parse_markdown(FIXTURE_SIMPLE.read_text())
        table = result.sheets[0].tables[0]
        first_row = table.rows[0]
        assert first_row[0].value == "ResNet18"
        assert first_row[1].value == "0.87"

    def test_multi_sheet_table_counts(self):
        result = parse_markdown(FIXTURE_MULTI.read_text())
        sheets = {s.name: s for s in result.sheets}
        assert len(sheets["Architecture Sweep"].tables) == 1
        assert len(sheets["Hyperparameter Tuning"].tables) == 1


# ---------------------------------------------------------------------------
# Prose block tests
# ---------------------------------------------------------------------------

class TestProseBlocks:
    def test_prose_in_multi_sheet(self):
        result = parse_markdown(FIXTURE_MULTI.read_text())
        sheets = {s.name: s for s in result.sheets}
        hpo_sheet = sheets["Hyperparameter Tuning"]
        # Should have a prose block (the paragraph before the table)
        assert len(hpo_sheet.prose) >= 1
        assert any("CaFormer" in pb.text for pb in hpo_sheet.prose)


# ---------------------------------------------------------------------------
# Marker detection tests
# ---------------------------------------------------------------------------

class TestMarkerDetection:
    def test_markers_detected_in_fixture(self):
        result = parse_markdown(FIXTURE_MARKERS.read_text())
        sheets = {s.name: s for s in result.sheets}
        table = sheets["Experiment Status"].tables[0]

        # Row 0: [winner] CaFormer + BCE
        assert table.rows[0][0].marker == MARKER_WINNER
        assert table.rows[0][0].value == "CaFormer + BCE"

        # Row 2: [warning]
        assert table.rows[2][0].marker == MARKER_WARNING

        # Row 3: [deferred]
        assert table.rows[3][0].marker == MARKER_DEFERRED

        # Row 4: [headline]
        assert table.rows[4][0].marker == MARKER_HEADLINE

    def test_plain_rows_have_no_marker(self):
        result = parse_markdown(FIXTURE_MARKERS.read_text())
        sheets = {s.name: s for s in result.sheets}
        table = sheets["Experiment Status"].tables[0]
        # Row 1: plain ResNet18 row
        assert table.rows[1][0].marker is None
