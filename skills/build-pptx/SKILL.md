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

## Layout-plan modes (v4)

`/build-pptx <markdown>` checks for a `<input>.md.layout.json` sidecar next to the input markdown and behaves differently depending on what it finds and which flag is passed:

- **Default — sidecar present, content unchanged:** the cached layout choices replay deterministically. ~2 sec render. Same input markdown + same sidecar → same pptx.

- **Default — sidecar present, slides added/edited:** entries with matching `content_hash` keep their cached layout; new or changed slides get default layouts inferred from their structure. The sidecar is updated in place.

- **Default — sidecar absent:** a default plan is inferred from chunk structure (mirrors v3's rule-based dispatch) and written to the sidecar. Subsequent runs replay it.

- **`--shake`:** ignore any existing sidecar and regenerate the plan from scratch. Use when you want to reroll layout choices (after content changes, or just for variety).

- **`--plan-only`:** write the sidecar JSON but skip rendering the pptx. Use to inspect / hand-edit the plan before committing it.

- **`--no-plan`:** bypass the v4 plan path entirely; use the legacy rule-based renderer. Useful when you want a fast deterministic render without writing a sidecar (e.g., one-off kb-learning decks).

### Sidecar location

The sidecar lives at `<input>.layout.json` next to the source markdown — e.g., `talk.md` → `talk.md.layout.json`. Commit it alongside the markdown so the deck is reproducible across machines and across time.

### Layout catalog

The renderer dispatches to one of these layouts per slide based on the plan entry's `kind`:

| kind | use for |
|---|---|
| `content-text` | text-only slides (paragraphs / bullets) |
| `content-text-image` | 1 image + supporting text (side-by-side or stacked by aspect) |
| `content-image-only` | 1+ images, no body text |
| `cards-grid` | 3+ uniform cards (e.g., definition lists) |
| `cards-heterogeneous` | 1 large primary card + 2-3 smaller |
| `three-pillars` | 3-column comparison with optional arrow connectors |
| `stat-callouts-right` | chart left + stat tiles right (funding-report style) |
| `bg-flip` | dark navy bg + white text — emphasis through inversion |
| `timeline` | horizontal timeline with milestones |
| `section-divider` | navy section break (auto-emitted on H1) |

See `plan_prompt.md` for the full param schemas and decision rubric.

## Branding source of truth

`~/arcadia/superstack/skills/_shared/branding.py`.
