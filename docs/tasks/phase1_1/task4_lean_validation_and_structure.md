# Phase 1.1 Task 4: Lean Validation and Folder Structure

## Scope

Task 4 keeps validation useful without making policy iteration expensive.

It also restructures flat `evaluation/` and `tests/` files into clearer folders.

## Implementation

### Lean diagnostics

- Added `--diagnostics-level minimal|full`.
- Minimal mode writes only:
  - `roi_metadata/rule_roi.jsonl`
  - `roi_metadata/gate_decisions.jsonl`
  - reports
- Full mode additionally writes detailed diagnostics:
  - `component_metadata.jsonl`
  - `tile_metadata.jsonl`
  - `policy_traces.jsonl`
- Kept detailed diagnostics opt-in for unusual runs.

### Folder structure

Restructured evaluation modules:

```text
evaluation/
  metrics/
  reports/
  system/
```

Restructured tests:

```text
tests/
  common_tests/
  data_loading_tests/
  evaluation_tests/
  gpu_inference_tests/
  roi_generator_tests/
  visualization_tests/
```

The `_tests` suffix avoids top-level package shadowing during `unittest discover`.

## Decision

Keep the lean validation boundary.

New policies should not need detailed component/tile/policy metadata unless a failure investigation needs it.

## Outputs

Run logs:

```text
docs/runs/phase1_1_a3_lean_validation_boundary_20260825.md
docs/runs/phase1_1_pre_stage_b_structure_cleanup_20260825.md
```

## Verification

```bash
.venv/bin/python -m unittest discover -s tests
.venv/bin/python -m compileall common data_loader evaluation experiments gpu_inference roi_generator tests tools visualization
```
