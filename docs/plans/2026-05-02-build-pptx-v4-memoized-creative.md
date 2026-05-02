# build-pptx v4: Memoized Creative Layouts Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Multi-task plan, ~6-8 hr CC time.

**Goal:** Make `/build-pptx` produce per-slide creative layouts (CPH/funding-report level — heterogeneous cards, stat callouts, arrows, bg flips, side-rail figures) on first invocation, then **deterministically replay** the same layouts on subsequent runs. A `--shake` flag regenerates a fresh creative plan when Jin wants to mix things up. Same input → same output by default.

**Architecture:** Split build-pptx into two phases.

```
markdown.md ──[plan]──> markdown.layout.json ──[render]──> markdown.pptx
                              │ (cache)
                              ▼
                       reused on next run unless --shake
```

- **Phase 1 (`plan`):** Claude reads the markdown, looks at each slide's content, picks a layout from a curated catalog of templates, fills in template params (e.g., for `cards-grid`: number of cards, icon assignments, bg color flip). Outputs a JSON sidecar.
- **Phase 2 (`render`):** Pure Python. Reads markdown + sidecar, dispatches each slide to its template renderer, produces .pptx. Zero LLM calls. ~2-second renders.
- **Cache invariant:** Slide IDs are stable hashes of H1/H2 + position. As long as the markdown's section structure is unchanged, the sidecar still applies. New slides get appended to the plan; removed slides stay in the sidecar but are unused.

**Tech Stack:** Python 3.12 in `deepdream` conda env. Existing deps. New: in-session Claude reasoning via Claude Code itself (no external API). The `plan` phase is invoked by Jin in the slash command; Claude Code (the agent) writes the JSON.

**Realistic effort: ~6-8 hr CC time.** Bulk is the layout primitives library and the prompt that drives plan generation.

---

## File Structure

```
~/arcadia/superstack/skills/build-pptx/
├── build.py                              MODIFY: add --plan, --shake, --no-plan, --plan-only flags
├── plan.py                               CREATE: plan generation logic (writes JSON sidecar)
├── render.py                             CREATE: deterministic render from markdown + plan
├── layouts/                              CREATE: layout primitives library
│   ├── __init__.py
│   ├── catalog.py                        CREATE: registry mapping layout-id → render fn
│   ├── _common.py                        CREATE: shared helpers (header, footer, accent bar)
│   ├── content_text.py                   PORT: existing add_content_slide → text-only variant
│   ├── content_text_image.py             PORT: existing 1-image text+image (side-by-side or stacked)
│   ├── content_image_only.py             PORT: existing full-bleed image
│   ├── cards_grid.py                     PORT: existing card grid (3-col uniform)
│   ├── cards_heterogeneous.py            CREATE: 1-large + 2-small grid (CPH proposal slide 2 style)
│   ├── three_pillars.py                  CREATE: 3-column compare (CPH slide 5: 3 boxes + arrow)
│   ├── stat_callouts_right.py            CREATE: chart left + 4 stat tiles right (funding_report slide 3)
│   ├── bg_flip.py                        CREATE: dark-on-dark take-away slide (CPH slide 6)
│   └── timeline.py                       CREATE: horizontal timeline with milestones
├── plan_prompt.md                        CREATE: prompt template for Claude's plan generation
└── tests/
    ├── test_plan_idempotent.py           CREATE: same md + same plan → same pptx
    ├── test_plan_round_trip.py           CREATE: write plan, read back, verify schema
    └── test_layout_*.py                  CREATE: per-layout unit tests
```

---

## Layout-Plan JSON Schema

```jsonc
{
  "version": 1,
  "deck_id": "dmg_v3",                       // optional, derived from filename
  "deck_md_hash": "sha256:...",              // for staleness detection
  "shake_seed": null,                        // set when --shake fires; else null
  "slides": [
    {
      "slide_id": "h1-executive-summary",   // hash of section headers
      "kind": "content-text",                // layout-catalog key
      "params": {
        "title": "Executive summary",
        "lede": "This v3 report supersedes v2...",
        "body_kind": "paragraphs",
        "accent_override": null              // null = inherit from section
      }
    },
    {
      "slide_id": "h1-methodology-overview",
      "kind": "cards-grid",
      "params": {
        "title": "Methodology overview",
        "cards": [
          { "label": "Cohorts", "body": "...", "icon": null },
          { "label": "Targets", "body": "...", "icon": null },
          // ...
        ]
      }
    },
    {
      "slide_id": "h2-known-risk-factors",
      "kind": "cards-heterogeneous",
      "params": {
        "title": "Known risk factors for ARIA",
        "primary_card": { "label": "APOE ε4 Genotype", "body": "Strongest predictor...", "icon": "icons/dna.png" },
        "secondary_cards": [/* 2-3 smaller */ ]
      }
    },
    // ...
  ]
}
```

---

## Slide-ID Stability

Slide IDs derive from a hash of the H1/H2 chain at that position in the markdown:

```
h1-executive-summary             # under # Executive summary
h1-methodology-overview          # under # Methodology overview
h2-cohorts                       # under ## Cohorts (within some H1)
auto-h2-cohorts-2                # if duplicate H2 in deck
```

Algorithm:
1. Walk slide chunks in order.
2. For each chunk, build path: `<closest H1 slug> [+ <H2 slug if present>]`.
3. If duplicate, append `-2`, `-3`...
4. ID is the path joined by `/`.

This way, reordering an unrelated section doesn't invalidate other slides' cache entries. Renaming a section title invalidates that one slide.

---

## Phased Tasks

### Task 1: Layout catalog + carve out existing renderers (~1.5 hr)

**Files:**
- Create: `skills/build-pptx/layouts/__init__.py`
- Create: `skills/build-pptx/layouts/_common.py`
- Create: `skills/build-pptx/layouts/catalog.py`
- Create: `skills/build-pptx/layouts/content_text.py`
- Create: `skills/build-pptx/layouts/content_text_image.py`
- Create: `skills/build-pptx/layouts/content_image_only.py`
- Create: `skills/build-pptx/layouts/cards_grid.py`
- Test: `skills/build-pptx/tests/test_layout_carve_out.py`

- [ ] **Step 1.1:** Move `_add_text`, `_add_rect`, `_set_bg`, `_blank`, `_add_card`, `_render_paragraph_block`, `_render_media_block`, `_get_image_aspect`, `_estimate_paragraph_height`, `_add_runs_from_html` from `build.py` into `layouts/_common.py`. Update imports in `build.py`.

- [ ] **Step 1.2:** Carve `add_content_slide`'s text-only branch into `layouts/content_text.py`:
  ```python
  def render(slide, *, params, accent_rgb, footer_kwargs):
      # params: {"title", "lede", "body": [{"kind","html"}], "extra"?}
      title = params["title"]
      lede = params.get("lede")
      body = params.get("body", [])
      # ... same as existing text-only branch
  ```

- [ ] **Step 1.3:** Same for `content_text_image.py`, `content_image_only.py`, `cards_grid.py`. Each takes `params` dict + accent + footer.

- [ ] **Step 1.4:** `catalog.py`:
  ```python
  from . import (content_text, content_text_image, content_image_only,
                 cards_grid, cards_heterogeneous, three_pillars,
                 stat_callouts_right, bg_flip, timeline)
  REGISTRY = {
      "content-text":         content_text.render,
      "content-text-image":   content_text_image.render,
      "content-image-only":   content_image_only.render,
      "cards-grid":           cards_grid.render,
      "cards-heterogeneous":  cards_heterogeneous.render,
      "three-pillars":        three_pillars.render,
      "stat-callouts-right":  stat_callouts_right.render,
      "bg-flip":              bg_flip.render,
      "timeline":             timeline.render,
  }
  def get(kind): return REGISTRY[kind]
  ```

- [ ] **Step 1.5:** Update existing `add_content_slide` in `build.py` to dispatch through `catalog.get(kind)(slide, params=...)`. Existing 22 tests must still pass — this is a pure refactor.

- [ ] **Commit:** `refactor(build-pptx): carve content slide into layouts/ catalog (no behavior change)`

### Task 2: New creative layout primitives (~2 hr)

**Files:**
- Create: `skills/build-pptx/layouts/cards_heterogeneous.py`
- Create: `skills/build-pptx/layouts/three_pillars.py`
- Create: `skills/build-pptx/layouts/stat_callouts_right.py`
- Create: `skills/build-pptx/layouts/bg_flip.py`
- Create: `skills/build-pptx/layouts/timeline.py`

- [ ] **Step 2.1:** `cards_heterogeneous` — one large card on the left (60% width, full body height) + 2-3 smaller cards stacked on the right. Each card supports `icon`, `label`, `body`. CPH proposal slide 2 reference.

- [ ] **Step 2.2:** `three_pillars` — three vertical columns with optional arrow connectors between them. `params.pillars = [{label, body, color_role}]`. Each pillar has paper bg + colored top stripe. Arrows render as right-pointing triangles between columns. CPH slide 5 reference.

- [ ] **Step 2.3:** `stat_callouts_right` — chart on the left (~7in wide, full body height), 4 stat tiles stacked on the right. Each stat tile: big mono number (24pt accent) + sans label below (12pt MUTED). funding_report slide 3 reference.

- [ ] **Step 2.4:** `bg_flip` — dark navy bg + white text, used for "key takeaway" slides. Same content shape as `content-text` but inverted color theme. CPH slide 6 reference.

- [ ] **Step 2.5:** `timeline` — horizontal axis at body midline, milestone dots along axis, labels above and dates below. `params.milestones = [{date, label, body}]`.

- [ ] **Step 2.6:** Per-layout unit tests confirming each renders without exception and produces expected number of shapes.

- [ ] **Commit:** `feat(build-pptx): add 5 creative layout primitives (heterogeneous cards, three pillars, stat callouts, bg flip, timeline)`

### Task 3: Slide-ID derivation + plan schema (~0.5 hr)

**Files:**
- Create: `skills/build-pptx/plan.py` (skeleton)
- Test: `skills/build-pptx/tests/test_plan_round_trip.py`

- [ ] **Step 3.1:** In `plan.py`, add:
  ```python
  def derive_slide_id(h1: str | None, h2: str | None,
                      auto_index: int) -> str:
      """Hashable, stable ID from section context."""
      slug = lambda s: re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") if s else ""
      parts = []
      if h1: parts.append(f"h1-{slug(h1)}")
      if h2: parts.append(f"h2-{slug(h2)}")
      if not parts: parts.append(f"auto-{auto_index}")
      return "/".join(parts)
  ```

- [ ] **Step 3.2:** `Plan` dataclass with `version`, `deck_md_hash`, `slides: list[SlideEntry]`. Round-trip JSON.

- [ ] **Step 3.3:** Test: write a plan, parse it back, verify equality.

- [ ] **Commit:** `feat(build-pptx): plan schema + slide-id derivation`

### Task 4: Plan generation prompt + driver (~1.5 hr)

**Files:**
- Create: `skills/build-pptx/plan_prompt.md`
- Modify: `skills/build-pptx/plan.py`

The plan generator runs IN-SESSION when Claude Code invokes the skill. The slash command writes a temp file with the markdown + the layout catalog reference, then asks Claude to fill in a JSON plan based on the layout choices.

- [ ] **Step 4.1:** Author `plan_prompt.md` — a self-contained prompt that tells Claude:
  - Here is the markdown.
  - Here are the available layouts (catalog with one-line descriptions + when to use each).
  - For each slide chunk (split by `<hr>` after rendering), pick the best layout from the catalog and fill its params.
  - Use `cards-grid` when ≥3 H3 children OR ≥3 def-list bullets.
  - Use `cards-heterogeneous` when content has one clearly-primary item and 2-3 supporting (e.g., "main result + caveats").
  - Use `three-pillars` when content explicitly compares 3 things.
  - Use `stat-callouts-right` when content has 1 chart + a list of numeric findings.
  - Use `bg-flip` for slides whose H1/H2 contains "Key", "Takeaway", "Critical", or similar.
  - Default to `content-text-image` or `content-text` for unstructured content.
  - Output JSON only, matching the schema in this plan doc.

- [ ] **Step 4.2:** `plan.py::generate_plan(md_path) -> dict`:
  - Computes `deck_md_hash`.
  - Splits markdown into slide chunks (reuse existing `_split_slides`).
  - Derives slide IDs.
  - Returns the *prompt* string that should be handed to Claude. Actual generation is done by the slash-command driver in Claude Code itself.

- [ ] **Step 4.3:** `plan.py::merge_with_existing(new_plan, existing_plan) -> dict`:
  - For each slide_id in new_plan, if it exists in existing_plan AND its content hash matches, keep the existing layout entry verbatim.
  - Otherwise use the new entry.
  - Slides removed from markdown drop from the merged plan.

- [ ] **Commit:** `feat(build-pptx): plan generation prompt + cache merge logic`

### Task 5: Render driver (~1 hr)

**Files:**
- Create: `skills/build-pptx/render.py`
- Modify: `skills/build-pptx/build.py` (CLI flags + orchestration)

- [ ] **Step 5.1:** `render.py::render_from_plan(md_path, plan, output_path)`:
  - Loads markdown for content (paragraphs, images per slide).
  - For each plan entry: looks up `params`, calls `catalog.get(kind)(slide, params=...)`.
  - Saves pptx.

- [ ] **Step 5.2:** `build.py` CLI flags:
  - `--shake` — ignore existing sidecar; regenerate plan from scratch.
  - `--plan-only` — emit plan JSON; don't render pptx.
  - `--no-plan` — fall through to legacy rule-based renderer (current behavior).
  - Default: read sidecar if present, else generate one in-session, save it, then render.

- [ ] **Step 5.3:** Sidecar path: `<input>.layout.json` next to the markdown (e.g., `talk.md` → `talk.md.layout.json`).

- [ ] **Step 5.4:** Determinism test: render twice with the same plan → assert pptx bytes are identical (modulo timestamp metadata, which we strip).

- [ ] **Commit:** `feat(build-pptx): render driver + CLI flags for plan/shake/no-plan modes`

### Task 6: Slash-command integration (~0.5 hr)

**Files:**
- Modify: `skills/build-pptx/SKILL.md`

The slash command needs to do the in-session Claude reasoning when no sidecar exists. The skill markdown already documents itself — adding a short block on the new behavior:

```markdown
When invoked, /build-pptx checks for a `.layout.json` sidecar next to
the input markdown:

- **Sidecar present + content unchanged:** render deterministically. ~2 sec.
- **Sidecar present + new slides added:** auto-extend the plan with default
  layouts for the new slides; render. ~2 sec.
- **Sidecar absent OR --shake:** Claude Code reads the markdown, picks a
  layout from the catalog for each slide, writes the sidecar, then renders.
  ~30-60 sec depending on deck size.
- **--no-plan:** skip the sidecar entirely; use the legacy rule-based
  renderer. Useful for kb-learning style decks where layout creativity
  isn't needed.
```

- [ ] **Step 6.1:** Update SKILL.md.
- [ ] **Step 6.2:** Add a smoke test that exercises each mode against `fixture_realistic.md`.

- [ ] **Commit:** `feat(build-pptx): document v4 layout-plan modes in SKILL.md`

### Task 7: Migration + smoke + tag (~0.5 hr)

- [ ] **Step 7.1:** Run on `dmg_v3_report.md` with no sidecar → Claude generates plan → render. Inspect output for creative-layout firing (cards-heterogeneous, stat-callouts, bg-flip).
- [ ] **Step 7.2:** Run again → should hit cached sidecar → byte-identical pptx (mod timestamp).
- [ ] **Step 7.3:** `touch` the markdown, add a new slide → run → cached entries preserved, new slide gets default layout.
- [ ] **Step 7.4:** Run with `--shake` → fresh plan generated → diff old vs new sidecar to confirm regeneration.
- [ ] **Step 7.5:** Sync to `~/.claude/skills/`. Tag `build-skills-v4`.

- [ ] **Commit + push + tag:** `chore: tag build-skills-v4`

---

## Self-Review Checklist

- [ ] Existing 22 tests pass (refactor is behavior-preserving)
- [ ] New layout primitives have unit tests (each renders without exception)
- [ ] Plan round-trips through JSON
- [ ] Same markdown + same plan → byte-identical pptx (modulo metadata)
- [ ] `--shake` regenerates a fresh plan
- [ ] New slides added to markdown auto-extend the plan without invalidating existing entries
- [ ] Slide-ID derivation is stable across re-orderings of unrelated sections
- [ ] SKILL.md documents the four modes (default / `--shake` / `--plan-only` / `--no-plan`)
- [ ] Tag `build-skills-v4` pushed

---

## Notes for the Implementer

- **Don't break the rule-based path.** `--no-plan` must keep working exactly as today's `/build-pptx`. The whole legacy renderer can stay as one big "content-text-image" layout dispatched when there's no sidecar AND no `--no-plan` flag is forced. Prefer this over surgery on `add_content_slide` — wrap, don't tear.
- **Sidecar lives next to the markdown, not in `~/.cache`.** Jin commits the sidecar so the deck is reproducible across machines and across time.
- **Plan generation is in-session Claude reasoning, not an API call.** The slash command writes a stub plan file with a sentinel like `"_pending_generation": true`, then Claude (running the skill) reads the markdown + catalog and rewrites the file with real choices. No `anthropic.Anthropic()` SDK calls needed — Claude Code is the agent.
- **Per-slide content hash, not just slide-ID.** If a slide's H2 is unchanged but its body content changed substantially, the cached layout might no longer fit. Compute a content hash per slide, store in the sidecar, and re-plan that slide if the hash drifts past a threshold (or if the cached layout's required params no longer match the content).
- **Catalog growth is the main improvement vector.** Each new layout in `layouts/` extends the creative range. Future templates worth adding: "quote pull", "before/after comparison", "agenda dashboard", "single big number", "chart with annotated callouts" (lines from data points to text labels).
