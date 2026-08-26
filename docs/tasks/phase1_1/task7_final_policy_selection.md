# Phase 1.1 Task 7: Final Policy Selection

## Scope

Task 7 closes Phase 1.1 as a policy-family selection pass.

It collects 600-frame PhysicalAI after3m results and assigns Keep/Tune/Disable decisions.

## Final Decisions

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
- remains open for overlap/margin tuning because the `margin_plus 0.35` probe improves containment at higher tensor cost

## Challenger

Keep `feedback_assisted_tile_12x12_overlap_top2` as the strongest realistic challenger.

Actual YOLO feedback improved containment over the practical default, but raised ROI/tensor/fallback cost.

## Closure

Phase 1.1 is closed as successful for ROI proposal policy selection.

Remaining work is Phase 1.2/backlog:

- feedback confidence decay
- stale refresh/fallback policy
- no-ROI target risk refresh
- broader E2E/OD-VIRAT verification
- Jetson/DeepStream cost coefficient calibration

## Outputs

Run logs:

```text
docs/runs/phase1_1/phase1_1_stage_d_final_policy_selection_20260825.md
docs/runs/phase1_1/phase1_1_final_closure_20260825.md
```

## Verification

```bash
.venv/bin/python -m unittest discover -s tests
.venv/bin/python -m compileall common data_loader evaluation experiments gpu_inference roi_generator tests tools visualization
```
