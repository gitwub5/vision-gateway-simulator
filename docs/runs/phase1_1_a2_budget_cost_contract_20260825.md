# Phase 1.1 A2 Budget / Cost Contract

## Scope

A2의 첫 작업은 A1 policy 후보를 바꾸지 않고, ROI/tile/batch cost contract를 runtime fallback 판단과 report artifact에 연결하는 것이다.

## Implemented

- Added budget config parsing:
  - `budget.enabled`
  - `budget.max_roi_per_frame`
  - `budget.max_total_roi_area_ratio`
  - `budget.max_selected_tile_count`
  - `budget.max_tensor_batch_cost`
- Reinterpreted `max_roi_per_frame` as ROI batch slot budget.
- Added fallback reasons:
  - `batch_slot_overflow`
  - `tensor_budget_overflow`
  - `tile_count_overhead_exceeds_gain`
  - `tile_not_beneficial_dense_scene` reserved for the next dense-scene rule.
- Added common cost estimation through `estimate_budget_cost`.
- Kept the cost contract lean:
  - `estimated_tensor_pixels`
  - `tensor_batch_cost`
  - `effective_input_area`
- Preserved component baseline behavior by applying selected-tile budget only to tile-driven policies:
  - `tile_mask`
  - `hybrid_component_tile`
- Separated `selected_tile_count` from `tile_group_count`:
  - `selected_tile_count`: selected grid tiles.
  - `tile_group_count`: tile-driven output ROI/group count.
- Updated ROI proposal reports and cost summary with average batch/tile/tensor cost fields.
- Moved detailed metadata outputs to optional diagnostics:
  - `component_metadata.jsonl`
  - `tile_metadata.jsonl`
  - `policy_traces.jsonl`

## Verification

Focused A2 tests passed before the additional gate-path assertions:

```bash
/Users/gwshin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest \
  tests.test_roi_budget \
  tests.test_roi_generator \
  tests.test_roi_metadata \
  tests.test_evaluation \
  tests.test_yolo_roi
```

Result:

```text
Ran 47 tests in 0.011s
OK
```

Compile check passed:

```bash
/Users/gwshin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m compileall \
  common roi_generator evaluation gpu_inference experiments tests
```

Full unittest discovery was initially blocked by missing local test dependencies:

- system Python: `numpy` missing
- bundled Python: `cv2` missing

The bundled Python environment was updated with:

```bash
/Users/gwshin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pip install \
  opencv-python \
  PyYAML
```

After installing the missing test dependencies, full unittest discovery passed:

```bash
/Users/gwshin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest discover -s tests
```

Result:

```text
Ran 76 tests in 18.961s
OK
```

After the implementation review, extra tests were added to cover:

- tile budget fallback through `RuleBasedRoiGenerator`, not only direct `budget.py` calls
- component policy tile metadata remaining observability-only for tile budget
- gate metadata reader round-tripping the lean cost fields
- ROI proposal report aggregating metadata cost fields

Full unittest discovery after these extra assertions:

```bash
/Users/gwshin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest discover -s tests
```

Result:

```text
Ran 78 tests in 0.204s
OK
```

Runtime sanity checks confirmed:

- `tile_mask` with `max_selected_tile_count=1` records `tile_count_overhead_exceeds_gain` when tile budget is the active overflow.
- `component_bbox` with the same selected tile metadata still records `roi_selected`, with `tile_group_count=0`, confirming component tile metadata stays observability-only.

After the lean-validation review, duplicated proxy fields were removed:

- `estimated_preprocess_cost`
- `estimated_tensor_cost`
- public `metadata_effective_input_pixel_area`

`gate_decisions.jsonl` remains the minimal contract for policy comparison. Detailed component/tile/policy trace files are now generated only with `--diagnostics-level full`.

## Remaining A2 Work

- Add and validate `tile_not_beneficial_dense_scene` fallback using UA-DETRAC diagnostic runs.
- Run A2 budget profiles on the three A1 candidates:
  - `component_bbox_balanced`
  - `tile_mask_recall_12x12`
  - `hybrid_component_tile_cost`
- Decide whether `max_selected_tile_count` and `max_tensor_batch_cost` should be profile defaults or only diagnostic knobs.
- Keep hybrid tile history/budget candidate scoring deferred until budget report evidence shows it is needed.
