# Handcraft every slide (expressive mode — the default)

**In expressive mode you HANDCRAFT EVERY content slide individually.** Design each one from scratch, for its own specific content, composing freeform geometry from the sandbox primitives. This is non-negotiable and it is the entire point of expressive mode.

**Follow NOTHING except the brand lock below.** Do not pick from a catalog of layouts. Do not reproduce the named layouts. Do not reuse another slide's composition. There is no menu and there is no template — if there were, you would use `--mode=strict`. Two slides should not share a composition. If you find yourself selecting "the closest layout," stop: that is the failure this document exists to prevent.

## The ONLY things you carry across slides (the brand lock)

These three are the complete set of constraints. Everything else is yours to invent, per slide, from scratch.

1. **Fonts.** `MONO_FONT` (Geist Mono) for all structural elements — titles, numbers, labels, eyebrows, stat values, table headers. `SANS_FONT` (Geist) for reading prose. Never any other font.
2. **Accent colors.** Brand-4 only — `TURQUOISE_RGB` / `DEEPPINK_RGB` / `AMBER_RGB` / `BLUEVIOLET_RGB` — plus the theme's `THEME_RGBS`/`SURFACE_RGB`/`CANVAS_BG_RGB` and `INK_RGB`/`WHITE_RGB`. No off-brand hexes. Text on a filled accent zone is `ON_DARK`-aware and amber-aware: white on turquoise/deeppink/blueviolet and on dark canvas; `INK_RGB` on amber (`(INK_RGB if accent_rgb == AMBER_RGB else WHITE_RGB)`).
3. **Side colorbar cycling.** The left colorbar (and each slide's `accent_rgb`) cycles turquoise → deeppink → amber → blueviolet by section order, handled automatically by the renderer. Use `accent_rgb` as the slide's lead color.

## Everything else is your design

Composition, hierarchy, zones, big numbers, diagrams, arrows, figure placement, whitespace, asymmetry, callouts — invent it for each slide based on what that slide says. A dominant statistic might become a giant number in a color zone; a two-way contrast might become split panels; a scorecard might become a color-chipped dashboard; a synthesis might become stacked narrative beats. But do not treat those as options to choose from — they are just evidence that the composition follows the content. Design yours.

## Mechanics

Sandbox API + primitives are in `plan_prompt.md` (freeform section) and `_sandbox.py`. To author: run `build.py --plan-only --shake` for correct `slide_id`/`content_hash`, then rewrite each content slide entry to `{"kind": "freeform", "params": {"title", "lede": "", "section_label": "", "code": "<your handcrafted design>"}}`, keep section-dividers, render WITHOUT `--shake`. Use `--qa` to emit per-slide PNGs and iterate visually. Precompute geometry in Python; emit flat primitive calls; `ast.parse` each snippet. Re-apply institutional logos to the cover after rendering.

## You defaulted (failed the bar) if

- Every figure slide is figure-left + bullets-right.
- Every list is a uniform card grid.
- The deck reuses two or three compositions across all slides.
- Any slide maps 1:1 onto a named layout.
- A wall of bullets with no visual hierarchy.

The deterministic `expressive_compose.py` composer is the floor for *agentless* renders only (a cron/pipeline with no LLM). When you — an agent — are building, you handcraft.
