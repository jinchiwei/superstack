# Results figures — every experiment / finding slide gets a representative data figure

For any research-talk deck, **every slide that reports a result needs a representative figure showing the underlying data** — not just a big-number stat zone with bullet points. The number is the headline; the figure is the evidence.

This is a standing default, parallel to [`intro_figures.md`](intro_figures.md) (which mandates custom intro/background figures redrawing published references). Where `intro_figures.md` covers BACKGROUND, this doc covers RESULTS.

## The rule

For every slide that headlines a quantitative finding (β, OR, ratio, p-value, mean difference, effect size, etc.), the slide MUST include a figure that visualizes the data behind the claim. Acceptable figure types per finding shape:

| Finding shape | Acceptable figure type |
|---|---|
| Continuous × continuous relationship (e.g. "FW tracks CDR-SB") | Scatter + regression line, color/style by group if relevant |
| Group means / comparison | Bar chart with error bars, or boxplot, or strip + group means |
| Slope difference between groups (e.g. APOE4 carriers vs non-carriers) | Two-or-more-line scatter+fit, lines clearly distinguishable by brand color |
| Longitudinal trajectory | Spaghetti plot (thin individual lines) + bold group means/predictions |
| Cross-cohort meta-analysis | Forest plot (study rows + diamond pooled) |
| Distribution / threshold | Histogram + cutpoint annotation |
| Per-region survey | Compact grid (heatmap or tiled bars) showing the effect across regions |
| Dose-response | Ordered bars with the dose levels + per-level value labels |

**Not acceptable as the sole visual** on a results slide:
- Bullet list of stats with no plot
- Per-region label tiles WITHOUT the associated values plotted (a "checkmark grid" of region names is decoration, not data)
- A big number alone in a colored zone (the hero-stat zone is fine AS the headline, but it must be paired with a data figure on the same slide)

## Layout pattern

The canonical layout: **compact hero stat zone left (~36% width)** + **dominant data figure right (~60% width)** + **caption + 1-2 micro-bullets**.

```
┌──────────────┬──────────────────────────────────────────────┐
│  RESULT N    │  ┌────────────────────────────────────────┐  │
│              │  │                                        │  │
│  +0.0091     │  │            DATA FIGURE                 │  │
│              │  │     (scatter / forest / trajectory)    │  │
│  beta (...)  │  │                                        │  │
│  ───────     │  │                                        │  │
│  p < 0.0001  │  │                                        │  │
│              │  └────────────────────────────────────────┘  │
│  micro-bul 1 │  small caption — what the figure shows        │
│  micro-bul 2 │                                              │
└──────────────┴──────────────────────────────────────────────┘
```

The stat zone width SHOULD compress to ~36% (was 42% in older designs) to give the figure room. The figure is the protagonist; the number is the byline.

## What to do when the figure already exists

Most experiment-driven research projects already produce per-experiment figures into `results/<date>_<scope>/<analysis>/figures/` as part of the analysis script. **Use those.** Copy or symlink them into the deck's `figures/` dir with a result-oriented name (e.g. `result1_fw_cdrsb_scatter.png`). Don't redraw if a clean version exists.

If the existing figure has annotations that conflict with the slide's headline (e.g. in-figure p-value from a different model parameterization than the slide's stat), either:
- Regenerate the figure with that annotation suppressed
- Or add a caption clarifying the relationship between in-figure annotations and the headline

## What to do when no figure exists

Generate one from the underlying summary CSV (which should exist per the [`intro_figures.md`](intro_figures.md) "Save the raw data" contract). Use the canonical `mpl_style` with the deck theme (slate/midnight/forest/paper/bone) so the figure background matches the slide canvas.

If the underlying analysis script doesn't save raw data: that's the contract violation called out in `intro_figures.md`. Either re-run the analysis with seed-fixed deterministic settings + saving raw data, or — if rerunning is expensive — accept a white-bg figure as a one-time exception, but the going-forward rule still applies to new work.

## Canonical figure types (worked examples)

These were validated on the AGF 2026-05-29 lab-talk deck:

- **Scatter + regression by group**: `result1_fw_cdrsb_scatter.png` — pooled-cohort baseline FW vs CDR-SB, 3 regression lines by APOE4 dose
- **Two-panel carrier × severity**: `result2_carrier_panel.png` — left = by-dose, right = by-carrier; CIs shown
- **Longitudinal trajectory by group**: `result3_ad_cingulate_trajectory.png` — AD-cingulate FW trajectories with thin individual lines + bold predicted means by APOE4 dose
- **Spaghetti by tertile**: `exp2_spaghetti.png` — longitudinal cortical thickness, color-coded by baseline FW tertile
- **Forest plot**: `exp4_forest_dx.png` — ADNI + NACC + pooled estimate with CIs
- **Bar + group means**: `exp3_fw_by_tau.png` — FW means by tau+/− stratified by cohort
- **Mixture distribution + cutpoint**: `exp3_gmm.png` — tau-SUVR histogram with GMM cutpoint marked

## Anti-patterns the doctrine prevents

- Slide 19 ("Result 1: cortical FW tracks CDR-SB") used to be a hero-stat-+-bullets-only slide with NO figure. Audience question: "what does that look like in the data?" — should not require a presenter to gesture at imagined data. Fixed via adding `result1_fw_cdrsb_scatter.png`.
- Per-region "tile grid" (slide 20 v1) listing 11 abbreviated region names without per-region effect sizes was decorative, not informative. Fixed by either adding p-values per tile (slide 20 v2) OR replacing with the data figure (slide 20 final = carrier panel scatter).

## See also

- [`intro_figures.md`](intro_figures.md) — background-figure doctrine (redraw published references + save raw data)
- [`bespoke_design.md`](bespoke_design.md) — slide composition doctrine (handcraft each slide; brand lock; figures dominate)
- [`self_qa.md`](self_qa.md) — render-look-fix QA loop (applies to both slides and figures)
