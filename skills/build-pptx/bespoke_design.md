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

## Visual polish — catch these yourself

These are baseline craft, not extras. Get them right while designing:

- **Even spacing / breathing room.** Distribute stacked elements evenly across their zone — don't bunch everything at the top and squish the rest at the bottom. Vertically center a lone block; evenly space a stack. Leave padding inside filled zones and cards (text must not touch edges).
- **No squished or clipped text.** Size boxes generously; if text is long, reduce font before letting it clip or collide. A giant number must fit its box (widen the box / drop the size — never let it truncate).
- **Figures dominate** (see above) and are readable.
- **Contrast holds** (amber → ink text; light text only on dark/strong fills).
- **Section colors match** divider ↔ its content.

## Self-QA is MANDATORY — do not deliver a deck you haven't looked at

After rendering, you MUST rasterize every slide to PNG (`--qa`, or `soffice --convert-to pdf` then `pdftoppm`) and **visually inspect each one**. Fix, before handing it over: thumbnail/cramped figures, squished or unevenly-spaced text, text touching or overflowing its box, clipped numbers, low-contrast text, mismatched section accents, empty bands. Iterate render → look → fix until each slide is clean. Catching these is your responsibility — the user should not have to point at slide N and tell you a figure is tiny or text is squished. If you skipped the visual pass, you are not done.

## Mechanics

Sandbox API + primitives are in `plan_prompt.md` (freeform section) and `_sandbox.py`. To author: run `build.py --plan-only --shake` for correct `slide_id`/`content_hash`, then rewrite each content slide entry to `{"kind": "freeform", "params": {"title", "lede": "", "section_label": "", "code": "<your handcrafted design>", "_provenance": "agent"}}`, keep section-dividers, render WITHOUT `--shake`. Use `--qa` to emit per-slide PNGs and iterate visually. Precompute geometry in Python; emit flat primitive calls; `ast.parse` each snippet. Re-apply institutional logos to the cover after rendering.

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

The deterministic `expressive_compose.py` composer is the floor for *agentless* renders only (a cron/pipeline with no LLM). When you — an agent — are building, you handcraft.
