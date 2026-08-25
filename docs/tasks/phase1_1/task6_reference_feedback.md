# Phase 1.1 Task 6: Reference Feedback

## Scope

Task 6 adds reference detector feedback as a candidate ROI source.

The goal is to test whether periodic/full-frame detector boxes can reduce motion-only misses without building a full tracker or online controller.

## Implementation

- Added `roi_generator/core/feedback.py`.
- Added `ReferenceFeedbackCache`.
- Added `RuleBasedRoiGenerator.update_reference_feedback(...)`.
- Added feedback config:
  - `reference_feedback.enabled`
  - `ttl_frames`
  - `min_confidence`
  - `margin_ratio`
  - `max_candidates_per_frame`
  - `duplicate_overlap_ratio`
- Added feedback counters to gate/frame/report metadata:
  - `feedback_candidate_count`
  - `feedback_assisted_roi_count`
  - `feedback_active_track_count`
  - `feedback_stale_track_count`
- Added ROI proposal validation feedback sources:
  - `none`
  - `ground_truth`
  - `full_frame_yolo`
- Added actual full-frame YOLO feedback smoke path for proposal validation.
- Added profiles:
  - `profile_feedback_assisted_tile_12x12_overlap.yaml`
  - `profile_feedback_assisted_tile_12x12_overlap_top1.yaml`
  - `profile_feedback_assisted_tile_12x12_overlap_top2.yaml`
  - `profile_feedback_assisted_tile_12x12_overlap_top2_dedup06.yaml`

## Decision

Keep `feedback_assisted_tile_12x12_overlap_top2` as Keep/Tune.

Actual YOLO feedback improved target and small-object containment over the practical default, but cost increased.

`feedback_assisted_tile_12x12_overlap` remains a high-recall, higher-cost reference.

`top2_dedup06` is not promoted. Aggressive overlap dedup reduced cost, but removed most actual YOLO feedback benefit.

## Deferred

Deferred to Phase 1.2/backlog:

- confidence decay
- stale feedback refresh/fallback reason
- no-ROI target risk refresh
- adaptive refresh reason redesign
- broader E2E feedback wiring

## Outputs

Run log:

```text
docs/runs/phase1_1_stage_c_reference_feedback_20260825.md
```

## Verification

```bash
.venv/bin/python -m unittest discover -s tests
.venv/bin/python -m compileall common data_loader evaluation experiments gpu_inference roi_generator tests tools visualization
```
