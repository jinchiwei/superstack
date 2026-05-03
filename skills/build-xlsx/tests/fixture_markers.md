---
title: "Status Dashboard"
subtitle: "Experiment status with semantic markers"
date: "2026-04-22"
---

# Experiment Status

| Experiment | Val AUC | Status | Notes |
|------------|---------|--------|-------|
| [winner] CaFormer + BCE | 0.931 | complete | best result |
| ResNet18 + BCE | 0.871 | complete | baseline |
| [warning] ViT-B + Focal | 0.812 | degraded | below threshold |
| [deferred] Swin + BCE | — | pending | not yet attempted |
| [headline] CaFormer + Focal | 0.945 | complete | new best! |

# Future Work

| Item | Priority | Notes |
|------|----------|-------|
| [winner] JHU dataset update | high | immediate lift expected |
| [deferred] Tongue modality | low | awaiting annotations |
| [warning] Audio pipeline | medium | infra not ready |
| Plain row | normal | no marker here |
