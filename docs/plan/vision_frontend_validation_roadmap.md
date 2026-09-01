# Vision Frontend Simulator Roadmap

이 문서는 공유 가능한 수준의 Phase 목록과 문서 위치만 관리한다.

기술 가설, 성공 기준, 시장성, DeepStream 대비 포지셔닝, ROI 개선과 SNN 전환 판단은 Git에 올리지 않는 `docs/idea/`에서 먼저 정리한다. 공유 가능한 결론만 이 문서로 옮긴다.

## Phase 목록

| Phase | 공유 범위 |
|---|---|
| Phase 1. Rule-based ROI generator | 구현 완료 상태, 실행 절차, 산출물 위치 |
| Phase 1.1. ROI Gate Policy Validation | component/tile/hybrid 비교로 tile 기반 방향성과 ROI/tile/cost contract 확정 |
| Phase 1.2. Tile-based ROI Gate Improvement | Phase 1.1에서 남긴 tile baseline을 강화해 boundary miss, false ROI, feedback/fallback 문제 개선 |
| Phase 1.3. Alternative ROI Exploration | heatmap/contour, event-like signal, non-uniform tile, compressed-domain 등 tile 기반 외 대안 검증 |
| Phase 2. SNN Tile Eventness Model | 공유 가능한 구현 계획이 확정되면 추가 |
| Phase 3. Multi-camera Simulation | 공유 가능한 구현 계획이 확정되면 추가 |
| Phase 4. GPU Pipeline Optimization | 공유 가능한 구현 계획이 확정되면 추가 |
| Phase 5. Hardware-oriented Spec | 공유 가능한 요구사항 문서가 확정되면 추가 |
| Phase 6. Edge Pipeline PoC | 공유 가능한 PoC 범위가 확정되면 추가 |
| Phase 7. Business Validation | 공유 가능한 판단 기준이 확정되면 추가 |

## 현재 공유 문서

- `docs/plan/phase1_implementation_plan.md`
- `docs/plan/phase1_validation_plan.md`
- `docs/plan/phase1_1_implementation_plan.md`
- `docs/plan/phase1_2_performance_improvement_plan.md`
- `docs/plan/phase1_3_alternative_roi_exploration_plan.md`
- `docs/tasks/phase1/`

## 로컬 메모

아래 항목은 `docs/idea/`에서 관리한다.

- Phase 1 상세 검증 컨셉
- ROI crop 개선 여부
- SNN/event 기반 전환 판단
- DeepStream과의 경계 및 보완 전략
- Phase 2 이후의 상세 기술 로드맵
