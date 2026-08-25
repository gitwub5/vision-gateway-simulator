# Phase 1.1 Stage B Small Object Policy Run

## Scope

Stage B started with a lean small-object slice:

- add object size bucket reporting to ROI proposal validation
- add `small_object_boost` config for tile ROI overlap
- add `profile_small_object_tile_recall.yaml`
- keep detailed diagnostics off by default

Object size buckets are based on GT bbox area divided by frame area:

- `small`: `< 0.01`
- `medium`: `< 0.05`
- `large`: `>= 0.05`
- `unknown`: frame size unavailable

## Validation

Commands:

- `.venv/bin/python -m unittest discover -s tests`
- `.venv/bin/python -m compileall common data_loader evaluation experiments gpu_inference roi_generator tests tools visualization`

Results:

- unittest discovery: 81 tests passed
- compileall: passed

Note: system `python3` does not have `numpy`; project `.venv/bin/python` has required dependencies and was used for validation.

## 120-frame PhysicalAI after3m quick runs

Dataset config:

- `configs/datasets/physicalai/physicalai_row0709_after3m.yaml`

Runs:

- `outputs/roi_proposal_validation/b_component_bbox_balanced_f5400_120`
- `outputs/roi_proposal_validation/b_tile_mask_recall_12x12_f5400_120`
- `outputs/roi_proposal_validation/b_small_object_tile_recall_f5400_120`

| Policy | ROI contain | Missed GT | Small contain | Missed small GT | Missed small frames | ROI/frame | Tile/frame | Tensor cost/frame | Effective reduction |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| component_bbox_balanced | 0.618 | 267 | 0.577 | 226 | 80 | 1.425 | 0.000 | 193356.4 | 0.898 |
| tile_mask_recall_12x12 | 0.758 | 169 | 0.757 | 130 | 37 | 2.383 | 13.542 | 308280.0 | 0.810 |
| small_object_tile_recall | 0.890 | 77 | 0.888 | 60 | 16 | 5.842 | 27.608 | 450342.5 | 0.708 |

## Decision

Stage B direction is valid: the small-object-specific tile path improves small GT containment and reduces missed small frames.

The current `small_object_tile_recall` profile is a high-recall candidate, not a default policy. It raises ROI count, tile count, tensor cost, and fallback frames enough that the next Stage B step should tune cost before promoting it:

- reduce grid or threshold aggressiveness
- lower `tile_overlap_ratio`
- add a stricter `max_tensor_batch_cost`
- compare against `tile_mask_recall_12x12` as the practical baseline

`full_frame_lowres_context + selected_tile_highres` is not implemented in Stage B. It should be reconsidered after Stage C feedback because it changes downstream inference composition rather than only ROI proposal.

## Cost tuning follow-up

Additional 120-frame tuning profiles:

- `profile_small_object_tile_recall_overlap025.yaml`: 16x16 grid, overlap `0.25`
- `profile_small_object_tile_recall_14x14.yaml`: 14x14 grid, overlap `0.25`
- `profile_small_object_tile_recall_12x12_overlap.yaml`: 12x12 grid, overlap `0.25`

120-frame comparison:

| Policy | ROI contain | Missed GT | Small contain | Missed small GT | Missed small frames | ROI/frame | Tile/frame | Tensor cost/frame | Effective reduction | Fallback frames |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| tile_mask_recall_12x12 | 0.758 | 169 | 0.757 | 130 | 37 | 2.383 | 13.542 | 308280.0 | 0.810 | 4 |
| small_object_tile_recall | 0.890 | 77 | 0.888 | 60 | 16 | 5.842 | 27.608 | 450342.5 | 0.708 | 8 |
| small_object_tile_recall_overlap025 | 0.886 | 80 | 0.888 | 60 | 16 | 5.842 | 27.608 | 400805.0 | 0.732 | 8 |
| small_object_tile_recall_14x14 | 0.750 | 175 | 0.710 | 155 | 71 | 3.200 | 17.417 | 283785.2 | 0.830 | 3 |
| small_object_tile_recall_12x12_overlap | 0.808 | 134 | 0.785 | 115 | 33 | 2.383 | 13.542 | 346343.3 | 0.791 | 4 |

120-frame decision:

- `14x14` is rejected because small containment regresses below `tile_mask_recall_12x12`.
- `16x16 overlap025` keeps high recall but remains expensive in ROI count, tile count, and fallback.
- `12x12_overlap` is the practical tuning candidate because it improves small containment without increasing ROI/frame, tile/frame, or fallback frames.

600-frame practical candidate comparison:

| Policy | ROI contain | Missed GT | Small contain | Missed small GT | Missed small frames | ROI/frame | Tile/frame | Tensor cost/frame | Effective reduction | Fallback frames |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| tile_mask_recall_12x12 | 0.544 | 1312 | 0.498 | 1030 | 468 | 2.638 | 12.752 | 228360.0 | 0.855 | 20 |
| small_object_tile_recall_12x12_overlap | 0.641 | 1035 | 0.602 | 816 | 443 | 2.638 | 12.752 | 263441.0 | 0.838 | 20 |

600-frame decision:

`profile_small_object_tile_recall_12x12_overlap.yaml` should be kept as the Stage B practical candidate. It improves small containment and missed small GT while keeping ROI count, selected tile count, and fallback count unchanged. The tradeoff is higher tensor cost per frame and lower effective area reduction, so it should stay as a tuned profile rather than replace `tile_mask_recall_12x12` by default.

## Closure

Stage B is closed with two retained profiles:

- `profile_small_object_tile_recall.yaml`: high-recall, non-default candidate
- `profile_small_object_tile_recall_12x12_overlap.yaml`: practical small-object candidate

The temporary tuning profiles were removed from `configs/roi_generator/` after their results were recorded here:

- `profile_small_object_tile_recall_14x14.yaml`
- `profile_small_object_tile_recall_overlap025.yaml`

`min_final_roi_width/height` was not connected to size buckets. The gate does not know GT bucket labels online, and applying fixed minimum ROI dimensions based on offline buckets would make the policy less direct than tile overlap. The existing minimum ROI dimensions remain available as component-bbox tuning options.

Next stage entry:

- Stage C should start from reference detector feedback, not more Stage B diagnostics.
- The remaining miss cases are likely motion-only limitations: static targets, sparse motion, and stale target context.
