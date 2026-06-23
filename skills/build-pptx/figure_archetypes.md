# Figure archetypes — reusable visual patterns for engaging slides

For any slide where the content is a scorecard, a comparison, a pipeline, a partition, an anatomical relationship, or a model-selection decision — **use a reusable archetype from `skills/_shared/deck_figures.py` instead of typing a table of numbers or hand-rolling matplotlib from scratch**.

This is the "engaging visuals" doctrine. Pairs with `intro_figures.md` (background concepts) and `results_figures.md` (data visualizations). Where those say *what* to draw, this says *how to draw it consistently* — so every deck gets the same brand-locked archetype library and you don't reinvent the wheel each session.

## The principle

When you're tempted to put a 4-row × 4-column table on a slide because "the numbers are the story," **stop**. Ask: what visual representation makes those numbers *immediately* readable at slide-glance distance? In almost every case, that's an archetype already in `deck_figures.py`. If it isn't, add one — don't re-implement.

The default for any slide that quantifies something is **a figure** + a short caption + 2-4 micro-bullets. Text + table is a fallback, not the default.

## The archetype catalog

All archetypes live in `skills/_shared/deck_figures.py`. Import:

```python
import sys; sys.path.insert(0, "/home/jiwei/arcadia/superstack/skills/_shared")
from mpl_style import apply_style, theme_colors, TURQUOISE, DEEPPINK, AMBER, BLUEVIOLET
from deck_figures import (
    region_dot_strip, comparison_bars, aic_or_metric_curves, binary_grid,
    depth_schematic, compartment_diagram, pipeline_flow,
    four_panel_scorecard, save_with_transparent_bg, composite_onto_canvas,
)
```

### 1. `region_dot_strip` — N items × M conditions, colored dots

**When**: showing direction agreement across many items (regions, bundles, models) at two or more conditions (depths, cohorts, models). The "did the result hold across regions" question.

**Example**: "T2 pre-saturation direction holds across depths" — 11 cortical regions × 2 depths, each dot colored by sign of β.

### 2. `comparison_bars` — paired horizontal bars per item

**When**: showing the same N items at two conditions with annotations (β, p-value). The "same item, two depths" question.

**Example**: precuneus + inferior parietal at 10mm (solid) vs 2mm (faded), with β and p annotated per bar.

### 3. `aic_or_metric_curves` — overlaid line curves with baseline

**When**: model-selection curves across a parameter grid (piecewise AIC, hyperparameter sweep, depth gradient). The "where does the model prefer to be" question.

**Example**: ΔAIC vs candidate knee location at 10mm (turquoise, dips below 0 = knee preferred) overlaid with 2mm (deeppink, stays above 0 = linear preferred), with amber baseline line at 0.

### 4. `binary_grid` — N×M filled/empty squares

**When**: binary survival across items and conditions (FDR-sig vs not, present vs absent). The "which regions made it" question.

**Example**: 11 cortical regions × 2 depths, filled = passed FDR correction. Visually shocking when the count collapses.

### 5. `depth_schematic` — anatomical cross-section with sampling layers

**When**: methods slides showing where in tissue a measurement is taken. The "where exactly does our pipeline sample" question.

**Example**: cortical cross-section with pia on top, WM/GM boundary in violet, then dashed lines for −2mm (turquoise) and −10mm (deeppink) sampling layers. Built-in right-side depth axis.

### 6. `compartment_diagram` — labeled partition of a whole

**When**: showing how a tissue/region/dataset splits into components. The "this whole has these compartments" question.

**Example**: WM partitioned into U-fibers (A) + major bundles (B) + WM rim (C), with each compartment labeled with its short letter, full name, description, and percent.

### 7. `pipeline_flow` — boxed flow diagram with arrows

**When**: methods slides showing a sequential pipeline or decision flow. The "here's the analytical pipeline" question.

**Example**: 4-stage preprocessing pipeline (DWI → preprocessing → FERNET fit → cortical projection).

### 8. `four_panel_scorecard` — composite of 4 panel-figure functions

**When**: TL;DR scorecards that need to show 4 different aspects of one story. The "here's what changed across our analyses" question.

**Example**: panel 1 = region_dot_strip (direction), panel 2 = comparison_bars (sig hits), panel 3 = aic_or_metric_curves (knee fit), panel 4 = binary_grid (FDR survival). All four cohere into one slide.

## The brand contract

All archetypes:
- Use brand-4 accents only (turquoise / deeppink / amber / blueviolet)
- Geist Mono for titles/labels, Geist for body
- Save with **transparent background** by default — composite onto the slide canvas via `save_with_transparent_bg`. The figure background dissolves into the slide bg cleanly.
- Save raw data sibling (JSON or CSV) for re-themability per the global "save raw data for figures" rule.
- Theme-aware: pass `theme="slate"` (or whatever the deck uses) for muted-text / rule colors that match.

## Workflow recipe

1. **In the deck-generation script** (`docs/runs/<date>_<scope>/_make_figs.py` or similar), build the figure using archetypes:

   ```python
   from deck_figures import four_panel_scorecard, region_dot_strip, comparison_bars, ...
   from mpl_style import apply_style, theme_colors, TURQUOISE, DEEPPINK
   apply_style(theme="slate")
   T = theme_colors("slate")

   def panel1(ax):
       region_dot_strip(ax,
           items=regions,
           rows=[("10mm", betas_10), ("2mm", betas_2)],
           color_fn=lambda v: TURQUOISE if v > 0 else DEEPPINK,
           legend=[("ADNI direction (+)", TURQUOISE), ("opposite direction (−)", DEEPPINK)],
           theme="slate",
       )

   def panel2(ax):
       comparison_bars(ax,
           items=["precuneus", "inferiorparietal"],
           cond_a=("10mm", betas_a, pvals_a),
           cond_b=("2mm",  betas_b, pvals_b),
           theme="slate",
       )

   # ... panels 3 + 4 ...

   four_panel_scorecard(
       panels=[
           ("1. T2 pre-saturation — direction holds", panel1),
           ("2. Both sig hits lose p<0.05",           panel2),
           ("3. Ceiling knee disappears",             panel3),
           ("4. Exp 2 thinning — FDR collapses 10×", panel4),
       ],
       out_path="figures/fig_headline_scorecard.png",
       suptitle="Slide 3 headline scorecard — visual",
       theme="slate",
       save_data={"regions": regions, "betas_10": list(betas_10), ...},
   )
   ```

2. **In the deck markdown**: reference the saved PNG as you would any figure (`![alt](figures/fig_headline_scorecard.png)`).

3. **In the bespoke slide design** (`_gen_deck.py` DESIGNS): use `_fit_image(slide, FIGS["fig_headline_scorecard.png"], ...)` with a slim takeaway band underneath.

## Adding new archetypes

When you build a hand-rolled figure that turns out to be useful (you've used the pattern in 2+ decks), promote it to `deck_figures.py` as a new function:
- Follow the existing signature pattern (ax, *, kwargs)
- Take a `theme` kwarg, use `theme_colors()` for theme-aware colors
- Use brand-4 accents only
- Save with transparent bg by default
- Add a brief docstring with "Idiom:" line describing the use case
- Add an entry to this doc's catalog
- Add a smoke test in `skills/_shared/tests/test_deck_figures.py`

If a hand-rolled figure is one-off (only useful for that specific deck), keep it in the deck's `_make_figs.py` script. Promotion bar is "I've seen this pattern twice."

## What this replaces

Before this catalog existed, every autoresearch deck reimplemented:
- Multi-panel scorecards from scratch (~100 lines each)
- Region-by-condition visualizations as ad-hoc bars (often ugly)
- Anatomical schematics with hand-tuned coordinates (often misaligned)
- AIC sweeps as raw scatter plots (no shading, no baseline)

Now those patterns are functions you call. The session deck's value goes up; the analyst time per deck goes down.

## See also

- [`intro_figures.md`](intro_figures.md) — background-figure doctrine (redraw published references)
- [`results_figures.md`](results_figures.md) — results-figure doctrine (every quant finding gets a data figure)
- [`bespoke_design.md`](bespoke_design.md) — slide composition doctrine (handcraft each slide)
- [`self_qa.md`](self_qa.md) — visual QA loop
- [`skills/_shared/deck_figures.py`](../../_shared/deck_figures.py) — the helper implementation
