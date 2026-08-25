# ROI Generator Configs

ROI generator configs are grouped by lifecycle and policy family.

## Layout

```text
configs/roi_generator/
  base/
    default.yaml
    smoke.yaml
  legacy/
    profile_balanced.yaml
    profile_balanced_highres.yaml
    profile_aggressive.yaml
    profile_recall.yaml
  phase1_1/
    component/
    tile/
    hybrid/
    small_object/
    feedback/
```

## Recommended Phase 1.1 Profiles

| Purpose | Config |
|---|---|
| Low-cost baseline | `phase1_1/component` or `legacy/profile_balanced.yaml` |
| Tile baseline | `phase1_1/tile/profile_tile_mask_recall_12x12.yaml` |
| Practical default candidate | `phase1_1/small_object/profile_small_object_tile_recall_12x12_overlap.yaml` |
| Feedback challenger | `phase1_1/feedback/profile_feedback_assisted_tile_12x12_overlap_top2.yaml` |

## Notes

- `base/` is for generic defaults and smoke tests.
- `legacy/` preserves earlier Phase 1 profiles.
- `phase1_1/` contains policy-family comparison profiles from Phase 1.1.
- High-recall and tuning profiles are kept when they are useful references, even if they are not default candidates.
