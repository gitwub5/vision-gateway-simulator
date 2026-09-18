# Phase 1.3 Baseline Failure Map - 2026-09-16

## Scope

Phase 1.3의 첫 실행으로, 현재 구현된 `grayscale -> resize -> motion map -> tile/ROI` 계열 profile을 5개 domain dataset에 적용했다.

이 run의 목적은 profile을 고도화하는 것이 아니라, 현재 motion/tile baseline이 어떤 domain에서 붕괴하는지 확인하는 것이다.

공통 조건:

- Frame limit: 120
- Diagnostics: `tile_trace`
- Output root: `outputs/roi_proposal_validation/`
- Matrix root: `outputs/validation_matrices/`

## Matrix Runs

| Coverage Group | Matrix root | Profiles |
|---|---|---|
| Traffic / parking | `outputs/validation_matrices/phase1_3_traffic_ua_detrac_mvi_39361_20260916_151639` | 5 |
| Logistics / smart factory | `outputs/validation_matrices/phase1_3_logistics_physicalai_row0709_after3m_20260916_151727` | 5 |
| Surveillance / security | `outputs/validation_matrices/phase1_3_surveillance_mot17_04_20260916_151814` | 5 |
| Retail / space analytics | `outputs/validation_matrices/phase1_3_retail_mall_dataset_20260916_151854` | 5 |
| General camera-motion stress | `outputs/validation_matrices/phase1_3_general_visdrone_uav0000086_20260916_151928` | 4 |

VisDrone excludes `feedback_confidence_decay` in the first pass because the default YOLO model class coverage does not match the full VisDrone class set.

## Best Profile by Domain

| Coverage Group | Best profile by containment | Containment | Missed GT | Reduction | Fallback frames | Interpretation |
|---|---|---:|---:|---:|---:|---|
| Traffic / parking | all tied | 0.000 | 505 | 0.000 | 119 | Current motion/tile pipeline fails as an ROI proposal source on this UA-DETRAC segment. |
| Logistics / smart factory | `feedback_confidence_decay` | 0.891 | 76 | 0.772 | 4 | Current family is partially viable here; `fallback_reason_retune` is close without YOLO feedback. |
| Surveillance / security | `tile_baseline` | 0.005 | 4920 | 0.004 | 118 | Dense MOT17 person scene collapses to fallback/no-ROI behavior. |
| Retail / space analytics | all tied | 0.000 | 3143 | 0.000 | 119 | Mall proxy-box targets are not captured by current motion/tile profiles. |
| General camera-motion stress | all tied | 0.000 | 4490 | 0.000 | 119 | Camera motion/small-object VisDrone segment is outside current baseline capability. |

## Full Matrix Summary

### Traffic / Parking: UA-DETRAC MVI_39361

| Profile | Feedback | Containment | Missed GT | ROI/frame | Tile/frame | Reduction | Fallback |
|---|---|---:|---:|---:|---:|---:|---:|
| `tile_baseline` | none | 0.000 | 505 | 0.000 | 103.792 | 0.000 | 119 |
| `practical_default` | none | 0.000 | 505 | 0.000 | 103.792 | 0.000 | 119 |
| `rescue_with_budget_cap` | none | 0.000 | 505 | 0.000 | 106.125 | 0.000 | 119 |
| `fallback_reason_retune` | none | 0.000 | 505 | 0.000 | 106.125 | 0.000 | 119 |
| `feedback_confidence_decay` | actual_yolo | 0.000 | 505 | 0.000 | 106.125 | 0.000 | 119 |

### Logistics / Smart Factory: PhysicalAI row0709_after3m

| Profile | Feedback | Containment | Missed GT | ROI/frame | Tile/frame | Reduction | Fallback |
|---|---|---:|---:|---:|---:|---:|---:|
| `tile_baseline` | none | 0.758 | 169 | 2.383 | 13.542 | 0.810 | 4 |
| `practical_default` | none | 0.808 | 134 | 2.383 | 13.542 | 0.791 | 4 |
| `rescue_with_budget_cap` | none | 0.881 | 83 | 2.275 | 14.092 | 0.783 | 4 |
| `fallback_reason_retune` | none | 0.890 | 77 | 2.292 | 14.092 | 0.787 | 3 |
| `feedback_confidence_decay` | actual_yolo | 0.891 | 76 | 2.842 | 14.092 | 0.772 | 4 |

### Surveillance / Security: MOT17Det MOT17-04

| Profile | Feedback | Containment | Missed GT | ROI/frame | Tile/frame | Reduction | Fallback |
|---|---|---:|---:|---:|---:|---:|---:|
| `tile_baseline` | none | 0.005 | 4920 | 0.050 | 53.975 | 0.004 | 118 |
| `practical_default` | none | 0.000 | 4947 | 0.000 | 53.975 | 0.000 | 119 |
| `rescue_with_budget_cap` | none | 0.000 | 4947 | 0.000 | 56.158 | 0.000 | 119 |
| `fallback_reason_retune` | none | 0.000 | 4947 | 0.000 | 56.158 | 0.000 | 119 |
| `feedback_confidence_decay` | actual_yolo | 0.000 | 4947 | 0.000 | 56.158 | 0.000 | 119 |

### Retail / Space Analytics: Mall Dataset

| Profile | Feedback | Containment | Missed GT | ROI/frame | Tile/frame | Reduction | Fallback |
|---|---|---:|---:|---:|---:|---:|---:|
| `tile_baseline` | none | 0.000 | 3143 | 0.000 | 95.058 | 0.000 | 119 |
| `practical_default` | none | 0.000 | 3143 | 0.000 | 95.058 | 0.000 | 119 |
| `rescue_with_budget_cap` | none | 0.000 | 3143 | 0.000 | 97.833 | 0.000 | 119 |
| `fallback_reason_retune` | none | 0.000 | 3143 | 0.000 | 97.833 | 0.000 | 119 |
| `feedback_confidence_decay` | actual_yolo | 0.000 | 3143 | 0.000 | 97.833 | 0.000 | 119 |

Mall uses head-point-derived proxy boxes, so follow-up analysis should also include point containment or a proxy-box sensitivity check.

### General Camera-Motion Stress: VisDrone-VID uav0000086_00000_v

| Profile | Feedback | Containment | Missed GT | ROI/frame | Tile/frame | Reduction | Fallback |
|---|---|---:|---:|---:|---:|---:|---:|
| `tile_baseline` | none | 0.000 | 4490 | 0.000 | 121.492 | 0.000 | 119 |
| `practical_default` | none | 0.000 | 4490 | 0.000 | 121.492 | 0.000 | 119 |
| `rescue_with_budget_cap` | none | 0.000 | 4490 | 0.000 | 123.017 | 0.000 | 119 |
| `fallback_reason_retune` | none | 0.000 | 4490 | 0.000 | 123.017 | 0.000 | 119 |

## Findings

1. Current motion/tile profiles are not a general ROI proposal solution across the selected domains.
2. PhysicalAI is the only dataset where the current family shows meaningful containment and area reduction.
3. Traffic, surveillance, retail, and camera-motion stress all show near-total baseline failure under this first matrix.
4. Full-frame YOLO feedback did not rescue UA-DETRAC, MOT17Det, or Mall in this matrix. That suggests the issue is not only profile retuning; it may also involve target class/domain mismatch, feedback confidence behavior, or signal-to-ROI conversion.
5. The next Phase 1.3 tests should prioritize Temporal Gate and Static Zone / Camera Prior, then Tracker Memory and Lightweight Visual Signal probes.

## Execution Notes

The first Traffic matrix attempt failed only on `feedback_confidence_decay` because `yolov8n.pt` was not available at the repo root and Ultralytics attempted a network download. After network access was approved, `yolov8n.pt` was downloaded and subsequent feedback runs completed.

`yolov8n.pt` is a local model artifact and is not tracked by git.
