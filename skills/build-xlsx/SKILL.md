---
name: build-xlsx
description: Turn any markdown file into a Jin-branded xlsx workbook. Each H1 heading becomes one sheet. Plain tables get default brand styling (ink/white header, paper alternating rows, frozen header). Optional bracket-prefix markers ([winner] / [deferred] / [warning] / [headline]) apply semantic fills and embed FA glyph icons in the cell. Use for data tables, project trackers, ablation summaries, scorecards, status dashboards — any structured data you want in your style. Voice triggers: "branded xlsx", "build xlsx", "make me a spreadsheet in my style", "export this table in my brand".
---

# /build-xlsx

Markdown → Jin-branded xlsx via openpyxl.

## When to invoke

User asks to make an xlsx (or spreadsheet) from a markdown file AND either explicitly mentions branding ("in my style", "branded", "with my colors") OR the content is something Jin owns (research tables, ablation results, status dashboards, project trackers).

Distinct from autoresearch's scorecard builder, which now uses build-xlsx internally for the styling pipeline.

## Required arguments

- `--input PATH` — path to source markdown file
- `--output PATH` — desired xlsx output path

## Optional flags

- `--no-title-bar` — skip the H1 title bar row at the top of each sheet
- `--no-frozen-header` — do not freeze the header row
- `--no-glyphs` — style marker rows but do not embed FA glyph icons

## Invocation pattern

```bash
python ~/arcadia/superstack/skills/build-xlsx/build.py \
  --input <markdown> \
  --output <xlsx>
```

## Input format

### Frontmatter (optional)

```yaml
---
title: "Q3 experiment matrix"
subtitle: "All-up status across initiatives"
date: "2026-04-22"
---
```

### H1 → sheet mapping

Each `# H1` heading becomes one sheet. Sheet name = H1 text, truncated to 31 characters (Excel limit).

```markdown
# Architecture Sweep

| Backbone | Loss | Val AUC |
|----------|------|---------|
| ResNet18 | BCE  | 0.871   |
| CaFormer | BCE  | 0.931   |

# Hyperparameter Tuning

| Run | LR   | Val AUC |
|-----|------|---------|
| 1   | 1e-3 | 0.921   |
```

### Prose sections

A paragraph that isn't a table is rendered as a text region starting in column A:

```markdown
# Notes

These results were obtained on the held-out test split.
Do not compare directly to the validation numbers above.

| ...table continues... |
```

## Semantic markers

Bracket-prefix labels at the start of a table cell apply semantic styling.

| Marker | Fill | Text | FA glyph (default on) |
|--------|------|------|----------------------|
| `[winner] ...` | Turquoise #40E0D0 | Ink, bold | FaTrophy |
| `[deferred] ...` | Light grey #E8E8E8 | Ink | FaForward |
| `[warning] ...` | Amber #F0C840 | Ink, bold | FaTriangleExclamation |
| `[headline] ...` | Deeppink #FF1493 | White, bold | FaStar |

The `[label]` prefix is stripped from the rendered cell text. Markers are case-insensitive.

Example:

```markdown
| Experiment | Result | Notes |
|------------|--------|-------|
| [winner] CaFormer + BCE | 0.931 | best |
| ResNet18 + BCE | 0.871 | baseline |
| [warning] ViT-B + Focal | 0.812 | below threshold |
| [deferred] Swin + BCE | — | not yet attempted |
```

## Default styling

- **Header row**: ink `#14141C` bg, white text, bold, 11pt Geist Mono
- **Data rows**: alternating PAPER `#FAFAFC` and WHITE bg, ink text, 11pt Geist
- **Frozen panes**: just below header row
- **Title bar**: row 1 of each sheet, ink bg / white text bold — sheet H1 as title
- **Column widths**: auto-sized from max content length, capped at 40 chars
- **Sheet tab color**: Turquoise `#40E0D0`

## Branding source of truth

All colors come from `~/arcadia/superstack/skills/_shared/branding.py`. Styling helpers come from `skills/_shared/branding_xlsx.py`. FA icons come from `skills/_shared/icons/`.

## Limitations (v1)

- No chart support
- No formula support
- No merged-cell control beyond the title bar row
- Each H1 produces exactly one sheet (H2+ headings are ignored structurally)
- Multiple tables in one H1 section are stacked sequentially on the same sheet

## Relationship to autoresearch

autoresearch's `_build_xlsx.py` scorecard builder imports its styling primitives from `skills/_shared/branding_xlsx.py` — the same module build-xlsx uses. The scorecard-specific sheet structure (Matrix, Per-task, HPO detail, etc.) remains in autoresearch; the brand styling layer is shared.
