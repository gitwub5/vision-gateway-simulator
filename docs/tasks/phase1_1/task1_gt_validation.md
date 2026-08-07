# Phase 1.1 Task 1: Annotation-aware Validation

## Scope

Phase 1.1 policy work needs annotation-aware validation before changing ROI behavior. This task adds OD-VIRAT Tiny annotation loading, report generation, and annotation bbox overlays in failure visualization.

OD-VIRAT Tiny annotations are partial and are not treated as exhaustive ground truth. The report file names still use `gt_*` for implementation continuity, but metric interpretation must use annotated-object lower-bound semantics.

## Implementation

- Added `GroundTruthAnnotation` as the shared GT schema.
- Added OD-VIRAT Tiny COCO-style annotation loading in `data_loader/annotation_loader.py`.
- Mapped annotation `file_name` to dataset `frame_id` using the same natural numeric image sequence ordering as `ImageSequenceStream`.
- Added optional annotation validation to `experiments/run_e2e_inference_validation.py`.
- Added annotation report outputs:
  - `annotations/ground_truth.jsonl`
  - `reports/gt_report.json`
  - `reports/gt_report.md`
- Added annotation bbox overlays to ROI overlay, comparison, and failure visualization.
- Added annotated-object miss failure rendering so annotation misses are visible even when pseudo-reference miss detection does not trigger.

## Feature Flag / Config

Annotation validation is enabled when the dataset config has an `annotations` section with `enabled` omitted or set to `true`.

Disable options:

```bash
python3 experiments/run_e2e_inference_validation.py \
  --dataset-config configs/datasets/od_virat_tiny.yaml \
  --gate-config configs/npx_gate/profile_balanced.yaml \
  --model-config configs/models/yolo_default.yaml \
  --disable-gt-validation
```

Dataset config example:

```yaml
annotations:
  enabled: false
  type: od_virat_tiny
  input_path: data/od_virat_tiny/json_anntations/test_annotations.json
  quality:
    completeness: partial
    expected_exhaustive: false
    unreliable_metrics:
      - false_roi_rate
      - precision
      - false_positive_count
    notes:
      - Visible target objects may be missing from GT annotations.
```

## Verification

Unit tests:

```bash
.venv/bin/python -m unittest discover -s tests
```

OD-VIRAT Tiny quick run:

```bash
.venv/bin/python experiments/run_e2e_inference_validation.py \
  --dataset-config configs/datasets/od_virat_tiny.yaml \
  --gate-config configs/npx_gate/profile_balanced.yaml \
  --model-config configs/models/yolo_default.yaml \
  --experiment-name odvirat_test_gt_balanced_natural_sort \
  --run-id odvirat_test_f0000_0120_gt_balanced_natural_sort_20260730 \
  --limit 120 \
  --render-limit 30
```

Generated run:

```text
outputs/experiments/odvirat_test_f0000_0120_gt_balanced_natural_sort_20260730/
```

This historical run was created before the E2E output root split. New E2E runs default to `outputs/e2e_inference_validation/<run_id>/`.

Key quick-run metrics:

| Metric | Value |
|---|---:|
| Annotated objects | 590 |
| Full-frame annotated-object recall | 0.446 |
| ROI-gated annotated-object recall | 0.342 |
| Annotated ROI containment | 0.732 |
| ROI-gated missed annotated objects | 388 |
| False ROI rate | 0.254 |
| ROI-gated duplicate detection rate | 0.003 |
| Pseudo recall retention | 0.275 |
| Input pixel area reduction | 0.744 |
| Average ROI count | 3.250 |

## Notes

OD-VIRAT Tiny annotation classes are not identical to COCO/YOLO classes. Matching normalizes obvious aliases such as `Person/person`, `Car/car`, and `truck` or `bus` to `Vehicle`. The report preserves original annotation class names for class recall output.

Annotations are not assumed to be exhaustive. Every annotated dataset config should declare `annotations.quality.completeness`, `expected_exhaustive`, and any metrics that require caution. If a dataset can have visible but unlabeled target objects, use recall and ROI containment as annotated-object lower-bound checks. Do not use false ROI rate, precision, or false positive count as hard criteria unless the dataset has been visually checked as exhaustive for the target classes.

Earlier OD-VIRAT quick runs without natural numeric sorting are invalid. Lexicographic filename ordering placed files such as `10.jpg`, `100.jpg`, and `1000.jpg` before `2.jpg`, which broke temporal continuity and distorted ROI gate metrics.
