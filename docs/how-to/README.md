# How-To Guides

이 폴더는 실제 실행 방법을 정리한다.

`docs/plan/`은 계획, `docs/runs/`는 실행 결과 로그, `docs/how-to/`는 재현 가능한 명령과 절차를 둔다.

## Guides

| File | Scope |
|---|---|
| `dataset_setup.md` | sample dataset 준비와 config 확인 |
| `roi_proposal_validation.md` | ROI proposal validation 실행 방법 |
| `e2e_inference_validation.md` | ROI gate + YOLO E2E validation 실행 방법 |
| `smoke_test.md` | synthetic smoke test 생성과 빠른 pipeline 확인 |
| `visualization.md` | ROI generation debug, single-run review, multi-run comparison |
| `phase1_2_experiment_automation.md` | profile registry, matrix runner, boundary taxonomy |

## Command Style

- repo root에서 실행하는 명령만 기록한다.
- run 결과 수치와 해석은 `docs/runs/`에 기록한다.
- 계획 변경이나 판단 기준은 `docs/plan/`에 기록한다.
