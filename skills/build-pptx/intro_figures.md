# Intro / background figures — redraw published references, don't leave placeholders

For **any research-talk deck** built with `build-pptx` — lab talks, conference talks, defenses, seminars, autoresearch reports — the intro / background / motivation slides need **custom figures that redraw foundational references** with clear citation. This is the **standing default**, not session-specific polish. Bullet-only intro slides are a regression.

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

```python
import sys
sys.path.insert(0, "/home/jiwei/arcadia/superstack/skills/_shared")
from mpl_style import apply_style, title, TURQUOISE, DEEPPINK, AMBER, GOLD, BLUEVIOLET

apply_style()

import matplotlib.pyplot as plt
import numpy as np

fig, ax = plt.subplots(figsize=(11, 5), dpi=160)
# ... your composition (sigmoids / bars / boxes / arrows) ...

# Citation in the title -- THIS IS NOT OPTIONAL
title(ax, "AD biomarker cascade -- where free-water could sit  (Jack 2013, NEJM)")

fig.tight_layout()
fig.savefig("figures/intro_cascade.png", bbox_inches="tight", facecolor="white")
```

Reference the figure in `deck.md` with the citation in the alt text:

```markdown
![ATN framework — where free-water sits as a candidate "N+" marker (Jack 2018)](figures/intro_atn_framework.png)
```

## Brand lock (same as everywhere)

- Titles + suptitles: **Geist Mono, black** (via `title(ax, ...)` from `mpl_style`)
- Body text (axis labels, ticks, annotations): **Geist sans, black**
- Data marks (bars, lines, markers): brand palette in priority order — **TURQUOISE → DEEPPINK → AMBER → BLUEVIOLET**
- Solid filled shapes (bar fills, filled markers, filled patches): swap `AMBER` → `GOLD` (matplotlib named color) for the deeper readability tone Jin uses for fills
- Errorbar / annotation text: black; only data marks may be colored
- White figure facecolor (`facecolor="white"`); `dpi=160`

Hand-rolling `rcParams` or inlining hex codes is a regression — always use `apply_style()` + the named palette imports.

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
