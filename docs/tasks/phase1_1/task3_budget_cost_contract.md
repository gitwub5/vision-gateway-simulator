# Phase 1.1 Task 3: Budget and Cost Contract

## Scope

Task 3 defines a shared downstream cost contract for ROI policy comparison.

The goal is to compare policies by target containment and actual gate cost, not only by ROI area.

## Implementation

- Added `roi_generator/core/budget.py` cost evaluation:
  - ROI batch slots
  - selected tile count
  - tile group count
  - tensor batch cost
  - effective input area
- Added budget config fields:
  - `budget.enabled`
  - `max_roi_per_frame`
  - `max_total_roi_area_ratio`
  - `max_selected_tile_count`
  - `max_tensor_batch_cost`
- Added fallback reasons:
  - `batch_slot_overflow`
  - `tensor_budget_overflow`
  - `tile_count_overhead_exceeds_gain`
- Extended `GateDecision`, frame metadata, policy trace, report JSON, and cost summary with the new fields.

## Decision

The cost contract is kept as Phase 1.1 core infrastructure.

It made later Stage B/C comparisons possible by exposing:

- ROI/frame
- tile/frame
- tensor cost/frame
- effective input area reduction
- fallback reason distribution

## Outputs

Primary run log:

```text
docs/runs/phase1_1/phase1_1_a2_budget_cost_contract_20260825.md
```

## Verification

```bash
.venv/bin/python -m unittest discover -s tests
.venv/bin/python -m compileall common data_loader evaluation experiments gpu_inference roi_generator tests tools visualization
```
