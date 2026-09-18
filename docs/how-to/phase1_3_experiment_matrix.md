# Phase 1.3 Experiment Matrix

Phase 1.3은 domain별 dataset에 동일한 ROI Gate profile set을 적용해, 기존 motion/tile 계열이 어느 scene에서 붕괴하는지와 어떤 후보 family가 다음 phase 구현 대상으로 남는지 확인한다.

## Experiment Configs

| Coverage Group | Config |
|---|---|
| Traffic / parking | `configs/experiments/phase1_3_traffic_ua_detrac_mvi_39361.yaml` |
| Logistics / smart factory | `configs/experiments/phase1_3_logistics_physicalai_row0709_after3m.yaml` |
| Surveillance / security | `configs/experiments/phase1_3_surveillance_mot17_04.yaml` |
| Retail / space analytics | `configs/experiments/phase1_3_retail_mall_dataset.yaml` |
| General camera-motion stress | `configs/experiments/phase1_3_general_visdrone_uav0000086.yaml` |

Each config uses:

- `limit: 120`
- `diagnostics_level: tile_trace`
- output root: `outputs/roi_proposal_validation/`
- matrix summary root: `outputs/validation_matrices/`

## Profiles

The first matrix compares the Phase 1.1/1.2 representative profiles:

- `tile_baseline`
- `practical_default`
- `rescue_with_budget_cap`
- `fallback_reason_retune`
- `feedback_confidence_decay`

`feedback_confidence_decay` uses `full_frame_yolo` reference feedback and is expected to be slower than pure ROI proposal profiles.

For `configs/experiments/phase1_3_general_visdrone_uav0000086.yaml`, the first pass excludes `feedback_confidence_decay`. VisDrone includes classes such as bicycle, van, tricycle, awning-tricycle, and motor, while `configs/models/yolo_default.yaml` currently targets only `person`, `car`, `truck`, and `bus`. Keep VisDrone as a class-rich camera-motion stress test first, then add a separate feedback experiment after model class coverage is made explicit.

## Dry Run

Use dry-run before executing a matrix to validate paths, profile registry entries, and feedback-source contracts.

```bash
python experiments/run_validation_matrix.py \
  --experiment-config configs/experiments/phase1_3_traffic_ua_detrac_mvi_39361.yaml \
  --dry-run
```

## Execute One Dataset Matrix

```bash
python experiments/run_validation_matrix.py \
  --experiment-config configs/experiments/phase1_3_traffic_ua_detrac_mvi_39361.yaml
```

## Execute Only Non-Feedback Profiles

Use this first when checking broad domain behavior without full-frame YOLO feedback cost.

```bash
python experiments/run_validation_matrix.py \
  --experiment-config configs/experiments/phase1_3_traffic_ua_detrac_mvi_39361.yaml \
  --profile tile_baseline \
  --profile practical_default \
  --profile rescue_with_budget_cap \
  --profile fallback_reason_retune
```

## Hard Metrics

Treat these as the primary comparison metrics:

- `target_gt_roi_containment`
- `effective_input_area_reduction`
- `fallback_frame_rate`
- `no_roi_target_frame_count`
- small-object bucket containment

VisDrone is a camera-motion and small-object stress dataset. Do not interpret it as fixed-CCTV deployment performance.
