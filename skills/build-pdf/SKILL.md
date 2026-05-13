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

## Research-writeup markdown recipe

The same markdown source that produces clean build-pptx decks (see `build-pptx/SKILL.md`) also produces clean PDF manuscripts, with these conventions:

### Frontmatter

Use the shared spec shown above (title / eyebrow / subtitle / name / org / date). Cover page renders all six fields; name in turquoise per brand spec.

### Heading hierarchy

- `# H1` → top-level section. Auto-colored per keyword classifier (Introduction → turquoise, Methods → deeppink, Results → amber/gold, Discussion → blueviolet).
- `## H2` → subsection.
- `### H3` → block label / stats group / sub-subsection.

### Figure embedding

Place figures in a sibling `figures/` directory and reference via relative paths:

```markdown
![Figure 1. Whole-brain FW vs CDR-SB by APOE4 dose.](figures/figure_1.png)
```

WeasyPrint renders the image at full content width with alt text as a centered caption below. The renderer resolves images relative to the markdown's location.

### Tables

Pipe-syntax tables render with branded styling (Geist Mono headers, alternating row tint). Use for results tables, demographics, etc.:

```markdown
| Test | n | β | p |
|---|---|---|---|
| AT3 | 81 | +0.0097 | 6.6e-4 |
```

### TOC and bookmarks

Pass `--toc` for a visible TOC page; PDF bookmarks are always on regardless (sidebar in any modern viewer). H1/H2/H3 all become bookmark levels.

### Watermark for drafts

Pass `--watermark DRAFT` for review copies — diagonal across every page. Drop the flag for the final submission build.

### Image paths — relative to the markdown file

Same rule as build-pptx and build-docx: relative paths only, anchored to the markdown's directory.

## Invocation pattern

```bash
python ~/arcadia/superstack/skills/build-pdf/build.py \
  --input <markdown> \
  --output <pdf>
```

## Branding source of truth

All colors and fonts come from `~/arcadia/superstack/skills/_shared/branding.py`. Edit that file to change the palette globally for build-pdf, build-pptx, and build-docx.

## First-time setup (CJK fonts)

If your docs contain Chinese, Japanese, or Korean characters, run the setup script once:

```bash
bash ~/arcadia/superstack/skills/build-pdf/setup.sh
```

This installs Noto Sans CJK (`brew install --cask font-noto-sans-cjk` on macOS) and writes `~/.config/fontconfig/fonts.conf` to make WeasyPrint prefer Noto over the macOS-bundled CJK fonts (PingFang, Heiti, Hiragino, Songti, ST*).

**Why this matters:** WeasyPrint embeds macOS CJK fonts as OpenType-CFF subsets that some PDF viewers (notably PDFgear) can't render — characters appear blank even though the font is properly embedded. Noto Sans CJK renders reliably across every viewer tested. Idempotent and safe to re-run.
