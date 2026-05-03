---
title: "Q3 Experiment Matrix"
subtitle: "All-up status across initiatives"
date: "2026-04-22"
---

# Architecture Sweep

| Backbone | Loss | Val AUC | Status |
|----------|------|---------|--------|
| ResNet18 | BCE | 0.871 | complete |
| CaFormer | BCE | 0.931 | complete |
| ViT-B | Focal | 0.812 | complete |

# Hyperparameter Tuning

This section covers HPO results for the winning backbone (CaFormer).

| Run | LR | Batch | Dropout | Val AUC |
|-----|-----|-------|---------|---------|
| run-1 | 1e-3 | 32 | 0.1 | 0.921 |
| run-2 | 5e-4 | 64 | 0.2 | 0.937 |
| run-3 | 1e-4 | 32 | 0.3 | 0.905 |

# Future Directions

Notes on next iteration priorities.

| Item | Effort | Expected Lift |
|------|--------|---------------|
| Add tongue modality | L | unknown |
| JHU 400-patient update | S | +0.01–0.02 AUC |
| Wav2Vec2 audio | L | unknown |
