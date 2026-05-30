# Custom deck figures — redraw published refs AND use real openly-licensed images, anywhere a concept needs one

For **any research-talk deck** built with `build-pptx` — lab talks, conference talks, defenses, seminars, autoresearch reports — slides that explain a concept need a **custom figure**, not a bullet wall or a placeholder. This is the **standing default**, not session-specific polish.

## Not just intro — the WHOLE deck

The original framing was "intro/background figures." Generalize it: **any slide whose point is a concept, structure, mechanism, or comparison deserves a figure** — wherever it sits in the deck.

- **Background:** disease cascade, mechanism, risk dose-response, conceptual framework.
- **Methods:** model **architecture diagrams (e.g. a ResNet / U-Net / transformer block stack)**, preprocessing/pipeline flowcharts, cohort/CONSORT diagrams, estimator schematics, study-design timelines.
- **Results:** conceptual schematics that frame a result (what a metric means, how a comparison is set up) — but never *replace* your real data figures (ROC, forest, calibration); those stay.
- **Discussion:** decision-flow / clinical-pathway diagrams, limitation taxonomies.

If a methods slide would benefit from, say, a hand-drawn ResNet block diagram, draw one (matplotlib `FancyBboxPatch` + `FancyArrowPatch`, brand-styled) — exactly as you would an intro cascade. Name it `methods_*.png`.

## Two complementary figure sources — use BOTH

1. **Redraw** foundational reference figures yourself in matplotlib (brand-styled), with `(adapted from Author Year)` in the **figure title** via `title(ax, ...)`. Best for *concepts/schematics*: cascades, dose-response, frameworks, architectures, pipelines. Never screenshot a paper figure.
2. **Real openly-licensed images** where photographic realism IS the payload — an MRI, PET, histology slide, micrograph, gross specimen. Pull **CC / public-domain** primary images (Wikimedia `https://commons.wikimedia.org/wiki/Special:FilePath/<File>?width=N`; NIH/PD sources). Frame white-bg images on a `WHITE_RGB` card; dark-bg images (MRI/PET) sit on the dark canvas. Caption with **source + license**. This is distinct from (and NOT the same ethical category as) screenshotting a copyrighted journal figure — those are still forbidden.

Redraw the concept; show the real thing. A mechanism slide can pair a redrawn schematic (the "how") with a real histology image (the "proof").

## Default vs opt-out

**Default ON** when any of:
- The deck is for an external or sibling-lab audience
- The user describes it as a "talk", "presentation", "seminar", "defense", or "lab talk for X"
- It's an autoresearch report deck
- The request is ambiguous about audience

**Default OFF** (skip intro figures) when any one:
- User says "skip intro figures" / "no intro figures" / "internal deck, no background"
- Deck frontmatter has `no_intro_figures: true`
- The deck is a status update / sprint review / team weekly / follow-up to a deck the audience already saw
- The audience already knows the program (e.g. "deck for our weekly")

When uncertain → default ON; ask post-build whether to strip them.

## Why

Background slides without figures read as wall-of-text and lose the audience early. Stock paper figures (screenshotted from a PDF) are off-brand, low-resolution, and ethically muddy. The reliable solution: **redraw** the foundational reference figures yourself in matplotlib, using brand styling, with clear "(adapted from Author Year)" attribution. The figure conveys the same concept; the credit goes to the original; the slide stays on-brand.

## What "applying it" looks like in practice

- Add ≥ 3 background / motivation slides **before** methods / results to the deck.md outline
- For each, generate one custom matplotlib figure (real citations only — from training knowledge; never fabricated)
- Save them to `figures/intro_*.png` (or `figures/methods_*.png` for methods-section figures)
- Reference in deck.md as `![Caption (adapted from Author Year)](figures/intro_xyz.png)`
- The autoresearch deck step does this by default

## The pattern — 3 to 5 intro figures per deck

Aim for one custom figure per background concept. Typical research-deck intro has 4 background slides; each gets one figure.

### Common archetypes (pick what fits your topic)

| Archetype | What it shows | Example reference to redraw |
|---|---|---|
| **Disease-progression cascade** | Stacked sigmoids of biomarker abnormality over disease stage | Jack 2013 NEJM AD biomarker cascade |
| **Decomposition schematic** | Multi-panel "= A + B" diagram of a model's components | Pasternak 2009 bi-tensor (observed = tissue + free water) |
| **Genotype / risk dose-response** | Ordered bars with OR / effect-size labels per group | Genin 2011 APOE meta-OR by diploid genotype |
| **Conceptual framework boxes** | A / T / N — tiered boxes with biomarker examples per tier | Jack 2018 ATN framework |
| **Cohort demographics** | Grouped bars by group × cohort + modality availability matrix | Any consortium description figure |
| **Pipeline / preprocessing flowchart** | FancyBboxPatch nodes + FancyArrowPatch arrows, color-coded by stage | Method papers' "Figure 1" pipeline diagrams |
| **Timeline / treatment landscape** | Clinical-era stack: approvals, trials, key papers as year-stacked bars | Drug-approval / biomarker-validation timelines |

You don't need every archetype every time — pick ones that map to your slides.

## How — code template

Use the shared canonical `mpl_style` (the project's brand). Save figures as `figures/intro_*.png` (or `figures/methods_*.png` for methods slides).

**Match the deck theme.** Read the deck's resolved theme from `<deck>.md.layout.json` (top-level `theme` field — e.g. `"slate"`, `"midnight"`, `"forest"`, `"paper"`, `"bone"`) and pass it to `apply_style(theme=...)`. Then save the figure with the theme's canvas color so the figure blends into the slide instead of being a stark white rectangle on a dark canvas:

```python
import sys, json
from pathlib import Path
sys.path.insert(0, "/home/jiwei/arcadia/superstack/skills/_shared")
from mpl_style import apply_style, title, theme_colors, \
    TURQUOISE, DEEPPINK, AMBER, GOLD, BLUEVIOLET

# Theme-aware setup — match the deck.
DECK_THEME = json.loads(Path("deck.md.layout.json").read_text())["theme"]  # "slate" / "paper" / ...
apply_style(theme=DECK_THEME)
T = theme_colors(DECK_THEME)   # T.canvas, T.ink_text, T.muted_text, T.rule, T.surface, T.on_dark

import matplotlib.pyplot as plt
import numpy as np

fig, ax = plt.subplots(figsize=(11, 5), dpi=160)
# ... your composition (sigmoids / bars / boxes / arrows) ...

# Citation in the title — THIS IS NOT OPTIONAL.
title(ax, "AD biomarker cascade — where free-water could sit  (Jack 2013, NEJM)")

# Annotation text uses theme ink, not hardcoded black/white.
ax.text(x, y, "FW: candidate upstream N+ marker",
        color=T.ink_text, fontsize=10, weight="bold")

fig.tight_layout()
fig.savefig("figures/intro_cascade.png", bbox_inches="tight", facecolor=T.canvas)
```

If the deck theme is unknown / the figure is going to a document (not a deck), omit `theme=` and you get the default light/paper styling — black text on white.

Reference the figure in `deck.md` with the citation in the alt text:

```markdown
![ATN framework — where free-water sits as a candidate "N+" marker (Jack 2018)](figures/intro_atn_framework.png)
```

## Brand lock (same as everywhere)

- Titles + suptitles: **Geist Mono**, themed ink color (via `title(ax, ...)` from `mpl_style`)
- Body text (axis labels, ticks, annotations): **Geist sans**, themed ink (use `T.ink_text` not hardcoded `"black"` / `"white"`)
- Data marks (bars, lines, markers): brand palette in priority order — **TURQUOISE → DEEPPINK → AMBER → BLUEVIOLET**. These work on light AND dark canvases — never swap them per theme.
- Solid filled shapes (bar fills, filled markers, filled patches): swap `AMBER` → `GOLD` (matplotlib named color) for the deeper readability tone
- Errorbar / annotation text: themed ink (`T.ink_text`); only data marks may be colored
- Figure facecolor: `T.canvas` (so it matches the slide canvas); `dpi=160` (200 for high-density)

## Self-QA — figures are visual artifacts; same discipline as slides

Before delivering, **render every figure to PNG and look at it**. The full QA loop and the checklist of common failures (text overlap with data, contrast against the canvas, off-edge clipping, illegible tick labels, legend covering data, etc.) lives in [`self_qa.md`](self_qa.md) — **the same doc that governs slide QA**, because the principle is identical: render, look, fix; don't ship a visual you haven't looked at.

Read [`self_qa.md`](self_qa.md) once; apply it to figures the same way you apply it to slides.

## Save the raw data so figures can be regenerated for any theme

Every figure script should write the data it plots to a sibling file alongside the PNG. Two benefits:

1. **Theme-matching versions** — if the deck theme changes (e.g. from `paper` to `slate`), you can re-run the figure script with `apply_style(theme=NEW)` and get a freshly-themed PNG in seconds. No analysis re-run.
2. **A "canonical white" version always exists** — keep the default `theme=None` (paper / white background) PNG as the cross-context reference for papers, docs, posters. The slide-deck version is a separate file generated for that deck's theme.

### Naming convention

For a figure `figures/intro_apoe_risk.png`:

- `figures/intro_apoe_risk.png` — the canonical (light / paper) version, always present
- `figures/intro_apoe_risk_<theme>.png` — theme-matching version (e.g. `_slate.png`) used when embedded in a dark deck
- `figures/raw/intro_apoe_risk.csv` (or `.npz`, `.json`) — the raw data the figure was plotted from
- `figures/raw/intro_apoe_risk.gen.py` (optional) — minimal script that reads the CSV and regenerates the figure for any theme

### What "raw data" means

Whatever the chart eats. For:

- A bar chart → CSV with `category, value, sem` columns
- A line chart → CSV with `x, series_1, series_2, ...` columns or a long-format CSV with `series, x, y`
- A forest plot → CSV with `study, effect, ci_lower, ci_upper, weight, label`
- A 2D heatmap / matrix → numpy `.npz` with the matrix + row/column labels
- A scatter → CSV with `x, y, group, label`

Don't save derived plotting state (matplotlib `Line2D` objects, etc.) — save the *numbers that went in*. The regen script reads them and re-plots.

### When you're authoring a new figure

Pattern: split the figure into two phases — (a) compute the data, (b) plot. Phase (a) saves the data to `figures/raw/` and returns it. Phase (b) takes the data and a theme and writes the PNG. The deck-build step calls (b) with the deck's theme; the canonical-white version comes from calling (b) with `theme=None`.

### Existing figures with no raw data

Pre-existing figures (e.g. results from an earlier analysis that didn't save its tabular outputs) stay as-is — typically white-background. Don't retrofit unless you're already touching them. Going forward, every NEW figure should follow the raw-data contract.

For `autoresearch`-driven analyses: the experiment driver scripts that write `fig_*.png` SHOULD also write `fig_*.csv` (or `.npz`) with the same stem, so the report-builder can regenerate the figure on-theme without re-running the experiment.

Hand-rolling `rcParams` or inlining hex codes is a regression — always use `apply_style(theme=...)` + `theme_colors(theme)` + the named palette imports.

## Citation rules — non-negotiable

- Cite **real** primary sources from training knowledge. Never invent an author / year / journal.
- If you're not sure of the exact year or journal, cite author + concept only: `"(adapted from Pasternak et al. — bi-tensor model)"`. Less precise is fine; fabricated is not.
- The figure is **redrawn**, not copied. Your composition should be your own — using your own ellipses / bars / boxes — that conveys the same concept. Never re-pixel a paper figure into PowerPoint.
- The caption signals adaptation: `"(adapted from Author Year)"` or `"(Author Year-style)"` — not `"(Author et al. Fig 2)"`.

## What this is NOT

- Not a generic stock-figure library — every figure is composed fresh for the slide's concept
- Not a substitute for showing your own DATA figures in the results sections
- Not OK to use with a citation you couldn't independently confirm
- Not template-driven — each figure is composed for its own slide

## Worked example — the AGF lab-talk deck

`docs/runs/2026-05-29_lab-talk/_make_figs.py` is the canonical reference implementation. Five figures, one per intro/methods concept, each citing the primary source in the title:

- `intro_atn_framework.png` — Jack 2013 NEJM biomarker cascade
- `intro_freewater_bitensor.png` — Pasternak 2009 bi-tensor decomposition
- `intro_apoe_risk.png` — Genin 2011 Mol Psychiatry APOE OR meta
- `methods_cohorts.png` — ADNI + NACC grouped bars + modality matrix
- `methods_pipeline.png` — FERNET pipeline flowchart

Copy that file, swap the topics, change the citations — that's the workflow.
