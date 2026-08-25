# Phase 1.1 Stage C Reference Feedback C0

## Scope

C0 implements the reference feedback contract without running detector inference inside the ROI gate.

Implemented:

- `reference_feedback.enabled` config
- `ReferenceFeedbackCache` for externally supplied full-frame detections
- TTL/confidence/margin/max-candidate filtering
- feedback ROI candidate append path in `RuleBasedRoiGenerator`
- gate/frame/policy metadata counters:
  - `feedback_candidate_count`
  - `feedback_assisted_roi_count`
  - `feedback_active_track_count`
  - `feedback_stale_track_count`
- ROI proposal report summary fields for feedback counts
- `profile_feedback_assisted_tile_12x12_overlap.yaml`

Not implemented in C0:

- validation runner connection from full-frame detector outputs to the feedback cache
- score fusion between component/tile candidates and feedback candidates
- confidence decay beyond TTL and minimum confidence filtering
- feedback-driven refresh/fallback policy

## Validation

Targeted tests:

- `.venv/bin/python -m unittest tests.roi_generator_tests.test_roi_generator tests.roi_generator_tests.test_roi_metadata tests.evaluation_tests.test_evaluation`

Result:

- 44 tests passed

## Decision

C0 is a contract implementation. It is ready for C1 runner wiring.

The next step is to connect full-frame detector outputs from periodic/full-frame checks into `RuleBasedRoiGenerator.update_reference_feedback(...)`, then compare:

- `tile_mask_recall_12x12`
- `small_object_tile_recall_12x12_overlap`
- `feedback_assisted_tile_12x12_overlap`

Primary C1 metrics should remain lean:

- target GT ROI containment
- missed target GT
- no-ROI target frames
- small bucket containment regression
- feedback-assisted ROI count/frame
- effective reduction and tensor cost
- full-frame/fallback count

## C1 ROI proposal oracle feedback

C1 connected ROI proposal validation to the feedback cache with:

- `--reference-feedback-source ground_truth`

This is an oracle proxy for proposal-stage validation. It verifies that the feedback contract can reduce missed targets when a reference source is available, but it is not a replacement for E2E detector-output wiring.

Runs:

- `outputs/roi_proposal_validation/c_feedback_assisted_tile_12x12_overlap_f5400_120`
- `outputs/roi_proposal_validation/c_feedback_assisted_tile_12x12_overlap_f5400_600`

120-frame comparison against Stage B practical candidate:

| Policy | ROI contain | Missed GT | Small contain | Missed small GT | Missed small frames | ROI/frame | Tile/frame | Tensor cost/frame | Effective reduction | Fallback frames | Feedback assist/frame |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| small_object_tile_recall_12x12_overlap | 0.808 | 134 | 0.785 | 115 | 33 | 2.383 | 13.542 | 346343.3 | 0.791 | 4 | 0.000 |
| feedback_assisted_tile_12x12_overlap | 0.843 | 110 | 0.830 | 91 | 30 | 3.392 | 13.542 | 380007.4 | 0.775 | 4 | 1.042 |

600-frame comparison:

| Policy | ROI contain | Missed GT | Small contain | Missed small GT | Missed small frames | ROI/frame | Tile/frame | Tensor cost/frame | Effective reduction | Fallback frames | Feedback assist/frame |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| small_object_tile_recall_12x12_overlap | 0.641 | 1035 | 0.602 | 816 | 443 | 2.638 | 12.752 | 263441.0 | 0.838 | 20 | 0.000 |
| feedback_assisted_tile_12x12_overlap | 0.797 | 585 | 0.826 | 356 | 201 | 4.208 | 12.752 | 293731.5 | 0.810 | 28 | 1.703 |

Decision:

Reference feedback is promising for target recall and especially small-object containment. On the 600-frame oracle proxy run, missed small GT drops from `816` to `356`.

The current profile is not cost-clean yet. ROI/frame rises from `2.638` to `4.208`, effective reduction drops from `0.838` to `0.810`, and fallback frames rise from `20` to `28` due to `batch_slot_overflow`.

Next Stage C step:

- tune feedback candidate limits and budget contract before promoting the profile
- start with `max_candidates_per_frame: 1-2` or stricter feedback overlap/dedup
- then wire actual full-frame detector outputs in E2E validation

## C1.1 feedback cost tuning

Additional profiles:

- `profile_feedback_assisted_tile_12x12_overlap_top1.yaml`: `max_candidates_per_frame: 1`, `margin_ratio: 0.1`
- `profile_feedback_assisted_tile_12x12_overlap_top2.yaml`: `max_candidates_per_frame: 2`, `margin_ratio: 0.1`

120-frame comparison:

| Policy | ROI contain | Missed GT | Small contain | Missed small GT | Missed small frames | ROI/frame | Tensor cost/frame | Effective reduction | Fallback frames | Feedback assist/frame |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| small_object_tile_recall_12x12_overlap | 0.808 | 134 | 0.785 | 115 | 33 | 2.383 | 346343.3 | 0.791 | 4 | 0.000 |
| feedback_assisted_tile_12x12_overlap | 0.843 | 110 | 0.830 | 91 | 30 | 3.392 | 380007.4 | 0.775 | 4 | 1.042 |
| feedback_assisted_tile_12x12_overlap_top1 | 0.818 | 127 | 0.798 | 108 | 33 | 2.592 | 348345.5 | 0.790 | 4 | 0.208 |
| feedback_assisted_tile_12x12_overlap_top2 | 0.823 | 124 | 0.803 | 105 | 30 | 3.058 | 361242.1 | 0.784 | 4 | 0.692 |

120-frame decision:

- `top1` is cost-clean but recall gain is modest.
- `top2` keeps clearer recall gain while staying below the top3 profile cost.
- `top2` was selected for 600-frame validation.

600-frame comparison:

| Policy | ROI contain | Missed GT | Small contain | Missed small GT | Missed small frames | ROI/frame | Tensor cost/frame | Effective reduction | Fallback frames | Feedback assist/frame |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| small_object_tile_recall_12x12_overlap | 0.641 | 1035 | 0.602 | 816 | 443 | 2.638 | 263441.0 | 0.838 | 20 | 0.000 |
| feedback_assisted_tile_12x12_overlap | 0.797 | 585 | 0.826 | 356 | 201 | 4.208 | 293731.5 | 0.810 | 28 | 1.703 |
| feedback_assisted_tile_12x12_overlap_top2 | 0.759 | 693 | 0.770 | 472 | 283 | 3.753 | 274159.7 | 0.829 | 22 | 1.148 |

Decision:

`feedback_assisted_tile_12x12_overlap_top2` is the current Stage C practical candidate. It keeps a large recall improvement over the Stage B practical candidate while reducing batch overflow compared with the top3 feedback profile:

- missed small GT improves from `816` to `472`
- batch overflow fallback drops from `8` frames in top3 feedback to `2` frames
- effective reduction is closer to Stage B practical: `0.829` vs `0.838`

`feedback_assisted_tile_12x12_overlap` remains a high-recall candidate, not the default practical candidate.

## C2 actual full-frame YOLO feedback smoke

C2 used actual full-frame YOLO outputs as the reference feedback source:

- `--reference-feedback-source full_frame_yolo`
- `--model-config configs/models/yolo_default.yaml`

Runs:

- `outputs/roi_proposal_validation/c_actual_yolo_feedback_top2_f5400_120`
- `outputs/roi_proposal_validation/c_actual_yolo_feedback_top2_f5400_600`

120-frame comparison:

| Policy | ROI contain | Missed GT | Small contain | Missed small GT | Missed small frames | ROI/frame | Tensor cost/frame | Effective reduction | Fallback frames | Feedback assist/frame | YOLO calls | Feedback detections |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| small_object_tile_recall_12x12_overlap | 0.808 | 134 | 0.785 | 115 | 33 | 2.383 | 346343.3 | 0.791 | 4 | 0.000 | 0 | 0 |
| oracle feedback top2 | 0.823 | 124 | 0.803 | 105 | 30 | 3.058 | 361242.1 | 0.784 | 4 | 0.692 | 0 | 0 |
| actual YOLO feedback top2 | 0.823 | 124 | 0.803 | 105 | 31 | 3.042 | 376596.1 | 0.777 | 4 | 0.692 | 5 | 24 |

600-frame comparison:

| Policy | ROI contain | Missed GT | Small contain | Missed small GT | Missed small frames | ROI/frame | Tensor cost/frame | Effective reduction | Fallback frames | Feedback assist/frame | YOLO calls | Feedback detections |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| small_object_tile_recall_12x12_overlap | 0.641 | 1035 | 0.602 | 816 | 443 | 2.638 | 263441.0 | 0.838 | 20 | 0.000 | 0 | 0 |
| oracle feedback top2 | 0.759 | 693 | 0.770 | 472 | 283 | 3.753 | 274159.7 | 0.829 | 22 | 1.148 | 0 | 0 |
| actual YOLO feedback top2 | 0.704 | 852 | 0.691 | 634 | 386 | 3.522 | 292541.5 | 0.819 | 23 | 0.940 | 24 | 92 |

Decision:

Actual full-frame YOLO feedback is weaker than oracle feedback, but it still improves over the Stage B practical candidate:

- small containment improves from `0.602` to `0.691`
- missed small GT drops from `816` to `634`
- target ROI containment improves from `0.641` to `0.704`

The cost tradeoff remains visible:

- ROI/frame rises from `2.638` to `3.522`
- tensor cost/frame rises from `263441.0` to `292541.5`
- fallback frames rise from `20` to `23`

Stage C should close with `feedback_assisted_tile_12x12_overlap_top2` as Keep/Tune, not as the default. It is a realistic candidate for Stage D final comparison, with the open caveat that actual detector confidence/coverage limits the oracle gain.

## C1.2 feedback overlap dedup decision

Added:

- `reference_feedback.duplicate_overlap_ratio`
- `profile_feedback_assisted_tile_12x12_overlap_top2_dedup06.yaml`

The dedup rule drops a feedback ROI when an existing policy ROI already covers at least the configured ratio of the feedback ROI area. `dedup06` uses `duplicate_overlap_ratio: 0.6`.

120-frame comparison:

| Policy | ROI contain | Missed GT | Small contain | Missed small GT | Missed small frames | ROI/frame | Tensor cost/frame | Effective reduction | Fallback frames | Feedback assist/frame | YOLO calls |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| small_object_tile_recall_12x12_overlap | 0.808 | 134 | 0.785 | 115 | 33 | 2.383 | 346343.3 | 0.791 | 4 | 0.000 | 0 |
| oracle feedback top2 | 0.823 | 124 | 0.803 | 105 | 30 | 3.058 | 361242.1 | 0.784 | 4 | 0.692 | 0 |
| oracle feedback top2 dedup06 | 0.815 | 129 | 0.794 | 110 | 32 | 2.650 | 349777.8 | 0.790 | 4 | 0.283 | 0 |
| actual YOLO feedback top2 | 0.823 | 124 | 0.803 | 105 | 31 | 3.042 | 376596.1 | 0.777 | 4 | 0.692 | 5 |
| actual YOLO feedback top2 dedup06 | 0.810 | 133 | 0.787 | 114 | 33 | 2.425 | 348054.9 | 0.790 | 4 | 0.050 | 5 |

Decision:

Aggressive overlap dedup reduces cost, but it also removes most actual YOLO feedback benefit. `dedup06` is not promoted to 600-frame validation.

Keep `duplicate_overlap_ratio` as a tuning knob with default `1.0`, which preserves existing behavior. Do not use aggressive dedup as the Stage C practical candidate.
