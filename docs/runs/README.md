# Run Logs

이 폴더는 실제 검증/실험 실행 결과를 기록한다.

`docs/plan/`은 앞으로 무엇을 어떻게 검증할지 쓰는 계획 문서이고, `docs/runs/`는 이미 실행한 결과와 해석을 남기는 로그 문서다. 대용량 `outputs/` artifact는 Git에 포함하지 않고, run id와 report 경로만 기록한다.

## Naming

| Pattern | Use |
|---|---|
| `phase<phase>_<stage>_<topic>_<yyyymmdd>.md` | 특정 phase/stage 실험 결과 |
| `phase<phase>_<dataset>_<topic>_<yyyymmdd>.md` | dataset 중심 결과 |
| `legacy_*.md` | 과거 로그를 보존할 때 |

## Current Logs

| File | Scope |
|---|---|
| `phase1_1_a1_roi_policy_baselines_20260819.md` | Phase 1.1 A1 ROI policy matrix, sweep, selected profile 결과 |
| `phase1_validation_runs.md` | Phase 1 초반 validation run index. 새 실험은 가능하면 별도 파일에 기록 |
| `smoke_test_visualization_result.md` | synthetic smoke visualization 실행 결과 |
