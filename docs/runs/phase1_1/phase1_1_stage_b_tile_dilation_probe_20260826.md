# Phase 1.1 Stage B Tile Dilation Probe

## Scope

This probe checks whether small/partial target misses are better handled by including adjacent tile cells instead of only increasing pixel margin.

Dataset:

- `configs/datasets/physicalai/physicalai_row0709_after3m.yaml`

## Profiles

| Profile | Config | Description |
|---|---|---|
| overlap025 | `configs/roi_generator/phase1_1/small_object/profile_small_object_tile_recall_12x12_overlap.yaml` | Existing Stage B practical candidate |
| margin_plus035 | `configs/roi_generator/phase1_1/small_object/profile_small_object_tile_recall_12x12_overlap_margin_plus.yaml` | Pixel margin tuning probe |
| dilation_rows1 | `configs/roi_generator/phase1_1/small_object/profile_small_object_tile_recall_12x12_tile_dilation_v1.yaml` | Symmetric vertical tile dilation, up/down 1 cell |
| dilation_down1 | `configs/roi_generator/phase1_1/small_object/profile_small_object_tile_recall_12x12_tile_dilation_down_v1.yaml` | Downward-only tile dilation, 1 cell |

## 600-frame Results

| Profile | ROI contain | Missed GT | Small contain | Missed small | ROI/frame | Tile/frame | Tensor cost/frame | Effective reduction | Fallback |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| tile_baseline | 0.544 | 1312 | 0.498 | 1030 | 2.638 | 12.752 | 228360.0 | 0.855 | 20 |
| overlap025 | 0.641 | 1035 | 0.602 | 816 | 2.638 | 12.752 | 263441.0 | 0.838 | 20 |
| margin_plus035 | 0.655 | 993 | 0.620 | 779 | 2.638 | 12.752 | 282164.2 | 0.829 | 20 |
| dilation_rows1 | 0.633 | 1058 | 0.632 | 755 | 1.797 | 20.552 | 283406.7 | 0.678 | 110 |
| dilation_down1 | 0.670 | 950 | 0.647 | 724 | 2.248 | 16.693 | 299016.7 | 0.789 | 39 |

## Interpretation

Downward-only tile dilation is a valid Stage B tuning direction. It improves target ROI containment and small-object containment beyond margin-plus, but it also raises selected tile count, tensor cost, and fallback frames.

Symmetric vertical dilation is not a good candidate in this configuration. It improves small containment, but fallback rises to 110 frames and effective reduction drops to 0.678.

## Decision

Reject `dilation_down1` as active Stage B code for Phase 1.1.

The current practical default remains `small_object_tile_recall_12x12_overlap` with Keep/Tune status. `dilation_down1` improved containment, but the selected tile count, tensor cost, and fallback increase were too high for the current direction. The experimental code and configs were rolled back after recording this result.

## Visual Artifacts

- `outputs/roi_proposal_validation/stage_b_compare_visual_tile_dilation_f5400_80`
- Representative frame: `outputs/roi_proposal_validation/stage_b_compare_visual_tile_dilation_f5400_80/Camera_0002_f005444_roi_policy_compare.jpg`

## Full Tile Trace Check

Additional full-diagnostics runs were generated to inspect actual selected tile positions instead of reconstructed review overlays:

- `outputs/roi_proposal_validation/b_small_object_tile_recall_12x12_overlap_full_diag_f5400_600`
- `outputs/roi_proposal_validation/b_small_object_tile_recall_12x12_overlap_margin_plus_full_diag_f5400_600`
- `outputs/roi_proposal_validation/b_small_object_tile_recall_12x12_tile_dilation_down_full_diag_f5400_600`

The comparison artifact using actual `tile_metadata.jsonl` is:

- `outputs/roi_proposal_validation/stage_b_compare_visual_true_tile_trace_f5400_600`

For frame `5444`, the actual selected tile counts are:

- `overlap025`: 7
- `margin_plus035`: 7
- `dilation_down1`: 11

This confirms that the earlier wide blue tile overlay in minimal-diagnostics review images could include reconstructed cells. Use the full tile trace artifact when deciding whether a candidate truly selected neighboring tiles.
