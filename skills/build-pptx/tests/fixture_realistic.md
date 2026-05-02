---
title: "Radiogenomic Prediction in Diffuse Midline Glioma"
eyebrow: "BRAIN LAB · LAB MEETING"
subtitle: "MRI-based H3K27M classification with external replication"
name: "Jinchi Wei"
org: "UCSF Department of Radiology"
date: "2026-05-01"
---

# Background

---

## Why this matters

Diffuse midline glioma carries near-universal mortality. Tumor genotype — specifically the H3K27M mutation — drives prognosis and eligibility for trial enrollment, but biopsy of midline structures carries real surgical risk.

A non-invasive imaging classifier could route patients to confirmatory biopsy, eligible trials, or palliative care without putting them under the knife twice.

---

## What we set out to do

Build a multi-institution MRI-based classifier for H3K27M status in pediatric and adult midline glioma cohorts, validated externally, with honest performance reporting at multiple operating points.

---

# Methods

---

## Pipeline overview

We built a three-stage radiogenomic pipeline. Stage one pulls volumetric T1, T2, and FLAIR sequences and rigidly registers them to the patient's own midline anatomy. Stage two extracts both deep features (a self-supervised 3D encoder pretrained on the BRATS atlas) and 1064 hand-crafted radiomic features. Stage three feeds a cross-validated logistic regression head with feature selection.

![Method summary](../../../../brainlab/projects/dmg/2026-05-01_dmg-final-report/figures/fig_method_summary.png)

---

## Cohorts

| Cohort | Site | n | H3K27M+ | Imaging |
|---|---|---|---|---|
| Internal train | UCSF | 142 | 67 | T1/T2/FLAIR |
| Internal val | UCSF | 38 | 19 | T1/T2/FLAIR |
| External A | CHOP | 86 | 41 | T1/T2/FLAIR |
| External B | DFCI | 64 | 29 | T1/FLAIR only |

---

# Results

---

## Headline numbers

Three operating points worth flagging — internal performance, external generalization, and the bimodal subset.

### AUC 0.91
Held-out internal cohort. The model separates H3K27M+ from wild-type cleanly when all three sequences are available.

### AUC 0.85+
Both external cohorts hold above 0.85. CHOP reaches 0.87; DFCI 0.85 with only T1+FLAIR.

### Sens 0.80+
At the prespecified operating point, sensitivity holds above 0.80 across all three validation cohorts.

### Spec 0.79+
Specificity tracks closely. We are not trading off heavy false-positive burden to chase sensitivity.

### Δ 0.03 cost
T1+FLAIR-only model (External B) loses ~0.03 AUC vs the full T1/T2/FLAIR pipeline.

### Spearman 0.79
Feature-importance ranks transfer cleanly from internal to CHOP. The model is not site-memorizing.

---

## Performance breakdown

A more granular look — per-cohort AUC, sensitivity, and specificity at the prespecified threshold.

| Cohort | AUC | Sens@0.5 | Spec@0.5 |
|---|---|---|---|
| Internal val | 0.91 | 0.88 | 0.84 |
| External A | 0.87 | 0.83 | 0.81 |
| External B | 0.85 | 0.80 | 0.79 |

---

## AUC heatmap

Per-cohort, per-feature-set AUC. The deep + radiomic combination beat either alone in every cohort, with the largest gain on the bimodal-only External B subset.

![AUC heatmap](../../../../brainlab/projects/dmg/2026-05-01_dmg-final-report/figures/fig_heatmap_auc.png)

---

## External replication

The atlas-replication test holds: feature importance ranks computed on internal data predict ranks on external data with Spearman 0.79 (CHOP) and 0.71 (DFCI). The model isn't memorizing site idiosyncrasies.

![Atlas replication](../../../../brainlab/projects/dmg/2026-05-01_dmg-final-report/figures/fig_atlas_replication.png)

---

# Limitations

---

## Where this fails

External B (DFCI) lacks T2 sequences. We re-fit a T1+FLAIR-only model for that cohort, which costs us roughly 0.03 AUC. Patients with prior cranial radiation see degraded contrast, and their per-patient AUC drops to 0.78. We do not yet have a calibration curve good enough to publish probabilities — only thresholded decisions.

---

## What we cannot claim

This is a retrospective binary classifier. It does not replace biopsy where biopsy is feasible. We have not measured downstream impact on trial enrollment or time-to-treatment. The training cohort skews younger; performance on adults over 50 is sparse.

![External validation breakdown](../../../../brainlab/projects/dmg/2026-05-01_dmg-final-report/figures/fig_external_validation.png)

---

# Conclusions

---

## What we'd ship

A site-deployable classifier, calibrated per institution, that flags likely H3K27M+ scans for radiologist review and confirmatory biopsy planning. Not a replacement for biopsy. A pre-screen.

---

## Next steps

Prospective enrollment at three additional sites (Stanford, MSK, Heidelberg). Harmonize T2 protocols where missing. Add a calibration head and publish per-cohort reliability diagrams. Pre-register a clinical decision-impact study with our oncology collaborators.
