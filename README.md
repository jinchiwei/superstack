# superstack

Blends complementary skills from [superpowers](https://github.com/obra/superpowers) and [gstack](https://github.com/garrytan/gstack) into a single pipeline for Claude Code and OpenAI Codex with minimal overhead.

## Claude Setup

```bash
git clone git@github.com:jinchiwei/superstack.git ~/arcadia/superstack
cd ~/arcadia/superstack
./setup
```

Requires [bun](https://bun.sh) (for gstack's browser build).

Running `./setup` again is safe -- it skips work when everything is already up to date.

## Codex Setup

Install the Codex version of the same pipeline:

```bash
cd ~/arcadia/superstack
./install-codex
```

This command:

- runs `./setup` so the gstack and superpowers sources are present
- refreshes the four Superpowers-derived Codex overlays from upstream `superpowers/skills`
- runs gstack's `./setup --host codex` to generate `~/.codex/skills/gstack-*` when the generated skills are missing or stale
- compacts generated gstack skill descriptions to avoid Codex skill-budget warnings
- installs the Codex overlays from `codex-skills/` into `~/.codex/skills`

The Codex overlays include `$pipeline`, `$writing-plans`, `$subagent-driven-development`,
`$test-driven-development`, `$verification-before-completion`, `$pipeline-update`,
`$pipeline-update_codex`, and `$claude`.

Reruns are idempotent: if gstack and the generated Codex skills are current, dependency-heavy
generation is skipped. Use `./install-codex --force-gstack-codex` to force regeneration, or
`./install-codex --no-compact-descriptions` to leave generated descriptions untouched.

## Update

Pull latest from upstream sources:

```bash
./update
./install-codex  # if you also use Codex
```

Or from Claude Code:

```
/pipeline-update
```

## What gets installed

| Source | Skills |
|--------|--------|
| **gstack** | browse, qa, ship, design-\*, plan-\*, review, office-hours, and [more](https://github.com/garrytan/gstack) |
| **superpowers** | subagent-driven-development, test-driven-development, verification-before-completion, writing-plans |
| **this repo** | pipeline, pipeline-update, autoresearch, build-pdf, build-pptx, build-docx |
| **this repo, Codex only** | claude second-opinion skill |

## The pipeline

```
THINK
  1. /office-hours              Clarify what to build
  2. /writing-plans             Write the implementation plan
  3. /autoplan                  Batched plan review (CEO + design + eng + DX + codex)
                                Fast path — auto-decides; surfaces close calls at a gate.
                                Manual fallback: /plan-ceo-review, /plan-design-review,
                                /plan-eng-review, /codex consult

BUILD
  4. /guard <project-dir>       Scope edits + destructive-command warnings
  5. /subagent-driven-development
     (each subagent uses /test-driven-development + /verification-before-completion)

VERIFY + SHIP
  6. /review                    Pre-landing code review
  7. /codex review              Cross-model diff review (independent model)
  8. /qa + /design-review       (if UI) Test and polish
  9. /ship                      Version bump, changelog, PR
  10. /document-release         Sync docs to what shipped
  11. /unfreeze                 Release the guard scope

If a step fails or you hit a bug mid-pipeline:
  * /investigate                Root-cause-first debugging before retrying
```

For Codex, the equivalent pipeline uses `$gstack-*` skills and replaces the old
Claude-side `/codex review` step with `$claude review`, which calls Claude Code with
xhigh effort for an outside-model pass.

## /autoresearch

Long-running autonomous research loop. Use when you want to iterate over a search space
(architectures, input modes, hyperparameters, etc.) for hours-to-days, with adaptive
replanning, agentic code-fix on failures, and a STOP-file kill switch. One invocation
per session — the skill self-paces via `ScheduleWakeup` and runs without prompts after
launch.

```
/autoresearch "iterate over architectures, input modes, loss functions for the FW model.
                target: val_corr > 0.85"
```

You'll be asked once at launch to confirm the planned axes. After that:

- **One iteration per ScheduleWakeup tick** — pick next candidate, run the experiment,
  classify any failure (transient / code_bug / infrastructure / unknown), replan the
  queue, append to the live narrative, schedule the next iteration.
- **State persisted** at `~/.gstack/projects/<slug>/autoresearch/state.json` so a Claude
  Code crash mid-session is recoverable (run `/autoresearch` with no args to resume).
- **Stop signals** — target metric reached, search space exhausted, `touch STOP` file,
  or 2 consecutive distinct infrastructure failures (D4 halt gate).
- **Standardized outputs** per iteration:
  - `results/<YYYY-MM-DD>_<scope>/iter-<NN>_<candidate>/` — synthesized (figures,
    metrics, `summary.md`); committed
  - `exp/<YYYY-MM-DD>_<scope>/iter-<NN>_<candidate>/` — raw artifacts (checkpoints,
    big logs); gitignored
  - Candidate scripts honor `$AUTORESEARCH_OUT_RESULTS` and `$AUTORESEARCH_OUT_EXP`
    (exported by the skill; no hardcoded paths).
- **Brand-styled session reports** at termination — runs any of
  `docs/_build_pptx.py`, `docs/_build_docx.py`, `docs/_build_pdf.py` that exist with
  `--date <date> --scope <slug>`. Templates dropped by `init-project` use Geist + the
  brand palette (turquoise / deeppink / amber / blueviolet) and produce a
  conference-presentation-quality deck plus conservative paper-style docx/pdf.

See `skills/autoresearch/USAGE.md` for full invocation, halt, and inspection patterns,
and `skills/autoresearch/DESIGN.md` for the architecture (locked decisions D1-D4 on
stash discipline, iteration error wrapping, schema migration, and infra halt gating).

## /build-pdf, /build-pptx, /build-docx

Three general-purpose markdown → branded document builders. They share one palette
and font system (`skills/_shared/branding.py`) so a PDF, deck, and Word doc generated
from the same source markdown look like they came from the same pen.

```
/build-pdf  notes.md             # branded PDF with cover, bookmarks, page numbers
/build-pptx talk.md              # 16:9 deck, navy title + section dividers, color cohesion
/build-docx draft.md             # Geist-styled Word doc via pandoc + reference.docx
```

- **Identity:** Geist Mono for structural elements (eyebrow, title, headings, code,
  metric values, page numbers); Geist Sans for body prose. Cross-platform fallback
  chains include Helvetica, system fonts, and CJK.
- **Palette:** turquoise (#40E0D0), deeppink (#FF1493), amber (#F0C840), blueviolet
  (#8A2BE2). Name renders turquoise, organization deeppink everywhere.
- **build-pptx layout plan (v7):** by default, the renderer writes a
  `<input>.md.layout.json` sidecar with per-slide layout choices and replays it
  on subsequent runs (deterministic). 13 named layouts cover most slides:
  `content-text`, `content-text-image`, `content-image-only`, `cards-grid`,
  `cards-heterogeneous`, `three-pillars`, `stat-callouts-right`, `bg-flip`,
  `timeline`, plus `stats-with-takeaway`, `figure-with-aside`,
  `cards-with-takeaway`, `table-with-takeaway`. The `composition` layout
  (rows × weight-allocated blocks, 8 block primitives, ~40 FA glyph icons via
  cairosvg) is a fallback when no named layout fits, and `freeform` lets
  Claude write raw python in a sandboxed namespace as a last resort. Use
  `--shake` to regenerate the plan, `--plan-only` to inspect without
  rendering, `--no-plan` to fall back to the v3 rule-based path, and
  `--use-blocks=auto|never|always` to control composition/freeform admission.
- **Closing-slide variety:** `composition` accepts `dark_bg: true` for navy-bg
  takeaways/conclusions, with each `card-row` card optionally carrying its own
  `accent_hex` to rotate through the brand palette. Card fills auto-darken to
  `#1A2D50` and body text flips to white when the slide bg is dark.
- **build-pptx color cohesion:** each section's accent color is auto-inferred from
  the H1 name (background/methods/results/limitations → turquoise/deeppink/amber/blueviolet)
  and cascades through every brand-color element on the section's slides — left
  accent bar, slide title, hairlines, first-table header, callout cards.
- **Frontmatter (optional):** `title`, `eyebrow`, `subtitle`, `name`, `org`, `date`.
- **Content slide layout** (matches funding_report + DMG canonical):
    - 0.22in left accent bar in the section's accent color (full height)
    - **Title** in 28pt Geist Mono bold INK (not accent — the bar carries the
      accent identity), with a hairline rule below
    - **Subtitle/lede** in 13pt Geist Sans MUTED — auto-extracted from the first
      paragraph after the H2 if it's short prose (≤220 chars) and there's more
      content below it on the slide
    - **Body region** routes by content type: cards (3-col grid), image-only
      (full-bleed), text+media (5.6/6.1 split with text left, media right),
      table-only (full-width), text-only (paragraph block with `▸` accent
      bullets in section color, sans 14pt INK, line-spacing 1.35)
    - **Footer** in 9pt Geist Mono MUTED: `name · org · deck title · date`
- **Special markdown for build-pptx:**
    - `---` separates slides
    - `# H1` starts a new section (emits a navy section-divider slide with a left
      colorblock, top-aligned eyebrow + accent bar, big title, low hairline rule,
      and a footer with name · org · deck title — geometry matched to DMG)
    - If `# H1` is followed by body content (no `## H2` separating them), the H1
      text is reused as the content slide title — avoids "(untitled)" slides
      when an author writes a section header directly above its content
    - `## H2` is a content slide title
    - `### H3` blocks under an H2 render as a card grid (paper tiles with accent
      top stripe, mono labels, sans body) — good for boxed-summary slides
    - markdown lists (`- foo`) render as accent-colored `▸` bullets
    - markdown tables render with the slide's accent color in row 1; if a slide
      carries 2+ tables, subsequent tables drop to INK so the second reads as
      supporting/legend data
    - `![alt](path)` embeds images, paths relative to the source markdown

Each skill is invocable directly via Python (e.g., `python skills/build-pptx/build.py
--input deck.md --output deck.pptx`) and ships fixture-driven tests under
`skills/<skill>/tests/`.
