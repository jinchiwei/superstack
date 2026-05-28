# Handcraft every slide (expressive mode — the default)

**In expressive mode you HANDCRAFT EVERY content slide individually.** Design each one from scratch, for its own specific content, composing freeform geometry from the sandbox primitives. This is non-negotiable and it is the entire point of expressive mode.

**Follow NOTHING except the brand lock below.** Do not pick from a catalog of layouts. Do not reproduce the named layouts. There is no menu and there is no template — if there were, you would use `--mode=strict`. If you find yourself selecting "the closest layout" instead of designing for the content, stop: that mechanical selection is the failure this document exists to prevent.

Resemblance is fine; *template-following* is not. If two slides end up looking similar because their content is genuinely alike (e.g. two single-statistic findings), that's a natural consequence of letting the composition follow the content — leave it. The line you must not cross is forcing slides into a fixed set of shapes regardless of what they say. Design each one for its content; if that yields some coincidental overlap, fine.

## The ONLY things you carry across slides (the brand lock)

These three are the complete set of constraints. Everything else is yours to invent, per slide, from scratch.

1. **Fonts.** `MONO_FONT` (Geist Mono) for all structural elements — titles, numbers, labels, eyebrows, stat values, table headers. `SANS_FONT` (Geist) for reading prose. Never any other font.
2. **Accent colors.** Brand-4 only — `TURQUOISE_RGB` / `DEEPPINK_RGB` / `AMBER_RGB` / `BLUEVIOLET_RGB` — plus the theme's `THEME_RGBS`/`SURFACE_RGB`/`CANVAS_BG_RGB` and `INK_RGB`/`WHITE_RGB`. No off-brand hexes. Text on a filled accent zone is `ON_DARK`-aware and amber-aware: white on turquoise/deeppink/blueviolet and on dark canvas; `INK_RGB` on amber (`(INK_RGB if accent_rgb == AMBER_RGB else WHITE_RGB)`).
3. **Side colorbar cycling.** The left colorbar (and each slide's `accent_rgb`) cycles turquoise → deeppink → amber → blueviolet by section order, handled automatically by the renderer. Use `accent_rgb` as the slide's lead color.

## Everything else is your design

Composition, hierarchy, zones, big numbers, diagrams, arrows, figure placement, whitespace, asymmetry, callouts — invent it for each slide based on what that slide says. A dominant statistic might become a giant number in a color zone; a two-way contrast might become split panels; a scorecard might become a color-chipped dashboard; a synthesis might become stacked narrative beats. But do not treat those as options to choose from — they are just evidence that the composition follows the content. Design yours.

## Figures must dominate

When a slide centers on a figure, **the figure IS the slide** — it must be readable and command major presence, roughly **half the canvas or more**. A reader should be able to read its axes and trend from across a room. **Never shrink a figure to a thumbnail to make room for stats or text.** If you have stats/text to show alongside, make the figure large and keep the supporting text compact — a slim stat strip, a short caption, a verdict tile — fit around the figure, not the other way around. A figure crammed into a corner while stat chips eat the top half is a failure: invert it (figure dominant, stats secondary). Use `_fit_image` with generous `max_w`/`max_h` so the figure fills its zone.

## Mechanics

Sandbox API + primitives are in `plan_prompt.md` (freeform section) and `_sandbox.py`. To author: run `build.py --plan-only --shake` for correct `slide_id`/`content_hash`, then rewrite each content slide entry to `{"kind": "freeform", "params": {"title", "lede": "", "section_label": "", "code": "<your handcrafted design>"}}`, keep section-dividers, render WITHOUT `--shake`. Use `--qa` to emit per-slide PNGs and iterate visually. Precompute geometry in Python; emit flat primitive calls; `ast.parse` each snippet. Re-apply institutional logos to the cover after rendering.

## You defaulted (failed the bar) if

- Every figure slide is figure-left + bullets-right.
- Every list is a uniform card grid.
- Slides are forced into a fixed handful of compositions *regardless of their content* (coincidental resemblance between genuinely-similar slides is NOT this — forcing dissimilar content into the same mold is).
- A slide is picked off the named-layout menu instead of designed.
- A wall of bullets with no visual hierarchy.

The deterministic `expressive_compose.py` composer is the floor for *agentless* renders only (a cron/pipeline with no LLM). When you — an agent — are building, you handcraft.
