"""Markdown → structured sheet data parser for build-xlsx.

Parses a markdown document with optional YAML frontmatter into a list of
SheetSpec objects.  Each H1 heading becomes one sheet; tables within that
section become data rows; non-table paragraphs become prose regions.

Marker syntax (bracket prefix at the start of a cell value):
  [winner] ...     → MARKER_WINNER
  [deferred] ...   → MARKER_DEFERRED
  [warning] ...    → MARKER_WARNING
  [headline] ...   → MARKER_HEADLINE

The marker label is stripped from the rendered text; only the rest of the
cell content is kept.

Public API:
  parse_markdown(text: str) -> ParseResult
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Marker constants
# ---------------------------------------------------------------------------

MARKER_WINNER   = "winner"
MARKER_DEFERRED = "deferred"
MARKER_WARNING  = "warning"
MARKER_HEADLINE = "headline"

_KNOWN_MARKERS = {MARKER_WINNER, MARKER_DEFERRED, MARKER_WARNING, MARKER_HEADLINE}

# Regex to detect a bracket marker at the start of a cell value.
# Matches [winner], [deferred], [warning], [headline] (case-insensitive).
_MARKER_RE = re.compile(r"^\[(" + "|".join(_KNOWN_MARKERS) + r")\]\s*", re.IGNORECASE)


def parse_cell_marker(raw: str) -> tuple[Optional[str], str]:
    """Return (marker_name, cleaned_text) from a raw cell string.

    If no marker is found, marker_name is None and cleaned_text is raw.
    """
    m = _MARKER_RE.match(raw.strip())
    if m:
        marker = m.group(1).lower()
        text = raw.strip()[m.end():]
        return marker, text
    return None, raw


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class CellData:
    """A single table cell with optional semantic marker."""
    value: str
    marker: Optional[str] = None   # one of MARKER_* or None


@dataclass
class TableSpec:
    """A parsed markdown table."""
    headers: list[str]           # header row values
    rows: list[list[CellData]]   # data rows (each row = list of CellData)


@dataclass
class ProseBlock:
    """A non-table paragraph or text block within a sheet section."""
    text: str


@dataclass
class SheetSpec:
    """All content for one sheet (one H1 → one sheet)."""
    name: str                               # sheet name (H1 text, max 31 chars)
    tables: list[TableSpec] = field(default_factory=list)
    prose: list[ProseBlock] = field(default_factory=list)
    # blocks in order (TableSpec | ProseBlock) — preserves relative ordering
    blocks: list = field(default_factory=list)


@dataclass
class ParseResult:
    """Top-level parse result."""
    meta: dict                              # frontmatter key/value pairs
    sheets: list[SheetSpec]                 # one per H1 heading


# ---------------------------------------------------------------------------
# YAML frontmatter parser (no dependency on PyYAML)
# ---------------------------------------------------------------------------

def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Extract YAML frontmatter (if present) and return (meta_dict, body).

    Only handles scalar string values (sufficient for title/subtitle/date).
    """
    meta: dict = {}
    if not text.startswith("---"):
        return meta, text

    end = text.find("\n---", 3)
    if end == -1:
        return meta, text

    fm_block = text[3:end].strip()
    body = text[end + 4:].lstrip("\n")

    for line in fm_block.splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key:
            meta[key] = val

    return meta, body


# ---------------------------------------------------------------------------
# Table parser
# ---------------------------------------------------------------------------

def _parse_table_block(lines: list[str]) -> Optional[TableSpec]:
    """Parse a list of raw table lines into a TableSpec. Returns None on failure."""
    # At minimum we need a header row + separator row
    if len(lines) < 2:
        return None

    def _split_row(line: str) -> list[str]:
        """Split a pipe-delimited table row into cell strings."""
        parts = line.strip().strip("|").split("|")
        return [p.strip() for p in parts]

    # Check that row 1 is a separator (only hyphens and pipes and colons)
    sep_re = re.compile(r"^[\s|:\-]+$")
    if len(lines) < 2 or not sep_re.match(lines[1]):
        return None

    header_cells = _split_row(lines[0])
    data_rows: list[list[CellData]] = []

    for line in lines[2:]:
        if not line.strip():
            continue
        raw_cells = _split_row(line)
        # Pad or truncate to match header count
        while len(raw_cells) < len(header_cells):
            raw_cells.append("")
        raw_cells = raw_cells[: len(header_cells)]

        row: list[CellData] = []
        for raw in raw_cells:
            marker, text = parse_cell_marker(raw)
            row.append(CellData(value=text, marker=marker))
        data_rows.append(row)

    if not header_cells:
        return None

    return TableSpec(headers=header_cells, rows=data_rows)


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------

def parse_markdown(text: str) -> ParseResult:
    """Parse a markdown string into a ParseResult.

    Each H1 heading (# Title) becomes a SheetSpec.  Content between H1s
    (tables + prose) is attached to the most recent sheet.  Content before
    the first H1 is attached to a default sheet named from frontmatter title
    or 'Sheet 1' if no title present.
    """
    meta, body = _parse_frontmatter(text)
    lines = body.splitlines()

    sheets: list[SheetSpec] = []
    current_sheet: Optional[SheetSpec] = None

    i = 0
    table_buffer: list[str] = []

    def _flush_table():
        nonlocal table_buffer
        if table_buffer and current_sheet is not None:
            ts = _parse_table_block(table_buffer)
            if ts is not None:
                current_sheet.tables.append(ts)
                current_sheet.blocks.append(ts)
        table_buffer = []

    def _flush_prose(text: str):
        text = text.strip()
        if text and current_sheet is not None:
            pb = ProseBlock(text=text)
            current_sheet.prose.append(pb)
            current_sheet.blocks.append(pb)

    prose_buffer: list[str] = []

    def _flush_prose_buffer():
        nonlocal prose_buffer
        if prose_buffer:
            _flush_prose("\n".join(prose_buffer))
        prose_buffer = []

    while i < len(lines):
        line = lines[i]

        # H1 heading → new sheet
        h1_match = re.match(r"^#\s+(.+)$", line)
        if h1_match:
            _flush_table()
            _flush_prose_buffer()
            sheet_name = h1_match.group(1).strip()[:31]  # Excel 31-char limit
            current_sheet = SheetSpec(name=sheet_name)
            sheets.append(current_sheet)
            i += 1
            continue

        # Skip H2+ headings (only H1 creates sheets)
        if re.match(r"^#{2,}\s+", line):
            _flush_table()
            _flush_prose_buffer()
            i += 1
            continue

        # Table row detection: starts with |
        if line.strip().startswith("|"):
            _flush_prose_buffer()
            table_buffer.append(line)
            i += 1
            # Consume until the table ends (no more | lines)
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_buffer.append(lines[i])
                i += 1
            _flush_table()
            continue

        # Blank line: separates blocks
        if not line.strip():
            if prose_buffer:
                _flush_prose_buffer()
            i += 1
            continue

        # Prose line
        if current_sheet is None:
            # Content before first H1: create a default sheet
            default_name = meta.get("title", "Sheet 1")[:31]
            current_sheet = SheetSpec(name=default_name)
            sheets.append(current_sheet)

        prose_buffer.append(line)
        i += 1

    # Flush any remaining buffers
    _flush_table()
    _flush_prose_buffer()

    return ParseResult(meta=meta, sheets=sheets)
