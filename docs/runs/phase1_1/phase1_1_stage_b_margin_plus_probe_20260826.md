# Phase 1.1 Stage B Margin Plus Probe

## Scope

This probe checks whether a slightly larger small-object tile overlap reduces boundary misses compared with the current practical default candidate.

Dataset:

- `configs/datasets/physicalai/physicalai_row0709_after3m.yaml`

Profiles:

- Baseline: `configs/roi_generator/phase1_1/small_object/profile_small_object_tile_recall_12x12_overlap.yaml`
- Probe: `configs/roi_generator/phase1_1/small_object/profile_small_object_tile_recall_12x12_overlap_margin_plus.yaml`

Change:

- `small_object_boost.tile_overlap_ratio`: `0.25 -> 0.35`

## Run

Output:

- `outputs/roi_proposal_validation/b_small_object_tile_recall_12x12_overlap_margin_plus_f5400_600`

Visual comparison:

- `outputs/roi_proposal_validation/stage_b_compare_visual_margin_plus_f5400_80`

## 600-frame Result

| Profile | ROI contain | Missed GT | Small contain | Missed small GT | ROI/frame | Tile/frame | Tensor cost/frame | Effective reduction | Fallback frames |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| overlap 0.25 | 0.641 | 1035 | 0.602 | 816 | 2.638 | 12.752 | 263441.0 | 0.838 | 20 |
| margin plus 0.35 | 0.655 | 993 | 0.620 | 779 | 2.638 | 12.752 | 282164.3 | 0.829 | 20 |

## Interpretation

`margin_plus 0.35` improves containment without increasing ROI count, tile count, or fallback count. The cost is a larger ROI boundary, reflected in tensor cost/frame increasing by about 7.1% and effective reduction dropping from 0.838 to 0.829.

Representative visual frame:

- `outputs/roi_proposal_validation/stage_b_compare_visual_margin_plus_f5400_80/Camera_0002_f005429_roi_policy_compare.jpg`

This supports the hypothesis that several misses are boundary misses rather than missing tile selection. Keep this as a Tune candidate, not yet the default, until it is checked against the current Stage D final candidate set and visual review.
