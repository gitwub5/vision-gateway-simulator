# Phase 1.1 Stage B/C True Tile Visual Overview

## Scope

Phase 1.2로 넘어가기 전에 Phase 1.1의 주요 tile-based 후보를 실제 `tile_metadata.jsonl` 기반으로 한 화면에서 비교한다.

Dataset:

- `configs/datasets/physicalai/physicalai_row0709_after3m.yaml`
- start frame: 5400
- limit: 600 frames
- diagnostics level: `full`

## Compared Runs

| Label | Run |
|---|---|
| `tile_baseline` | `outputs/roi_proposal_validation/a1_tile_mask_recall_12x12_full_diag_f5400_600` |
| `stage_b_overlap` | `outputs/roi_proposal_validation/b_small_object_tile_recall_12x12_overlap_full_diag_f5400_600` |
| `stage_b_margin` | `outputs/roi_proposal_validation/b_small_object_tile_recall_12x12_overlap_margin_plus_full_diag_f5400_600` |
| `stage_c_oracle_top2` | `outputs/roi_proposal_validation/c_feedback_assisted_tile_12x12_overlap_top2_full_diag_f5400_600` |
| `stage_c_actual_yolo_top2` | `outputs/roi_proposal_validation/c_actual_yolo_feedback_top2_full_diag_f5400_600` |

## Summary

| Profile | Contain | Missed GT | Missed frames | ROI/frame | Tile/frame | Tensor/frame | Reduction | Fallback | False ROI | FB/frame |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `tile_mask_recall_12x12` | 0.544 | 1312 | 506 | 2.638 | 12.752 | 228360.0 | 0.855 | 20 | 880 | 0.000 |
| `small_object_tile_recall_12x12_overlap` | 0.641 | 1035 | 457 | 2.638 | 12.752 | 263441.0 | 0.838 | 20 | 828 | 0.000 |
| `small_object_tile_recall_12x12_overlap_margin_plus` | 0.655 | 993 | 453 | 2.638 | 12.752 | 282164.2 | 0.829 | 20 | 813 | 0.000 |
| `feedback_assisted_tile_12x12_overlap_top2_oracle` | 0.759 | 693 | 356 | 3.753 | 12.752 | 274159.7 | 0.829 | 22 | 1084 | 1.148 |
| `feedback_assisted_tile_12x12_overlap_top2_actual_yolo` | 0.704 | 852 | 432 | 3.522 | 12.752 | 292541.5 | 0.819 | 23 | 1052 | 0.940 |

## Visual Artifact

- `outputs/roi_proposal_validation/phase1_1_stage_b_c_true_tile_overview_f5400_600`
- images: 100
- representative image: `outputs/roi_proposal_validation/phase1_1_stage_b_c_true_tile_overview_f5400_600/Camera_0002_f005429_roi_policy_compare.jpg`

## Visual Encoding

- yellow: final tile ROI / downstream inference area
- blue: actual selected tile cell from `tile_metadata.jsonl`
- green: feedback ROI / reference detector box
- magenta: contained GT
- red: missed GT

## Interpretation

Stage B overlap clearly improves containment over the A1 tile baseline without increasing selected tile count. `margin_plus 0.35` recovers additional boundary misses, but at higher tensor cost and lower reduction.

Stage C feedback improves containment further, but both oracle and actual YOLO variants increase ROI count, false ROI count, fallback frames, and feedback dependency. This supports the Phase 1.1 decision: keep `small_object_tile_recall_12x12_overlap` as the practical default candidate and keep `feedback_assisted_tile_12x12_overlap_top2` as a Keep/Tune challenger.
