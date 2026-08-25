# Phase 1.1 Task 2: ROI Policy Baselines

## Scope

Task 2 compares multiple ROI policy families under one proposal-validation contract.

Compared policies:

- `component_bbox_balanced`
- `tile_mask_recall_12x12`
- `hybrid_component_tile_cost`

## Implementation

- Reorganized `roi_generator/` into:
  - `core/`
  - `signals/`
  - `candidates/`
  - `policies/`
  - `observability/`
- Added tile candidate helpers and tile trace metadata.
- Added policy selection through `roi_policy`.
- Added or stabilized policy profiles:
  - `configs/roi_generator/profile_tile_mask_recall_12x12.yaml`
  - `configs/roi_generator/profile_hybrid_component_tile_cost.yaml`
- Kept component-bbox tile metadata as observability only, not as decision input.
- Updated visual comparison so policy differences are visible:
  - component bbox: final ROI only
  - tile/hybrid: selected tile and final ROI

## Decision

600-frame PhysicalAI after3m baseline comparison showed:

- `component_bbox_balanced`: lowest cost, weak target containment
- `tile_mask_recall_12x12`: better containment, higher cost
- `hybrid_component_tile_cost`: low cost, no recall improvement over component baseline

`tile_mask_recall_12x12` became the practical tile baseline.

## Outputs

Representative visualization:

```text
outputs/roi_proposal_validation/a1_compare_visual_policy_methods_f5401_100/
```

Primary run log:

```text
docs/runs/phase1_1_a1_roi_policy_baselines_20260819.md
```

## Verification

Use the common test command:

```bash
.venv/bin/python -m unittest discover -s tests
```
