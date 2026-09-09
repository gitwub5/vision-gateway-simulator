# Vision Frontend Simulator Roadmap

이 문서는 공유 가능한 수준의 Phase 목록, 현재 우선순위, 문서 위치를 관리한다.

기술 가설, 성공 기준, 시장성, DeepStream 대비 포지셔닝, 장기 아이디어는 Git에 올리지 않는 `docs/idea/`에서 먼저 정리한다. 공유 가능한 결론만 이 문서로 옮긴다.

## 현재 우선순위

현재 검증의 1순위는 SNN 모델 자체가 아니라 **ROI를 얼마나 잘 생성해서 GPU detector/model에 넘길 수 있는지**다.

따라서 이후 roadmap은 특정 구현 방식 하나를 먼저 고정하지 않는다. Motion map, tile, background model, detector feedback, tracker, compressed-domain cue, lightweight objectness model, SNN/eventness model은 모두 ROI Gate 후보 기술로 취급한다.

핵심 판단 기준:

- target을 놓치지 않는 ROI proposal 품질
- full-frame 대비 충분히 작은 inference region
- ROI count, tensor cost, fallback을 포함한 GPU handoff 효율
- 기존 CCTV/camera와 GPU 서버 환경에서의 적용 가능성
- scene/domain별 재현성

## Phase Track 구분

Phase 1.x는 ROI Gate 적용 가능성과 기술 방향을 찾는 exploration track이다. 이 구간에서는 motion/tile 기반을 유지할지, scene별로 다른 gate family가 필요한지, 공통 적용 가능한 signal/architecture가 있는지를 검증한다.

Phase 2부터는 implementation track으로 전환한다. Phase 1.x에서 선택한 ROI Gate architecture를 실제 CCTV/GPU pipeline에 적용하고, runtime handoff, throughput, multi-camera, integration 가능성을 검증한다.

## Phase 목록

| Phase | 공유 범위 |
|---|---|
| Phase 1. Rule-based ROI generator | 구현 완료 상태, 실행 절차, 산출물 위치 |
| Phase 1.1. ROI Gate Policy Validation | component/tile/hybrid 비교로 tile 기반 방향성과 ROI/tile/cost contract 확정 |
| Phase 1.2. Tile-based ROI Gate Improvement | Phase 1.1에서 남긴 tile baseline을 강화해 boundary miss, false ROI, feedback/fallback 문제 개선 |
| Phase 1.3. Scene/Domain ROI Gate PoC | motion 기반 신호의 유효성을 재검증하고, scene/domain별 적합한 ROI Gate architecture 후보를 찾음 |
| Phase 2. ROI Gate Architecture Implementation | Phase 1.3에서 선택된 ROI Gate family를 구현하고 GPU handoff 기준으로 고도화 |
| Phase 3. ROI-to-GPU Pipeline Optimization | ROI batching, packing, full-frame switch, detector refresh 등 실제 GPU 전달 경로 최적화 |
| Phase 4. Multi-camera / Multi-domain Validation | 여러 camera stream과 scene/domain 조합에서 throughput, recall, cost를 검증 |
| Phase 5. Edge / DeepStream Integration PoC | 기존 CCTV/RTSP/GPU 서버 환경에서 연동 가능한 runtime 구조 검증 |
| Phase 6. Hardware-oriented Spec | software PoC 결과를 바탕으로 frontend hardware 또는 accelerator 요구사항 도출 |
| Phase 7. Business Validation | 도메인별 PoC 기준, 적용 조건, ROI Gate value proposition 정리 |

## Phase 1.3 방향

Phase 1.3은 기존의 "tile 기반 외 대안 탐색"보다 넓은 PoC 단계로 재정의한다.

목표:

```text
기존 CCTV/RGB 영상 환경에서 ROI를 충분히 정확하고 작게 생성해
GPU detector에 넘길 수 있는 scene/domain 조건과 기술 조합을 찾는다.
```

검증할 architecture family:

- motion-primary gate
- motion + scene guard gate
- background-model gate
- detector-assisted gate
- tracker-assisted gate
- heatmap/contour ROI gate
- compressed-domain pre-gate
- lightweight objectness gate

도메인은 GPU/DeepStream 기반 video analytics 수요가 큰 vertical을 우선한다.

1차 vertical:

- traffic / parking
- surveillance / security
- logistics / smart factory
- retail / space analytics

`general multi-class object detection`은 business vertical이 아니라 공통 평가축으로 둔다. 기술 판단은 각 vertical 안의 scene condition 중심으로 한다.

초기 scene coverage:

- stable indoor fixed camera
- outdoor illumination variation
- global camera shake / unstable feed
- slow or stationary target
- small far-field target
- dense multi-object scene
- periodic machine/background motion
- low-light / compressed feed

Phase 1.3의 종료 산출물은 단일 default profile이 아니라 scene/domain별 ROI Gate recommendation matrix와 다음 phase implementation target이다.

현재 Phase 1.3 준비 상태:

- 5개 1차 dataset axis 준비 완료: traffic/parking, logistics/smart factory, surveillance/security, retail/space analytics, general multi-class stress.
- `outputs/roi_proposal_validation/phase1_3_smoke_*` smoke run으로 stream, annotation, report generation 확인 완료.
- 기존 motion-primary gate는 PhysicalAI indoor warehouse 외 domain에서 대부분 fallback/no-ROI로 붕괴하므로, Phase 1.3 본 실험은 이 결과를 baseline failure로 두고 후보 gate family를 비교한다.
- 다음 작업은 scene/domain별 candidate matrix 실행과 recommendation 기준 확정이다.

## 현재 공유 문서

- `docs/plan/phase1_implementation_plan.md`
- `docs/plan/phase1_validation_plan.md`
- `docs/plan/phase1_1_implementation_plan.md`
- `docs/plan/phase1_2_performance_improvement_plan.md`
- `docs/plan/phase1_3_scene_domain_roi_gate_poc_plan.md`
- `docs/tasks/phase1/`

## 로컬 메모

아래 항목은 `docs/idea/`에서 관리한다.

- ROI Gate current findings
- Scene condition taxonomy
- ROI Gate idea backlog
- 다음 probe 후보
- DeepStream과의 경계 및 보완 전략
- SNN/eventness, compressed-domain, lightweight model 등 후보 기술 메모
