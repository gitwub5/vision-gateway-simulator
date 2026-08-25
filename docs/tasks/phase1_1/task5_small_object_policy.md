# Phase 1.1 Task 5: Small Object Policy

## Scope

Task 5 checks whether small-target misses are better handled by a small-object tile path than by simple component padding.

## Implementation

- Added object size bucket metrics to ROI proposal reports.
- Bucket definition:
  - `small`: GT bbox area / frame area `< 0.01`
  - `medium`: `< 0.05`
  - `large`: `>= 0.05`
  - `unknown`: missing frame size
- Added `small_object_boost` config.
- Added tile ROI overlap support:
  - `tile_overlap_ratio`
- Added profiles:
  - `profile_small_object_tile_recall.yaml`
  - `profile_small_object_tile_recall_12x12_overlap.yaml`

Temporary tuning profiles were tested and removed after recording results:

- `profile_small_object_tile_recall_14x14.yaml`
- `profile_small_object_tile_recall_overlap025.yaml`

## Decision

Keep `small_object_tile_recall_12x12_overlap` as the Phase 1.1 practical default candidate.

It improves small-object containment relative to `tile_mask_recall_12x12` while keeping ROI/frame, tile/frame, and fallback count unchanged.

`small_object_tile_recall` remains a high-recall, non-default reference profile.

## Outputs

Run log:

```text
docs/runs/phase1_1_stage_b_small_object_policy_20260825.md
```

Retained profiles:

```text
configs/roi_generator/phase1_1/small_object/profile_small_object_tile_recall.yaml
configs/roi_generator/phase1_1/small_object/profile_small_object_tile_recall_12x12_overlap.yaml
```

## Verification

```bash
.venv/bin/python -m unittest discover -s tests
.venv/bin/python -m compileall common data_loader evaluation experiments gpu_inference roi_generator tests tools visualization
```
