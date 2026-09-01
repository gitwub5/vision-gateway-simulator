# Phase 1.2 Workstream D: Feedback And Fallback Retuning

Date: 2026-09-01

## Scope

- Main dataset: `configs/datasets/physicalai/physicalai_row0709_after3m.yaml`
- Experiment: `configs/experiments/phase1_2_feedback_retuning.yaml`
- Matrix root: `outputs/validation_matrices/phase1_2_feedback_retuning_20260901_160637`
- Feedback source: actual `full_frame_yolo`

## Implementation

- Added reference feedback confidence decay.
- Added `empty_policy_only` assist mode for low-frequency feedback assist.
- Added feedback assisted ROI cap.
- Added fallback retune profile based on C candidate budget limits.

## Main 600-Frame Result

| Profile | Feedback | Contain | Missed GT | Small contain | Missed small | ROI/frame | Tile/frame | Tensor/frame | Fallback | False ROI |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `practical_default` | none | 0.641 | 1035 | 0.602 | 816 | 2.638 | 12.752 | 263441.0 | 20 | 0.523 |
| `margin_plus` | none | 0.655 | 993 | 0.620 | 779 | 2.638 | 12.752 | 282164.2 | 20 | 0.514 |
| `rescue_with_budget_cap` | none | 0.699 | 867 | 0.685 | 647 | 2.293 | 12.840 | 299538.0 | 20 | 0.447 |
| `feedback_actual_yolo` | actual_yolo | 0.704 | 852 | 0.691 | 634 | 3.522 | 12.752 | 292541.5 | 23 | 0.498 |
| `feedback_confidence_decay` | actual_yolo | 0.753 | 710 | 0.759 | 494 | 2.953 | 12.840 | 321146.5 | 21 | 0.433 |
| `low_frequency_feedback_assist` | actual_yolo | 0.699 | 867 | 0.685 | 647 | 2.293 | 12.840 | 299538.0 | 20 | 0.447 |
| `fallback_reason_retune` | none | 0.701 | 861 | 0.687 | 642 | 2.297 | 12.840 | 301579.0 | 19 | 0.447 |
| `feedback_roi_budget_cap` | actual_yolo | 0.733 | 768 | 0.730 | 553 | 2.832 | 12.840 | 319375.3 | 20 | 0.454 |

## Feedback Summary

| Profile | Candidate/frame | Assisted ROI/frame | Active track/frame | Stale track/frame |
|---|---:|---:|---:|---:|
| `feedback_actual_yolo` | 1.997 | 0.940 | 1.997 | 0.148 |
| `feedback_confidence_decay` | 1.860 | 0.682 | 1.860 | 0.138 |
| `low_frequency_feedback_assist` | 0.000 | 0.000 | 1.853 | 0.133 |
| `feedback_roi_budget_cap` | 1.853 | 0.542 | 1.853 | 0.133 |

## Taxonomy

| Profile | Margin insufficient | Adjacent tile not selected | Signal missing | Low density false ROI | Partial target boundary | Off target motion |
|---|---:|---:|---:|---:|---:|---:|
| `feedback_actual_yolo` | 210 | 274 | 249 | 658 | 375 | 19 |
| `feedback_confidence_decay` | 135 | 219 | 246 | 494 | 257 | 16 |
| `feedback_roi_budget_cap` | 167 | 235 | 261 | 497 | 258 | 17 |
| `fallback_reason_retune` | 215 | 262 | 285 | 493 | 114 | 9 |

## Decision

- Keep `feedback_confidence_decay` as the Workstream D high-recall candidate.
- Keep `feedback_roi_budget_cap` as a conservative fallback candidate only if tensor cost must be capped further.
- Disable `low_frequency_feedback_assist`; it is equivalent to `rescue_with_budget_cap` on this main dataset.
- Do not promote `fallback_reason_retune` as default. It reduces fallback by one frame but has minor recall impact.
- Phase 1.2 default candidate should remain `rescue_with_budget_cap`; `feedback_confidence_decay` is optional high-recall mode.
