# Phase 1 Validation Runs

이 문서는 Phase 1 초반 검증 실행 결과의 legacy index다.

새 실험 결과는 가능하면 `docs/runs/<phase>_<stage>_<topic>_<yyyymmdd>.md` 형식의 별도 파일에 기록한다.

대용량 output은 Git에 포함하지 않는다. 필요한 경우 `outputs/experiments/<run_id>/manifest.json`과 report 경로만 기록한다.

## 기록 형식

| Date | Dataset | Segment | Profile | Run ID | Report | Notes |
|---|---|---|---|---|---|---|
| 2026-07-30 | `opencv-vtest` | f0000-0119 | balanced | `opencv_vtest_f0000_0120_balanced_20260730` | `outputs/experiments/opencv_vtest_f0000_0120_balanced_20260730/reports/comparison_report.md` | Quick run passed end-to-end. Pseudo recall 0.786, ROI containment 0.488, input area reduction 0.563. ROI count benchmark suggests 2-3 ROI bucket is slower than full-frame estimate. |
| 2026-07-30 | `opencv-vtest` | f0000-0119 | profile matrix | `opencv_vtest_f0000_0120_*_20260730` | `outputs/experiments/opencv_vtest_f0000_0120_profile_summary_20260730.md` | Quick matrix passed for aggressive, balanced, recall, and no-refresh. Recall profile had highest pseudo recall at 0.964 but low input area reduction at 0.177. |
| 2026-07-30 | `od-virat-tiny` | test f0000-0119 | profile matrix | `odvirat_test_f0000_0120_*_20260730` | `outputs/experiments/odvirat_test_f0000_0120_profile_summary_20260730.md` | Invalidated. These runs used lexicographic image filename ordering, so `10.jpg`, `100.jpg`, `1000.jpg` appeared before `2.jpg`. Do not use for Phase 1.1 decisions. |
| 2026-07-30 | `od-virat-tiny` | test f0000-0119 | balanced + GT | `odvirat_test_f0000_0120_gt_balanced_20260730` | `outputs/experiments/odvirat_test_f0000_0120_gt_balanced_20260730/reports/gt_report.md` | Invalidated. This run used lexicographic image filename ordering. Replaced by `odvirat_test_f0000_0120_gt_balanced_natural_sort_20260730`. |
| 2026-07-30 | `od-virat-tiny` | test f0000-0119 | balanced + GT | `odvirat_test_f0000_0120_gt_balanced_natural_sort_20260730` | `outputs/experiments/odvirat_test_f0000_0120_gt_balanced_natural_sort_20260730/reports/gt_report.md` | Natural numeric image ordering quick run passed. Full-frame GT recall 0.446, ROI-gated GT recall 0.342, GT ROI containment 0.732. Pseudo recall 0.275 and input area reduction 0.744. |
| 2026-07-30 | `construction-site-static-camera` | `1-250` IMG2-IMG11 | balanced + GT | `construction_static_scene_0002_0011_balanced_20260730` | `outputs/experiments/construction_static_scene_0002_0011_balanced_20260730/reports/gt_report.md` | 10-frame pipeline/GT smoke passed. Dataset labels load from YOLO txt. This run produced 0 ROI records, so it validates integration only and should not be used for ROI policy quality decisions. |
| 2026-08-05 | `construction-site-static-camera` | `251-500` IMG259-IMG457 | balanced + GT | `construction_static_0259_0457_balanced_20260805` | `outputs/experiments/construction_static_0259_0457_balanced_20260805/reports/comparison_report.md` | 199-frame segment run passed. Current balanced gate produced 0 ROI records and relied entirely on full-frame checks, so pseudo recall is 1.000 but workload reduction is 0.000. Annotation report loaded 1,799 objects; full-frame and ROI-gated annotated recall were both 0.046. Use this as a construction dataset integration baseline, not as evidence that current ROI policy works on this segment. |
| 2026-08-07 | `physicalai-smartspaces` | row 709 `Warehouse_000/Camera_0002` f0000-0119 | ROI proposal balanced + person target | `physicalai_row0709_f0000_0120_balanced_20260807` | `outputs/roi_proposal_validation/physicalai_row0709_f0000_0120_balanced_20260807/reports/roi_proposal_report.md` | Target-aware ROI Proposal quick run passed. Target class `person`, 240 GT objects over 120 frames. Current balanced gate has target GT ROI containment 0.042, missed target GT 230, ROI-only input area reduction 0.993, effective input area reduction 0.985, average ROI count 1.033, gate avg latency 0.693 ms. Use as evidence that current motion-only baseline is cheap but misses small/slow/static person targets. |

## Summary Artifacts

Profile summary:

```bash
python3 tools/summarize_phase1_profiles.py \
  outputs/experiments/<run_id_1> \
  outputs/experiments/<run_id_2> \
  --output-json outputs/experiments/phase1_profile_summary.json \
  --output-markdown outputs/experiments/phase1_profile_summary.md
```

ROI count latency benchmark:

```bash
python3 tools/benchmark_roi_count_latency.py \
  outputs/experiments/<run_id> \
  --output-json outputs/experiments/<run_id>/reports/roi_count_latency.json \
  --output-markdown outputs/experiments/<run_id>/reports/roi_count_latency.md
```
