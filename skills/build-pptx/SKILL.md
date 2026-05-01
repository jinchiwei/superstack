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

- `--no-cover` — suppress title slide
- `--no-end` — suppress closing "Thanks" slide

## Markdown format

- YAML frontmatter at top populates the title slide (same fields as build-pdf/build-docx)
- `---` (horizontal rule) separates slides
- First H1/H2 of each slide chunk becomes the slide title
- Bullets (`-` lists) render as bulleted lines on the slide
- Paragraphs render as body prose

## Slide masters available (Python API)

`new_presentation()`, `add_title_slide`, `add_content_slide`, `add_section_divider`, `add_big_number_slide`, `add_two_column_slide`, `add_quote_slide`, `add_end_slide`. See `build.py` for signatures. v1's main() only auto-uses title + content + end; specialized masters are callable from custom Python.

## Branding source of truth

`~/arcadia/superstack/skills/_shared/branding.py`.
