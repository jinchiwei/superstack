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

## First-time setup (CJK fonts)

If your docs contain Chinese, Japanese, or Korean characters, run the setup script once:

```bash
bash ~/arcadia/superstack/skills/build-pdf/setup.sh
```

This installs Noto Sans CJK (`brew install --cask font-noto-sans-cjk` on macOS) and writes `~/.config/fontconfig/fonts.conf` to make WeasyPrint prefer Noto over the macOS-bundled CJK fonts (PingFang, Heiti, Hiragino, Songti, ST*).

**Why this matters:** WeasyPrint embeds macOS CJK fonts as OpenType-CFF subsets that some PDF viewers (notably PDFgear) can't render — characters appear blank even though the font is properly embedded. Noto Sans CJK renders reliably across every viewer tested. Idempotent and safe to re-run.
