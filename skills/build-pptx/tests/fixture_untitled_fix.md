---
title: "Regression: H1-with-body produces titled content slides, not (untitled)"
eyebrow: "REGRESSION TEST"
name: "Jinchi Wei"
org: "UCSF"
date: "2026-05-01"
---

# EXECUTIVE SUMMARY

This v3 report supersedes v2. The methodology has been audited for leakage and the leak-free numbers are reported here, alongside the original leaky numbers for comparison.

---

# METHODOLOGY OVERVIEW

- Cohorts: UCSF (n ≈ 100, primary) + PNOC (multi-site held-out external, n ≈ 35).
- Per-fold MI selection. No baked-in feature lists.
- 5-seed bootstrap CIs throughout.

---

# Results

The headline numbers below should each appear on their own slide, with a real title (not "(untitled)").

---

## Headline AUC

The classifier reaches AUC 0.91 on held-out internal data and 0.85 across both external sites.

---

## Methodology footnote

Numbers reported are from the leak-corrected pipeline. Leak-free per-fold MI selection replaces the original baked-in feature list.
