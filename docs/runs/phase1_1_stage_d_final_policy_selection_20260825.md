# Phase 1.1 Stage D Final Policy Selection

## Scope

Stage D compares the 600-frame PhysicalAI after3m ROI proposal results gathered through Stage A-C.

Dataset:

- `configs/datasets/physicalai/physicalai_row0709_after3m.yaml`

Comparison runs:

- `outputs/roi_proposal_validation/d_component_bbox_balanced_f5400_600`
- `outputs/roi_proposal_validation/d_hybrid_component_tile_cost_f5400_600`
- `outputs/roi_proposal_validation/b_tile_mask_recall_12x12_f5400_600`
- `outputs/roi_proposal_validation/b_small_object_tile_recall_12x12_overlap_f5400_600`
- `outputs/roi_proposal_validation/c_feedback_assisted_tile_12x12_overlap_top2_f5400_600`
- `outputs/roi_proposal_validation/c_actual_yolo_feedback_top2_f5400_600`

## 600-frame Comparison

| Policy/Profile | ROI contain | Missed GT | Small contain | Missed small GT | Missed small frames | ROI/frame | Tile/frame | Tensor cost/frame | Effective reduction | Fallback frames | Feedback assist/frame |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| component_bbox_balanced | 0.441 | 1610 | 0.340 | 1353 | 530 | 1.468 | 0.000 | 141416.9 | 0.923 | 0 | 0.000 |
| hybrid_component_tile_cost | 0.440 | 1611 | 0.340 | 1354 | 530 | 1.468 | 9.615 | 141263.6 | 0.924 | 0 | 0.000 |
| tile_mask_recall_12x12 | 0.544 | 1312 | 0.498 | 1030 | 468 | 2.638 | 12.752 | 228360.0 | 0.855 | 20 | 0.000 |
| small_object_tile_recall_12x12_overlap | 0.641 | 1035 | 0.602 | 816 | 443 | 2.638 | 12.752 | 263441.0 | 0.838 | 20 | 0.000 |
| feedback_oracle_top2 | 0.759 | 693 | 0.770 | 472 | 283 | 3.753 | 12.752 | 274159.7 | 0.829 | 22 | 1.148 |
| feedback_actual_yolo_top2 | 0.704 | 852 | 0.691 | 634 | 386 | 3.522 | 12.752 | 292541.5 | 0.819 | 23 | 0.940 |

## Decisions

| Policy/Profile | Decision | Role |
|---|---|---|
| component_bbox_balanced | Keep | low-cost baseline |
| hybrid_component_tile_cost | Disable | cost is low, but recall does not improve over component baseline |
| tile_mask_recall_12x12 | Keep | practical tile baseline |
| small_object_tile_recall_12x12_overlap | Keep | small-object practical candidate |
| feedback_assisted_tile_12x12_overlap_top2 | Keep/Tune | strongest realistic candidate with actual detector feedback |
| feedback_assisted_tile_12x12_overlap | Tune | high-recall reference, too costly for practical default |
| small_object_tile_recall | Tune | high-recall small-object reference, too costly for practical default |

## Default Recommendation

Use `small_object_tile_recall_12x12_overlap` as the current practical default candidate for Phase 1.1.

Reason:

- materially improves target and small-object containment over `tile_mask_recall_12x12`
- keeps ROI/frame, tile/frame, and fallback count unchanged relative to `tile_mask_recall_12x12`
- avoids the extra actual detector dependency and higher fallback count of feedback-assisted profiles

Use `feedback_assisted_tile_12x12_overlap_top2` as a Stage D challenger, not the default.

Reason:

- actual YOLO feedback improves target containment from `0.641` to `0.704`
- small containment improves from `0.602` to `0.691`
- cost rises: ROI/frame `2.638 -> 3.522`, tensor cost/frame `263441.0 -> 292541.5`, fallback frames `20 -> 23`

## Stage C Revisit Items

After Stage D, revisit Stage C only for cost-control decisions:

- feedback/component/tile overlap dedup or scoring
- confidence decay beyond TTL and minimum confidence
- feedback stale refresh reason
- actual detector output integration in full E2E inference validation

Do not add more diagnostics before one of those policy decisions is needed.
