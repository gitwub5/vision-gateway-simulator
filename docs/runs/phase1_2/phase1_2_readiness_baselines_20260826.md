# Phase 1.2 Readiness Baselines

## Scope

Phase 1.2 Stage A 진입 전에 true selected tile trace, run provenance, feedback mode를 동일 계약으로 고정했다.

- dataset: `configs/datasets/physicalai/physicalai_row0709_after3m.yaml`
- camera: `Camera_0002`
- start frame: `5400`
- limit: `600`
- target class: `person`
- diagnostics: `tile_trace`

각 manifest는 Git revision/dirty state, config SHA-256, resolved dataset segment와 ROI generator 설정을 포함한다.

## Runs

| Label | Run ID | Feedback |
|---|---|---|
| `tile_baseline` | `phase1_2_readiness_tile_mask_recall_12x12_f5400_600` | none |
| `practical_default` | `phase1_2_readiness_small_object_tile_recall_12x12_overlap_f5400_600` | none |
| `margin_plus` | `phase1_2_readiness_small_object_tile_recall_12x12_overlap_margin_plus_f5400_600` | none |
| `feedback_oracle` | `phase1_2_readiness_feedback_top2_oracle_f5400_600` | `oracle_gt` |
| `feedback_actual_yolo` | `phase1_2_readiness_feedback_top2_actual_yolo_f5400_600` | `actual_yolo` |

## Results

| Run | Contain | Missed GT | Small contain | Missed small | ROI/frame | Tile/frame | Tensor/frame | Reduction | Fallback | False ROI |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `tile_baseline` | 0.544 | 1312 | 0.498 | 1030 | 2.638 | 12.752 | 228360.0 | 0.855 | 20 | 0.556 |
| `practical_default` | 0.641 | 1035 | 0.602 | 816 | 2.638 | 12.752 | 263441.0 | 0.838 | 20 | 0.523 |
| `margin_plus` | 0.655 | 993 | 0.620 | 779 | 2.638 | 12.752 | 282164.2 | 0.829 | 20 | 0.514 |
| `feedback_oracle` | 0.759 | 693 | 0.770 | 472 | 3.753 | 12.752 | 274159.7 | 0.829 | 22 | 0.481 |
| `feedback_actual_yolo` | 0.704 | 852 | 0.691 | 634 | 3.522 | 12.752 | 292541.5 | 0.819 | 23 | 0.498 |

자동 생성한 원본 비교 결과:

- `outputs/roi_proposal_validation/phase1_2_readiness_comparison_f5400_600/summary.md`
- `outputs/roi_proposal_validation/phase1_2_readiness_comparison_f5400_600/summary.json`

## Interpretation

- 기존 Phase 1.1 수치와 일치해 `tile_trace` tier가 ROI/cost 결과를 바꾸지 않는 것을 확인했다.
- `practical_default`는 tile 수, ROI 수, fallback을 유지하면서 baseline보다 containment를 높인다.
- `margin_plus`는 추가 containment를 얻지만 tensor cost가 더 높다.
- oracle과 actual YOLO feedback은 machine-readable mode로 분리되며 직접 대체 관계로 해석하지 않는다.
- 모든 run에서 `tile_metadata.jsonl`과 `tile_metrics_available=true`를 확인했다.

## Entry Decision

Phase 1.2 Stage A는 위 run을 공식 baseline으로 사용한다. 이전 minimal diagnostics run은 aggregate cost 비교에는 사용할 수 있지만 true tile 위치 또는 tile-level 원인 분석에는 사용하지 않는다.
