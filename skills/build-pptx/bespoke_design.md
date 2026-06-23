# Handcraft every slide (expressive mode — the default)

**In expressive mode you HANDCRAFT EVERY content slide individually.** Design each one from scratch, for its own specific content, composing freeform geometry from the sandbox primitives. This is non-negotiable and it is the entire point of expressive mode.

**Follow NOTHING except the brand lock below.** Do not pick from a catalog of layouts. Do not reproduce the named layouts. There is no menu and there is no template — if there were, you would use `--mode=strict`. If you find yourself selecting "the closest layout" instead of designing for the content, stop: that mechanical selection is the failure this document exists to prevent.

Resemblance is fine; *template-following* is not. If two slides end up looking similar because their content is genuinely alike (e.g. two single-statistic findings), that's a natural consequence of letting the composition follow the content — leave it. The line you must not cross is forcing slides into a fixed set of shapes regardless of what they say. Design each one for its content; if that yields some coincidental overlap, fine.

## The ONLY things you carry across slides (the brand lock)

These three are the complete set of constraints. Everything else is yours to invent, per slide, from scratch.

1. **Fonts.** `MONO_FONT` (Geist Mono) for all structural elements — titles, numbers, labels, eyebrows, stat values, table headers. `SANS_FONT` (Geist) for reading prose. Never any other font.
2. **Accent colors.** Brand-4 only — `TURQUOISE_RGB` / `DEEPPINK_RGB` / `AMBER_RGB` / `BLUEVIOLET_RGB` — plus the theme's `THEME_RGBS`/`SURFACE_RGB`/`CANVAS_BG_RGB` and `INK_RGB`/`WHITE_RGB`. No off-brand hexes. Text on a filled accent zone is `ON_DARK`-aware and amber-aware: white on turquoise/deeppink/blueviolet and on dark canvas; `INK_RGB` on amber (`(INK_RGB if accent_rgb == AMBER_RGB else WHITE_RGB)`).
3. **Side colorbar cycling.** The left colorbar (and each slide's `accent_rgb`) cycles turquoise → deeppink → amber → blueviolet by section order, handled automatically by the renderer. Use `accent_rgb` as the slide's lead color.

### Contrast is non-negotiable

- **Text on a filled color zone:** pick the text color with **`_text_on(fill)`** (a luminance/WCAG helper exposed in the sandbox) — it returns ink or white for max contrast. Do NOT hardcode (`WHITE` on every fill, or `INK if amber else WHITE`). `_text_on(accent_rgb)`, `_text_on(some_theme_hue)`, etc.
- **Body text on a surface/card panel must be high-contrast** — `INK_RGB` on light, `WHITE_RGB` on dark (or `_text_on(SURFACE_RGB)`). **Never put primary/body text in a muted/dim gray (`MUTED_RGB`/`DIM_RGB`) on a panel** — it blends into the surface and becomes unreadable. Reserve `MUTED_RGB`/`DIM_RGB` only for *tiny secondary captions on the open canvas* where separation is obvious, never for card body copy.
- If you can't read it at a glance in the QA render, it fails.

## Everything else is your design

Composition, hierarchy, zones, big numbers, diagrams, arrows, figure placement, whitespace, asymmetry, callouts — invent it for each slide based on what that slide says. A dominant statistic might become a giant number in a color zone; a two-way contrast might become split panels; a scorecard might become a color-chipped dashboard; a synthesis might become stacked narrative beats. But do not treat those as options to choose from — they are just evidence that the composition follows the content. Design yours.

## Figures must dominate

When a slide centers on a figure, **the figure is the protagonist** — it must out-weigh everything else on the slide and be legible. The bar is **readability + relative dominance, judged in the QA render — not a fixed width fraction** (a portrait figure can dominate at 40% width; a wide one can be tiny at 60%). The test: in the rendered PNG, can you read the figure's axes / labels / data points at a glance, and is it clearly the focal point? If a figure reads as a thumbnail, or you can't read its axes, or stats/text are competing with it for dominance — it's too small. Enlarge it (and cut/compress the surrounding text) until it passes. **Never shrink a figure to make room for text; the text fits around a large figure, never the reverse.** Use `_fit_image` with generous `max_w`/`max_h`. This is caught in the mandatory self-QA pass — *look* at every figure slide and ask "is the figure the clear focal point and readable?"

## Figures must match the slide background — and raw data must always be saved (ENFORCED)

**Every figure you generate for a slide must be rendered on that slide's background color** — never matplotlib's default white. A white figure box on a dark themed slide (or a dark box on a light slide) reads as a pasted screenshot and is a defect. Match it: set `figure.facecolor` / `axes.facecolor` / `savefig.facecolor` to the slide canvas hex, and flip text / tick / spine / legend / annotation colors to a readable foreground (light on dark, ink on light). Theme canvas hexes live in `contrast_check.py::THEME_CANVAS_HEX` (slate `#1E293B`, midnight `#14141C`, forest `#0F1E17`, paper/bone light) — read the deck's `theme` from the sidecar and use its canvas. If the SAME figure also appears in a white-background doc (PDF/report), keep BOTH a white-bg original and a slide-bg variant and point each target at the right file.

**Always save the raw data behind every figure** (npz / csv / parquet / json) next to its script, as you plot — BEFORE you need it. A figure whose underlying arrays aren't persisted is not finished: re-theming it to the slide background, or any reviewer tweak, otherwise forces a full pipeline re-run. With the data saved, regeneration is seconds (canonical pattern: plot once to white for the doc, then re-theme from the saved arrays to the slide bg for the deck). This is mandatory.

**Enforcement.** The runtime contrast check (`contrast_check.py`) auto-runs on EVERY render and, for an agent-in-the-loop render (i.e. without `--allow-composed`), **aborts the build (non-zero exit)** if any non-brand-approved text run is below WCAG AA on its actual background — including ink/muted text on a dark canvas. You cannot ship a handcrafted deck with unreadable text. (Agentless `--allow-composed` cron renders accept the deterministic floor and only warn.) On a dark theme, use `_text_on(CANVAS_BG_RGB)` (or `(WHITE_RGB if ON_DARK else INK_RGB)`) for primary text and `_text_on(<fill>)` for text on a colored/surface rect; never hardcode `INK_RGB`/`MUTED_RGB` on a dark canvas. The escape hatch `--allow-contrast-fail` exists only for a deliberate brand-edge case. The figure-background and raw-data rules are part of the mandatory self-QA pass below — treat a white-on-dark figure as a hard fail there.

## Visual polish — catch these yourself

These are baseline craft, not extras. Get them right while designing:

- **Even spacing / breathing room.** Distribute stacked elements evenly across their zone — don't bunch everything at the top and squish the rest at the bottom. Vertically center a lone block; evenly space a stack. Leave padding inside filled zones and cards (text must not touch edges).
- **No squished or clipped text.** Size boxes generously; if text is long, reduce font before letting it clip or collide. A giant number must fit its box (widen the box / drop the size — never let it truncate).
- **Figures dominate** (see above) and are readable.
- **Contrast holds** (amber → ink text; light text only on dark/strong fills).
- **Section colors match** divider ↔ its content.

## Self-QA is MANDATORY — do not deliver a deck you haven't looked at

After rendering, you MUST rasterize every slide to PNG (`--qa`, or `soffice --convert-to pdf` then `pdftoppm`) and **visually inspect each one**. Iterate render → look → fix until each slide is clean.

The full discipline — what to look for (text overlap, contrast, spacing, truncation, layout, mismatched accents, empty bands) and how to run the loop — lives in [`self_qa.md`](self_qa.md). It applies the same way to slide composition AND to custom matplotlib figures generated for the deck. **Read it once; apply it every deck.**

## Mechanics

Sandbox API + primitives are in `plan_prompt.md` (freeform section) and `_sandbox.py`. To author: run `build.py --plan-only --shake` for correct `slide_id`/`content_hash`, then rewrite each content slide entry to `{"kind": "freeform", "params": {"title", "lede": "", "section_label": "", "code": "<your handcrafted design>", "_provenance": "agent"}}`, keep section-dividers, render WITHOUT `--shake`. Use `--qa` to emit per-slide PNGs and iterate visually. Precompute geometry in Python; emit flat primitive calls; `ast.parse` each snippet. Re-apply institutional logos to the cover after rendering.

### Speaker notes are part of the deliverable

Every content slide also gets comprehensive, didactic speaker notes via `params["notes"]` (the renderer embeds them into the notes pane). A handcrafted deck without notes is unfinished. See [`speaker_notes.md`](speaker_notes.md).

### The enforcement gate — you cannot skip this

`build.py` MECHANICALLY enforces bespoke. The agentless composer stamps every slide it generates with `params["_provenance"] = "composer"`. On a real render (not `--plan-only`), if **any** content slide is still stamped `"composer"`, the build **aborts with a non-zero exit and writes no `.pptx`**, listing the floor slides you still owe. The floor is a hard error, not a warning — because prose guidance here was ignored too many times.

To clear the gate, **handcraft the slide and set `params["_provenance"] = "agent"`** (or delete the key) when you write its `code`. The stamp persists in the sidecar, so you cannot dodge the gate by re-running `build.py` on a floor sidecar — it stays red until each slide is genuinely handcrafted.

`--allow-composed` bypasses the gate and ships the floor. It exists ONLY for non-interactive / cron renders (e.g. the autoresearch shell-out) with no agent in the loop. **If you are an agent reading this, you ARE in the loop — never pass `--allow-composed`; handcraft instead.**

## You defaulted (failed the bar) if

- Every figure slide is figure-left + bullets-right.
- Every list is a uniform card grid.
- Slides are forced into a fixed handful of compositions *regardless of their content* (coincidental resemblance between genuinely-similar slides is NOT this — forcing dissimilar content into the same mold is).
- A slide is picked off the named-layout menu instead of designed.
- A wall of bullets with no visual hierarchy.
- A framing/methods/motivation slide is only text cards or a step-rail, with no explanatory diagram (see *Concept figures*).

The deterministic `expressive_compose.py` composer is the floor for *agentless* renders only (a cron/pipeline with no LLM). When you — an agent — are building, you handcraft.


## Figure-first default

When a slide quantifies something (a scorecard, a comparison, a survey across regions), prefer a custom figure over a typed table. A typed table is a fallback, not the default. If you're typing a table of numbers, you're almost certainly missing a chart that would read in 2 seconds instead of 20.

## Concept figures — non-results slides need diagrams too (DON'T default to text cards)

The figure-first rule is **not just for results**. The slides that most often fall back to text — intended use, methods/approach, motivation, study design, framing, recommendations — should ALSO carry a bespoke **explanatory diagram**, not a grid of text cards or a bulleted "steps" rail. Card-grids and step-rails are the *text* fallback; treat them like typed tables: a last resort, not the default. A reader should grasp the concept from the picture before reading a word.

Build these by hand in matplotlib (dark/brand-locked, same palette + Geist/Geist Mono as your data figures). Hand-roll each one bespoke to the idea. Common concept-figure shapes and when to use them:

- **Pipeline / flow** — for intended-use, system architecture, "how it works": input → process → model → decision, with a fork for outcomes. (e.g. patient → questionnaire → model → triage decision.)
- **Method schematic** — for "why trust this": draw the actual procedure. A cross-validation schematic (fold grid with held-out highlighted), a data-split diagram, a leakage-control illustration. Show the mechanism, don't assert it.
- **Funnel / cohort flow** — for population / inclusion-criteria / case-mix slides: a narrowing funnel with n and key rates at each stage makes spectrum/prevalence shifts obvious.
- **Concept map / 2×2 / quadrant** — for trade-offs, positioning, taxonomies.
- **Timeline / roadmap** — for study phases, milestones, sequencing.
- **Annotated diagram** — for anatomy, device, or workflow context.

A short caption strip under the diagram (one line of key points) is fine — but the diagram, not the text, is the slide. If a framing slide is only text cards or only a step-rail with no figure, you defaulted.

This is the doctrine `intro_figures.md` (background) and `results_figures.md` (results) leave out: the **middle** of the deck (methods, motivation, design, recommendations) earns bespoke figures too.
