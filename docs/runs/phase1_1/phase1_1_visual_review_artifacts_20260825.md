# Phase 1.1 Visual Review Artifacts

## Scope

After A1, Stage B/C/D results were mostly report-oriented. This run generates visual artifacts for manual review without changing policy decisions.

Dataset:

- `configs/datasets/physicalai/physicalai_row0709_after3m.yaml`

## Generated Artifacts

| Artifact | Output | Images | Purpose |
|---|---|---:|---|
| Stage D final candidates | `outputs/roi_proposal_validation/stage_d_compare_visual_final_candidates_f5400_80` | 80 | Compare component, tile, small-object, and actual feedback candidates side by side |
| Stage B small-object before/after | `outputs/roi_proposal_validation/stage_b_compare_visual_small_object_before_after_f5400_80` | 80 | Check whether small-object profile improves containment without just expanding arbitrarily |
| Stage C feedback effect | `outputs/roi_proposal_validation/stage_c_compare_visual_feedback_effect_f5400_80` | 80 | Compare small-object default candidate against oracle and actual feedback-assisted candidates |
| Stage D default failure album | `outputs/roi_proposal_validation/stage_d_default_failure_album_small_object_f5400_600/visualizations/failures` | 47 | Inspect remaining miss/failure types for the practical default |
| Stage D default ROI debug album | `outputs/roi_proposal_validation/stage_d_default_failure_album_small_object_f5400_600/visualizations/roi_debug` | 80 | Inspect default candidate ROI generation behavior frame by frame |
| Stage B tile dilation tuning | `outputs/roi_proposal_validation/stage_b_compare_visual_tile_dilation_f5400_80` | 80 | Compare overlap, margin-plus, downward tile dilation, and symmetric vertical tile dilation |
| Stage B true tile trace | `outputs/roi_proposal_validation/stage_b_compare_visual_true_tile_trace_f5400_600` | 80 | Compare Stage B tuning candidates with actual selected tile positions from full diagnostics |
| Phase 1.1 Stage B/C true tile overview | `outputs/roi_proposal_validation/phase1_1_stage_b_c_true_tile_overview_f5400_600` | 100 | Compare A1 tile baseline, Stage B overlap/margin, and Stage C oracle/actual feedback with actual selected tile positions |

## Notes

- The comparison renderer and CLI entry point both live at `visualization/roi_policy_comparison_renderer.py`.
- Comparison frames are selected automatically from frames where candidate containment differs or feedback changes ROI behavior.
- Faint gray lines show the 12x12 grid when a tile policy is active.
- Blue overlays show selected/active tile cells; when minimal diagnostics omit tile trace, active cells are reconstructed from tile ROI geometry for review only.
- Yellow overlays show tile-policy ROI areas that move to downstream inference.
- Green overlays show feedback ROI/reference boxes, so Stage C detector feedback is visually separated from tile-policy ROI.
- Magenta GT boxes are contained and red GT boxes are missed.

## Verification

- `visualization/roi_policy_comparison_renderer.py` compiled successfully.
- Representative Stage B/C/D images were visually checked for readable labels and valid overlays.
