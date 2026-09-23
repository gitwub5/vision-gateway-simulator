# Agent Project Context

이 파일은 Codex 또는 자동화 agent가 이 프로젝트를 빠르게 파악하기 위한 첫 진입점이다.

## 프로젝트 한 줄 요약

`vision-frontend-simulator`는 카메라와 GPU 사이의 Vision Frontend / ROI Generator 아이디어를 소프트웨어로 검증하는 Python 프로젝트다.

이 파일은 특정 phase의 구현 계획이 아니라, phase가 바뀌어도 유지되어야 하는 공통 컨텍스트를 정리한다. 현재 진행 중인 phase나 세부 작업은 `docs/plan/`, `docs/tasks/`, `docs/runs/`, `docs/idea/`의 해당 문서를 따라간다.

공통 검증 파이프라인의 기본 형태는 다음과 같다.

```text
Dataset stream
  -> ROI / gate policy
  -> ROI metadata
  -> full-frame / ROI YOLO inference
  -> evaluation report
  -> visualization
```

## 먼저 읽을 문서

1. `README.md`
   - 프로젝트 목적, 빠른 실행, 폴더 역할을 확인한다.

2. `docs/README.md`
   - 전체 문서의 역할과 읽는 순서를 확인한다.

3. `docs/current_status.md`
   - 완료된 Phase, 현재 결론, 한계와 다음 작업을 확인한다.

4. `docs/architecture.md`
   - runtime data contract와 모듈 경계를 확인한다.

5. `docs/how-to/quickstart.md`
   - unit test와 synthetic smoke run으로 환경을 확인한다.

6. 필요한 plan/run/task 문서
   - 현재 판단은 최신 run 문서를 우선하고, 과거 plan과 task는 구현 배경을 확인할 때 읽는다.

## 문서 구조

```text
docs/
  README.md
  current_status.md
  architecture.md
  how-to/
    quickstart.md
  plan/
    README.md
    phase1_implementation_plan.md
    phase1_1_implementation_plan.md
    phase1_2_performance_improvement_plan.md
    phase1_3_scene_domain_roi_gate_poc_plan.md
    phase1_validation_plan.md
    vision_frontend_validation_roadmap.md
  tasks/
    README.md
    phase1/
      task2_dataset_stream_loader.md
      task3_rule_based_roi_generator.md
      task4_roi_metadata.md
      task5_full_frame_yolo_baseline.md
      task6_roi_yolo_inference.md
      task7_evaluation.md
      task8_visualization.md
  runs/
    phase1/phase1_validation_runs.md
    phase1_1/
    phase1_2/
    phase1_3/
  idea/       # gitignored, local-only
```

## 중요 문서 경계

- `docs/plan/`에는 공유 가능한 구현 계획, 실행 절차, 산출물 위치만 둔다.
- `docs/tasks/phase*/`에는 실제 구현 과정과 사용법을 둔다.
- `docs/runs/`에는 공유 가능한 검증 실행 기록과 report 위치를 둔다.
- `docs/idea/`에는 검증 가설, 성공 기준 초안, ROI 개선 고민, SNN 전환 판단, DeepStream 포지셔닝 같은 비공개 기술 메모를 둔다.
- `docs/idea/`는 `.gitignore` 대상이다. 사용자가 명시적으로 요청하지 않는 한 이 내용을 공유 문서로 옮기지 않는다.

## 현재 상태

이 섹션은 phase별 세부 구현 상태를 길게 복제하지 않고, 새 agent가 어디를 보면 되는지만 안내한다.

- Phase 1~1.3 탐색은 완료됐다. 현재 상태는 `docs/current_status.md`를 기준으로 판단한다.
- Phase 1.3 최종 결론은 `docs/runs/phase1_3/phase1_3_final_domain_recommendation_matrix_20260917.md`에 있다.
- Phase 2 architecture family는 선정됐지만 production runtime path 구현은 시작하지 않았다.
- 과거 계획은 `docs/plan/`, 실제 실행 기록은 `docs/runs/`, 구현 배경은 `docs/tasks/`에서 확인한다.
- DeepStream, hardware, SNN 전환과 사업성 판단처럼 아직 공유하기 이른 내용은 `docs/idea/`에서 로컬 메모로 관리한다.

## 주요 코드 위치

| 경로 | 역할 |
|---|---|
| `common/` | 공유 schema |
| `data_loader/` | video/image sequence loader |
| `roi_generator/` | rule-based ROI generation, event map, ROI metadata |
| `gpu_inference/` | full-frame YOLO, ROI YOLO, coordinate restore |
| `evaluation/` | recall, containment, workload, latency report |
| `visualization/` | ROI overlay, comparison, failure case render |
| `experiments/` | 대표 validation runner와 Phase별 연구 재현 script. 선택 기준은 `experiments/README.md` 참고 |
| `configs/` | dataset/gate/YOLO config |
| `tools/` | sample data, smoke video, auxiliary scripts |

## 빠른 검증 명령

이 환경에서는 `python` 대신 `python3`를 우선 사용한다.

```bash
python3 -m unittest discover -s tests
```

실험 실행 예시는 `README.md`와 `docs/plan/phase1_validation_plan.md`를 따른다.

## 작업 원칙

- 사용자 변경을 되돌리지 않는다.
- 실험 결과에 영향을 주는 threshold, ROI policy, model config 변경은 config 또는 문서에 이유를 남긴다.
- ROI metadata schema는 inference, evaluation, visualization이 공유하는 계약으로 취급한다.
- 대용량 dataset, model weight, 실험 output은 Git에 포함하지 않는다.
- 전략성 판단은 먼저 `docs/idea/`에 둔다. 공유 가능한 결론으로 정리된 경우에만 `docs/plan/`으로 승격한다.
- DeepStream과 겹치는 단순 ROI crop/inference 재구현보다, dynamic ROI proposal, policy controller, tracking-assisted ROI, batching/fallback decision 같은 차별화 지점을 우선 검토한다.
- phase별 상세 구현 상태를 이 파일에 길게 복사하지 않는다. 이 파일은 공통 맥락과 문서 탐색 경로만 유지한다.
