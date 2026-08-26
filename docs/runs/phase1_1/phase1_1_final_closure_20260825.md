# Phase 1.1 Final Closure

## Scope

This closes Phase 1.1 as a policy-family selection pass.

The phase compared:

- component bbox baseline
- tile-first recall baseline
- small-object tile overlap profile
- reference feedback-assisted profile
- cost/budget fallback contract

## Final Policy Decisions

| Policy/Profile | Decision | Role |
|---|---|---|
| `component_bbox_balanced` | Keep | low-cost baseline |
| `tile_mask_recall_12x12` | Keep | practical tile baseline |
| `small_object_tile_recall_12x12_overlap` | Keep/Tune | Phase 1.1 practical default candidate; overlap/margin tuning remains open |
| `feedback_assisted_tile_12x12_overlap_top2` | Keep/Tune | strongest realistic challenger, needs cost tuning before default |
| `feedback_assisted_tile_12x12_overlap` | Tune | high-recall feedback reference |
| `small_object_tile_recall` | Tune | high-recall small-object reference |
| `hybrid_component_tile_cost` | Disable | recall does not improve over component baseline |

## Practical Default

Use `small_object_tile_recall_12x12_overlap` as the current practical default candidate with Keep/Tune status.

Reason:

- improves target and small-object containment over `tile_mask_recall_12x12`
- keeps ROI/frame, tile/frame, and fallback count unchanged relative to `tile_mask_recall_12x12`
- does not require an actual detector feedback dependency
- remains open for overlap/margin tuning because `margin_plus 0.35` improves containment at higher tensor cost

## Challenger

Keep `feedback_assisted_tile_12x12_overlap_top2` as the strongest realistic challenger.

Actual YOLO feedback improves containment over the practical default, but raises cost:

- target containment: `0.641 -> 0.704`
- small containment: `0.602 -> 0.691`
- missed small GT: `816 -> 634`
- ROI/frame: `2.638 -> 3.522`
- tensor cost/frame: `263441.0 -> 292541.5`
- fallback frames: `20 -> 23`

## Deferred

These are not required to close Phase 1.1:

- feedback confidence decay
- feedback stale refresh/fallback reason
- no-ROI target risk refresh
- adaptive refresh reason redesign
- E2E/OD-VIRAT broader verification
- Jetson/DeepStream cost coefficient calibration

They are Phase 1.2/backlog candidates.

## Validation

Final code validation:

- `.venv/bin/python -m unittest discover -s tests`
- `.venv/bin/python -m compileall common data_loader evaluation experiments gpu_inference roi_generator tests tools visualization`

Status:

- Phase 1.1 is closed as successful for ROI proposal policy selection.
