# Documentation Guide

이 디렉터리는 현재 상태, 실행 방법, 과거 계획, 실험 결과를 구분해서 관리합니다.

## 처음 읽을 문서

| 순서 | 문서 | 용도 |
|---:|---|---|
| 1 | [`current_status.md`](current_status.md) | 현재 완료 범위, 핵심 결론, 다음 작업 |
| 2 | [`architecture.md`](architecture.md) | 코드 모듈과 데이터 흐름 |
| 3 | [`how-to/quickstart.md`](how-to/quickstart.md) | 새 환경에서 테스트와 smoke run 실행 |
| 4 | [`runs/phase1_3/phase1_3_final_domain_recommendation_matrix_20260917.md`](runs/phase1_3/phase1_3_final_domain_recommendation_matrix_20260917.md) | Phase 1.3 최종 실험 판단 |

## 문서 구분

| 경로 | 성격 | 읽는 시점 |
|---|---|---|
| `current_status.md` | 현재 기준 문서 | 저장소를 처음 확인할 때 |
| `architecture.md` | 현재 코드 구조 | 코드를 수정하거나 확장하기 전 |
| `how-to/` | 재현 가능한 실행 절차 | 환경 설정과 실험 실행 시 |
| `runs/` | 완료된 실험의 결과와 해석 | 수치와 판단 근거를 확인할 때 |
| `plan/` | 각 Phase를 시작할 때 작성한 계획과 roadmap | 의사결정 배경을 확인할 때 |
| `tasks/` | Phase 1/1.1 구현 단위 기록 | 세부 구현 배경을 추적할 때 |

`plan/`과 `tasks/`에는 작성 당시의 예정 사항이 남아 있을 수 있습니다. 현재 구현 여부와 다음 작업은 `current_status.md`와 최신 `runs/phase1_3/` 문서를 우선해서 판단합니다.

## 로컬 문서

`docs/idea/`는 개인 기술 메모와 공유 전 의사결정 초안을 두는 로컬 작업 공간입니다. `.gitignore` 대상이므로 다른 연구자에게 전달해야 하는 내용은 `current_status.md`, `plan/`, 또는 `runs/`의 적절한 문서로 옮깁니다.

## 문서 갱신 원칙

- 현재 상태가 바뀌면 `current_status.md`를 먼저 갱신합니다.
- 재현 가능한 명령은 `how-to/`에 기록합니다.
- 실행 결과와 해석은 `runs/`에 기록합니다.
- 아직 실행하지 않은 계획은 `plan/`에 기록합니다.
- 같은 내용을 여러 문서에 복사하지 않고 기준 문서에 링크합니다.
