---
name: build-pptx
description: Turn any markdown file into a Jin-branded PPTX (16:9, dark title + closing slides, white content, all-Geist-Mono headings, slide separation by `---`). Optional flags for suppressing cover or end slide. Use for research talks, conference presentations, lab meetings — slide decks where Jin's branding matters. Distinct from generic / template-y PowerPoint output. Voice triggers: "branded pptx", "build pptx", "slide deck in my style", "presentation".
---

# /build-pptx

Markdown → Jin-branded 16:9 PPTX via python-pptx.

## When to invoke

User asks to make slides from markdown for a research talk, lab meeting, conference presentation, or any deck that should be in Jin's brand identity.

## Default: generate custom intro figures (research decks)

For any **research-talk deck** — lab talks, conference talks, defenses, seminars, autoresearch reports — generating **3–5 custom matplotlib figures redrawing foundational reference papers** for the intro / background / motivation section is the **default**, not an extra. Each figure has clear "(adapted from Author Year)" attribution in its title. Follow [`intro_figures.md`](intro_figures.md) for the pattern + archetype catalog + code template + the reference implementation. Do not deliver a research deck with bullet-only intro slides.

**Opt out** when the audience already knows the work — internal status updates, sprint reviews, "team weekly" decks, follow-up program decks for the same lab, or any deck where ≥ 3 background slides would be over-explanation. Opt-out signals (any one):
- User says "skip intro figures" / "no intro figures" / "internal deck, no background"
- Deck frontmatter has `no_intro_figures: true`
- The deck is for a strictly internal audience the user identifies (e.g. "weekly to my team")

If the request is ambiguous, default to generating intro figures and ask the user post-build whether to keep or strip them.

## Default: every results slide ships with a representative data figure

For any slide that headlines a quantitative finding (β, OR, ratio, p-value, mean difference, etc.) in a research-talk deck, **the slide MUST pair the headline number with a figure showing the underlying data** — scatter + regression line, forest plot, longitudinal trajectory, bar chart with error bars, etc. Big-stat-only slides with bullet points are a regression. See [`results_figures.md`](results_figures.md) for the layout pattern (compact hero stat left + dominant data figure right), acceptable figure types per finding shape, and how to handle existing-figure vs need-to-regenerate cases.

**For the figure itself**: hand-roll each figure in matplotlib, bespoke to the data, dark/brand-locked (consistent palette + Geist/Geist Mono, slide-matched background). There is no archetype library — design each figure to its content.

**Non-results slides need figures too**: methods, motivation, intended-use, study-design, and recommendation slides should carry a bespoke **explanatory diagram** (pipeline/flow, method schematic, cohort funnel, concept map) — not a grid of text cards or a step-rail. See [`bespoke_design.md`](bespoke_design.md) → *Concept figures*.

Use the figures the experiment scripts already produce (typically under `results/<date>_<scope>/<analysis>/figures/`) — copy/symlink them into the deck's `figures/` dir with a result-oriented name. Don't redraw if a clean version exists. If no figure exists for a finding, regenerate from the underlying summary CSV using the canonical `mpl_style` + the deck theme.

## Default: ship comprehensive speaker notes

Every deck ships with **comprehensive, didactic speaker notes** in the PowerPoint notes pane (Presenter View) — this is canonical, not optional. Put each slide's notes in its sidecar `params["notes"]`; `render.py` embeds them automatically (content slides + dividers). Notes must TEACH the slide — explain the concept in plain language for a presenter who's a little lost, translate the numbers to intuition, and give the transition. See [`speaker_notes.md`](speaker_notes.md). A non-fatal build warning lists content slides missing notes. Opt out only if the user says "no notes."

## Default: rich "Thank You" closing slide

The auto end slide is a branded **Thank-You** slide (replaces the old generic "Thanks"): big deeppink "Thank You", the presenter's name with **Chinese name over English, both turquoise**, email in amber, and the 夢想 identity logos (`assets/meng.png` + `assets/xiang.png`) lower-right. It pulls `name`/`org` from frontmatter; `name_cjk` and `email` fall back to the tool owner's defaults. Override per deck via frontmatter (`name:`, `org:`, `name_cjk:`, `email:`); set `email: ""` or `name_cjk: ""` to omit either. Suppress the whole slide with `--no-end`.

## Required arguments

- `--input PATH` — markdown source
- `--output PATH` — output PPTX path

## Optional flags

- `--no-cover` — suppress title slide
- `--no-end` — suppress closing "Thanks" slide
- `--use-blocks=auto|never|always` — control when `composition`/`freeform` layouts are admissible (default: `auto`)
- `--mode=expressive|strict` — default `expressive` (bespoke). `strict` (named layouts) is **opt-in only** — pass it explicitly; never a default or silent fallback. See [Construction mode](#construction-mode--bespoke-by-default-strict-is-opt-in-only).
- `--allow-composed` — bypass the bespoke gate and ship the agentless composer FLOOR. Non-interactive / cron use ONLY (see below). An agent in the loop must NOT pass this — handcraft instead.
- `--qa` — after rendering, emit per-slide PNGs for visual inspection. See [Visual QA loop](#visual-qa-loop---qa).

> **ENFORCEMENT (expressive mode):** a real render **aborts with a non-zero exit and writes no `.pptx`** if any content slide is still the agentless composer FLOOR (`params._provenance == "composer"`). You MUST handcraft each content slide's freeform `code` and set `params._provenance = "agent"` — see [`bespoke_design.md`](bespoke_design.md). The only escape is `--allow-composed` (cron/non-interactive). This is a hard, cross-machine gate, not advice.

## Markdown format

- YAML frontmatter at top populates the title slide (same fields as build-pdf/build-docx)
- `---` (horizontal rule) separates slides
- First H1/H2 of each slide chunk becomes the slide title
- Bullets (`-` lists) render as bulleted lines on the slide
- Paragraphs render as body prose

## Research-deck markdown recipe

A well-shaped markdown source dispatches to the rich layouts automatically (figure-with-aside, cards-triple, conclusions). A poorly-shaped one falls through to bullet-only `content-text`. The patterns below produce manuscript-prep / talk-grade research decks reliably.

### Frontmatter — populate everything

```yaml
---
title: "<paper-style title>"
eyebrow: "<PROJECT · STAGE · YEAR>"   # small caps tag above title
subtitle: "<one-line orientation>"
name: "<Author Name>"                  # renders in turquoise on the cover
org: "<Lab / Affiliation>"
date: "YYYY-MM-DD"
---
```

### Section dividers — one `# H1` per arc

`# H1` auto-emits a navy section-break slide colored via keyword classifier (Background → turquoise, Methods → deeppink, Results → amber/gold, Discussion → blueviolet, etc). Use one H1 per logical arc (Background → New analyses → Framing → Next steps). Don't use H1 for ordinary content.

### Figure slides — DO NOT mix `### H3` cards with images

The auto-inferrer dispatches `figure-with-aside` only when the chunk has exactly one image, no tables, no `### H3` cards, and a non-empty lede or body. **If you add `### Label` blocks to a figure slide, the cards-grid layout eats the image.** Right pattern:

```markdown
## My finding — one-line takeaway

Short lede paragraph (50-500 chars) framing the test.

![alt text](figures/local_relpath.png)

- **Headline number:** β = X.XX, p = Y.YY — interpretation
- **Sample size:** n = 268 / 285 with caveat
- **Verdict:** one-sentence conclusion
```

Wide panel composites (aspect ≥ 1.8) auto-route to `figure-with-aside-horizontal`; squarer figures route to `figure-with-aside` (figure left, aside card right). The score-based dispatch admits caption lengths up to ~1000 chars; keep the lede focused.

### Stats slides — `### H3` IS the card

For "3-4 short factual blocks" slides (cohort tables, conclusions, definitions), use H3 as the card label and let the body follow:

```markdown
## Where we are — RSNA 2026 abstract status

Optional lede sentence.

### FW–severity gradient
Whole-brain β = **+0.0091, p < 0.0001**. Slope p<0.05 in **11/11 regions**.

### APOE4 modulation
Carrier × CDR-SB interaction in **11/11 regions**. Whole-brain β = **+0.0054, p = 0.033**.

### Longitudinal × APOE4
AD cingulate β(time × APOE4) = **−0.0084, p = 0.0042**.
```

Each H3 becomes one card; 2-4 H3s dispatch to `cards-triple` (flat full-width row), 3+ with longer bodies to `cards-grid`, mixed long-and-short to `cards-heterogeneous`. **Never write `### cards`** as a literal marker — that produces a card labeled "cards".

### Bullet-only slides → conclusions / cards-triple

A slide with 2-5 plain bullets and no images/tables/cards auto-promotes to `cards-triple` so it doesn't render as sparse text. Bullets in the shape `**Label:** body` or `**Label** — body` get split into card label + body; plain bullets become body-only rows. Closing/Next-steps slides with bullet shape under a closing-section H1 (Conclusions / Next steps) auto-pick the `conclusions` layout (dark navy bg + per-card accent).

### Tables-only slides

A slide with a markdown table and no image dispatches to `table-with-takeaway`. Trailing prose / lede gets promoted to the dark accent callout footer.

### Image paths — relative to the markdown file

Stage figures in a sibling `figures/` directory next to the deck markdown and reference via relative paths (`![](figures/foo.png)`). Absolute paths can fail to be detected by the planner — observed empirically. The renderer chdirs to the markdown's directory before resolving images.

### Institutional logos on the title slide (multi-affiliation users)

Cover frontmatter only renders the byline; institutional logos need a post-build python-pptx pass. Pattern (UCSF + Cal example for paired-affiliation labs):

```python
from pathlib import Path
from pptx import Presentation
from pptx.util import Inches, Emu

REF_DIR = Path.home() / "arcadia" / "reference"
prs = Presentation("deck.pptx")
slide = prs.slides[0]
H = Inches(0.9); GAP = Inches(0.25)
# Scale primary logo +40% if its asset has heavy canvas padding
targets = [(REF_DIR / "primary-logo.png", Emu(int(H * 1.40))),
           (REF_DIR / "secondary-logo.png", H)]
# ... place lower-right, vertical-center aligned ...
prs.save("deck.pptx")
```

Full helper with positioning math is documented per-user (institutional logo PNG paths vary by lab). Default position: paired block in lower-right, ~0.5 in from slide right + bottom edges, vertically center-aligned.

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

- **`--use-blocks=auto`** (default): planner may pick `composition` or `freeform` when the decision rubric says appropriate.
- **`--use-blocks=never`**: forbid `composition` and `freeform` entirely; if a sidecar contains them the build aborts with a clear error. Use to enforce named-layout-only decks. To fix: delete the sidecar (or run `--shake`) and rerun, or pass `--use-blocks=auto`.
- **`--use-blocks=always`**: signal that the agent should prefer composition (useful for explicit experiments; does not force-rewrite an existing sidecar — only informs inline plan generation when no sidecar exists).

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
| `stats-with-takeaway` | 2-5 big-number stat tiles + dark accent-callout footer |
| `figure-with-aside` | figure left (weight 2) + commentary card right (weight 1) |
| `cards-with-takeaway` | N cards in a row + dark accent-callout footer |
| `table-with-takeaway` | full-width data table + dark accent-callout footer |
| `composition` | arbitrary rows × blocks (fallback when no named layout fits) |
| `section-divider` | navy section break (auto-emitted on H1) |

See `plan_prompt.md` for the full param schemas and decision rubric.

## When invoked: auto-generate the layout plan inline

When `/build-pptx <input.md>` runs, **before** invoking `python build.py`,
decide what to do based on flags + sidecar state:

| State | Action |
|---|---|
| `--no-plan` flag | Skip everything below; let `build.py --no-plan` use legacy v3 path. |
| Sidecar exists AND no `--shake` | Skip auto-generation; let `build.py` replay the cached layouts. |
| Sidecar absent OR `--shake` | **Generate the plan inline before rendering** (see steps below). |

### Inline plan generation steps

Run these in order whenever you need to (re)generate the sidecar:

1. **Read the source markdown.** Get its full text from `<input>.md`.
2. **Read `<skill_dir>/plan_prompt.md`** — the layout catalog, sandbox
   API, decision rubric, and worked examples. The skill_dir is the
   directory containing this `SKILL.md`.
3. **Walk slide chunks.** From the markdown's HTML body, split on `<hr>`
   to get one chunk per slide. For each chunk:
   - Derive a stable `slide_id` via `plan.derive_slide_ids_from_chunks`
   - Compute `content_hash = plan.hash_text(chunk_html)`
   - Note H1 (carries forward) and H2 (per-slide)
4. **Decide a layout `kind` per slide — this depends on the mode.**

   **Expressive mode (the default).** You HANDCRAFT each slide. **Read and
   follow `<skill_dir>/bespoke_design.md` — it mandates handcrafting every
   content slide from scratch, following NOTHING except the brand lock (fonts +
   brand-4 accents + the section-cycled colorbar). No menu, no template, no
   catalog.** Compose each slide's geometry yourself for its specific content
   (Anthropic-pptx aesthetic). There is **no named-layout-first rubric** and no "freeform as
   last resort" rule in expressive — that is strict-mode guidance and does NOT
   apply here. The 13 named kinds are optional tools you may reach for when a
   slide's content maps cleanly onto one (a real data table →
   `table-with-takeaway`); otherwise compose freely. **Do NOT pick from a fixed
   set of layouts — selecting from a catalog is strict mode with extra options,
   and it is the exact failure to avoid; handcraft each slide from the
   primitives for its content.** The ONLY hard constraints are the brand lock:
   fonts (Geist / Geist Mono) and the color palette (brand-4 accents + theme
   hues). **If a deck comes out looking like plain named layouts — or like every
   slide picked the same handful of compositions — you skipped the design step.
   That is the bug.** The deterministic `expressive_compose.py` composer is the
   floor for *agentless* renders only; when you (an agent) are building, you
   design bespoke instead.

   **Strict mode (`--mode=strict`).** Use the named-layout-first priority
   below: most slides should be one of the 13 named kinds (`content-text`,
   `cards-grid`, `content-text-image`, `content-image-only`,
   `cards-heterogeneous`, `three-pillars`, `stat-callouts-right`, `bg-flip`,
   `timeline`, `stats-with-takeaway`, `figure-with-aside`,
   `cards-with-takeaway`, `table-with-takeaway`). Reach for `composition` only
   when 2+ structurally distinct chunks can't fit one named layout, and
   `freeform` ONLY when no named layout AND no composition fits.
5. **For `freeform` slides, write the python snippet.** Use ONLY the
   sandbox API documented in `plan_prompt.md`. Important constraints:
   - No `import`, no dunder access, no `try`/`with`, no
     `eval`/`exec`/`open`/`getattr`/etc.
   - Stay inside the body region: `body_top, body_h, body_l, body_w`
   - Use brand colors (`accent_rgb`, `INK_RGB`, `TURQUOISE_RGB`, ...)
     and brand fonts (`MONO_FONT`, `SANS_FONT`)
   - Test mentally: does it respect the geometry? Does it use the
     listed primitives correctly?
6. **Write the JSON to `<input>.md.layout.json`.** Schema:
   ```json
   {
     "version": 1,
     "deck_md_hash": "<sha256 of the markdown>",
     "shake_seed": null,
     "slides": [
       {
         "slide_id": "h1-...",
         "kind": "content-text" | "freeform" | "section-divider" | ...,
         "params": { ... layout-specific ... },
         "content_hash": "<sha256 of the chunk HTML>"
       },
       ...
     ]
   }
   ```
   For section-divider entries, also include
   `params.accent_hex = "#xxxxxx"` (the renderer needs the hex string,
   not just the label) — look up via the keyword classifier on the H1
   text:
   - `branding.match_section_color(label)` returns the right hex.
7. **Invoke the renderer:**
   `python build.py --input <input.md> --output <output.pptx>`
   The renderer reads the sidecar you just wrote and renders.

### Layout selection priority (STRICT MODE ONLY)

> This priority and the "When to use `freeform`" guidance below apply to
> **strict mode**. In **expressive** (the default) you design freeform-first —
> see step 4 above and `plan_prompt.md`'s construction-modes section.

Apply in this order:
1. **Named layouts first** (all 13 of them — see catalog above). Deterministic, brand-locked, consistent.
2. **`composition` as fallback** — only when the slide has 2+ structurally distinct content chunks that no single named layout captures.
3. **`freeform` as last resort** — only for genuinely bespoke geometry (custom arrows, unusual stat arrangements) that no named layout and no reasonable composition can express.

A strict deck that reaches for `composition` or `freeform` on most slides is drifting from brand. Stick to named layouts.

### When to use `freeform` vs named layouts (strict mode)

In strict mode, default to named layouts. Reach for `freeform` only for slides where:
- A chart pairs with stat callouts in a way `stat-callouts-right` doesn't
  capture (custom positions, non-uniform tiles, annotation arrows)
- 3 things compare side-by-side with arrows or connectors
- A single big number with custom flanking annotations
- Anything genuinely bespoke that would lose its shape if forced into a
  named template

Skip `freeform` for slides that fit `content-text` / `cards-grid` /
`content-text-image` / `stats-with-takeaway` / `cards-with-takeaway` /
`table-with-takeaway` / `figure-with-aside` — determinism and consistency
are easier with named layouts.

### When validation fails

If a freeform snippet is rejected by the AST validator at render time, the
slide renders with a visible deeppink error chip:
```
[freeform code rejected: <reason>]
```
Read the error, fix the snippet in the sidecar, re-run. Same for runtime
errors:
```
[freeform runtime error: <ExceptionType>: <message>]
```

The deck always renders to completion — a single bad slide doesn't crash
the whole deck.

### Examples

For a slide that fits `cards-grid`:
```json
{
  "slide_id": "h1-methodology/h2-cohorts",
  "kind": "cards-grid",
  "params": {
    "title": "Cohorts",
    "lede": "...",
    "cards": [{"label": "UCSF", "body": "n=100"}, ...],
    "section_label": "Methodology"
  },
  "content_hash": "..."
}
```

For a bespoke slide that needs custom geometry:
```json
{
  "slide_id": "h1-results/h2-headline",
  "kind": "freeform",
  "params": {
    "title": "Headline AUC",
    "lede": "Site-mixed external eval, 5-seed mean.",
    "section_label": "Results",
    "code": "_add_text(slide, '0.848', left=body_l, top=body_top + 0.5, width=body_w, height=2.5, size=120, color_rgb=accent_rgb, font=MONO_FONT, bold=True, align=PP_ALIGN.CENTER)\n_add_text(slide, '± 0.040 across 5 seeds', left=body_l, top=body_top + 3.2, width=body_w, height=0.5, size=18, color_rgb=MUTED_RGB, font=SANS_FONT, align=PP_ALIGN.CENTER)"
  },
  "content_hash": "..."
}
```

For a section divider, you must set `accent_hex`:
```json
{
  "slide_id": "divider-h1-results",
  "kind": "section-divider",
  "params": {
    "label": "Results",
    "accent_hex": "#F0C840"
  },
  "content_hash": "..."
}
```

## Construction mode — bespoke by default; strict is opt-in only

**`expressive` (bespoke) is the DEFAULT and the only mode you get unless you ask otherwise.** The planner DESIGNS each slide freely (freeform-first, Anthropic-pptx aesthetic), with NO deterministic layout-selection rubric. The only hard constraints are the brand lock: fonts (Geist / Geist Mono) and the color palette (brand-4 accents + the theme's supplementary hues). Named layouts are optional tools the planner may use when content cleanly fits one; everything else is its call. A theme is auto-picked (seeded by `shake_seed`) and frozen into the sidecar.

**`strict` (rules-based named layouts) is OPT-IN ONLY.** It is honored **only** when you pass `--mode=strict` explicitly on that invocation. It is **never** the default and is **never** silently inferred — there is no auto-revert to strict. On a plain re-render with no flag, a sidecar that recorded `strict` keeps it (determinism — it only got there by a deliberate earlier choice); omitting the flag on a fresh deck always yields expressive.

An agent in the loop must NOT reach for strict, `--no-plan` (legacy v3 renderer), or `--allow-composed` (agentless floor) on its own — those produce non-bespoke output and exist only for explicit user request / non-interactive cron. Default behavior is always bespoke. The "strict mode" guidance in some sections below (named-layout-first priority) applies ONLY when the user explicitly opted into strict.

## Visual QA loop (`--qa`)

`--qa` renders the deck, then converts it to one PNG per slide under `<output>_qa/` (e.g. `talk.pptx` → `talk_qa/slide-1.png`, ...). The pipeline is pptx → PDF (LibreOffice headless) → per-slide PNGs (poppler `pdftoppm`); python-pptx cannot rasterize, so we shell out.

The agent driving the loop should:
1. **Read each PNG** under `<output>_qa/`.
2. Check it against the **Design principles / anti-patterns** in `plan_prompt.md` and theme cohesion (consistent accent use, hierarchy, no crowding/overflow).
3. **Edit the `.layout.json` sidecar** to fix any issues, then re-run (`python build.py --input ... --output ... --qa`).
4. Repeat until the slides pass. Determinism holds — fixes are frozen in the sidecar, so a re-render reproduces the corrected deck.

### Dependencies

- **LibreOffice** (`soffice`) — `brew install --cask libreoffice` on mac.
- **poppler** (`pdftoppm`) — `brew install poppler` on mac.

If either is missing, `--qa` prints `QA skipped: <actionable message>` to stderr and the build still succeeds.

On a no-sudo cluster (FAC/SCS), use an extracted LibreOffice AppImage placed in a **non-home** location — home dirs are quota-limited and the AppImage tree is ~1GB, so pick roomy scratch/project space interactively. Then put its `program/` dir on `PATH` or extend `_SOFFICE_CANDIDATES` in `qa.py`. Get `pdftoppm` via `conda install -c conda-forge poppler` or a cluster module. Alternatively, generate the `.pptx` on the cluster and `scp` it to a mac for QA.

## Branding source of truth

`~/arcadia/superstack/skills/_shared/branding.py`.
