# Phase 1.2 Workstream C: Near-Threshold Neighbor Rescue

Date: 2026-09-01

## Scope

- Main dataset: `configs/datasets/physicalai/physicalai_row0709_after3m.yaml`
- Secondary dataset: `configs/datasets/ua_detrac/ua_detrac_mvi_39361.yaml`
- Main experiment: `configs/experiments/phase1_2_neighbor_rescue.yaml`
- Secondary experiment: `configs/experiments/phase1_2_secondary_neighbor_rescue_ua_detrac_mvi_39361.yaml`

## Implementation

- Added `neighbor_rescue` config block.
- Added 1-ring near-threshold tile rescue in `TileMaskPolicy`.
- Added `neighbor_motion_weak` selection reason in tile metadata.
- Added candidate profiles:
  - `neighbor_motion_weak`
  - `rescue_with_budget_cap`

`boundary_only_rescue` is deferred as an online policy. The policy cannot use GT/miss taxonomy at inference time, so this remains an analysis/tuning direction rather than a direct implementation in Workstream C.

## Main 600-Frame Result

Matrix root: `outputs/validation_matrices/phase1_2_neighbor_rescue_20260901_155233`

| Profile | Contain | Missed GT | Small contain | Missed small | Tile/frame | Tensor/frame | Fallback | False ROI |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `practical_default` | 0.641 | 1035 | 0.602 | 816 | 12.752 | 263441.0 | 20 | 0.523 |
| `margin_plus` | 0.655 | 993 | 0.620 | 779 | 12.752 | 282164.2 | 20 | 0.514 |
| `rare_tile_guard` | 0.625 | 1081 | 0.588 | 845 | 11.462 | 245620.7 | 19 | 0.485 |
| `neighbor_motion_weak` | 0.713 | 826 | 0.700 | 615 | 14.762 | 329729.0 | 28 | 0.461 |
| `rescue_with_budget_cap` | 0.699 | 867 | 0.685 | 647 | 12.840 | 299538.0 | 20 | 0.447 |

## Taxonomy

| Profile | Margin insufficient | Adjacent tile not selected | Signal missing | False ROI records |
|---|---:|---:|---:|---:|
| `practical_default` | 297 | 329 | 304 | 828 |
| `margin_plus` | 255 | 329 | 304 | 813 |
| `neighbor_motion_weak` | 189 | 231 | 258 | 651 |
| `rescue_with_budget_cap` | 215 | 262 | 285 | 615 |

Tile selection reason counts:

| Profile | Motion threshold | Neighbor weak | Rare guard suppressed |
|---|---:|---:|---:|
| `neighbor_motion_weak` | 7651 | 1206 | 0 |
| `rescue_with_budget_cap` | 6909 | 795 | 996 |

## Secondary Result

Matrix root: `outputs/validation_matrices/phase1_2_secondary_neighbor_rescue_ua_detrac_mvi_39361_20260901_155345`

`MVI_39361` remains dominated by global-motion fallback:

| Profile | Contain | Missed GT | Tile/frame | Fallback |
|---|---:|---:|---:|---:|
| `practical_default` | 0.000 | 2643 | 84.567 | 599 |
| `margin_plus` | 0.000 | 2643 | 84.567 | 599 |
| `neighbor_motion_weak` | 0.000 | 2643 | 87.958 | 599 |
| `rescue_with_budget_cap` | 0.000 | 2643 | 87.222 | 599 |

## Visualization

Comparison frames:

- `outputs/roi_policy_comparisons/phase1_2_workstream_c_neighbor_rescue_main_20260901_155233/frames`

## Decision

- Keep `rescue_with_budget_cap` as the current Workstream C candidate.
- Do not promote `neighbor_motion_weak` as-is because fallback and tensor cost increase too much.
- Keep `boundary_only_rescue` deferred unless a non-GT online proxy is defined.
- Continue to Workstream D with `practical_default`, `margin_plus`, and `rescue_with_budget_cap` as the relevant comparison set.
