# Phase 1.3-M Final Domain/Scene ROI Gate Recommendation Matrix

Date: 2026-09-17

## Scope

Phase 1.3의 종료 산출물로, 5개 공식 domain axis 전체에 대한 ROI Gate family 권고, traffic 전용 방향 확정, Phase 2로 넘길 architecture family를 정리한다.

이 문서는 새 실험을 추가하지 않고, 아래 선행 run들의 결과를 종합한다.

- `phase1_3_baseline_failure_map_20260916.md`
- `phase1_3_temporal_gate_poc_20260916.md`
- `phase1_3_static_zone_prior_poc_20260916.md`
- `phase1_3_tracker_memory_poc_20260917.md`
- `phase1_3_lightweight_visual_signal_poc_20260917.md`
- `phase1_3_compression_signal_poc_20260917.md`
- `phase1_3_hybrid_gate_candidate_selection_20260917.md`
- `phase1_3_traffic_velocity_prior_probe_20260917.md`
- `phase1_3_traffic_road_region_prior_probe_20260917.md`
- `phase1_3_hybrid_family_600frame_validation_20260917.md`

## 1. Traffic Direction Finalization

Phase 1.3-H(velocity prior)와 1.3-I(road/lane region prior)에서 확인한 결과를 기반으로 traffic/parking 방향을 확정한다.

확정 이유:

- 120-frame과 600-frame 모두에서 단순 velocity prediction은 hold-memory 대비 recall을 개선하지 못했다(`velocity_refresh_5_margin_30` recall 0.622 vs `hold_refresh_5_margin_30` 0.624, 600-frame 기준).
- Road/lane bbox envelope(oracle)는 bbox recall 1.000을 달성하지만, 관찰 window가 길어질수록 selected area가 급격히 커진다(120-frame 31.6% -> 600-frame 64.6%, `bbox_envelope_margin_0` 기준).
- 즉 traffic 문제는 "어디를 봐야 하는가(공간)"가 "본 차량이 어디로 움직이는가(속도)"보다 우선이며, 공간 prior도 segment로 나누지 않으면 결국 거의 full-frame이 된다.

확정 방향:

```text
road/lane segmented prior + entry-zone guard
  + tracker/refresh inside active lane segments
  + packing/budget across active segments
```

역할 분담:

| 구성 요소 | 역할 | 근거 |
|---|---|---|
| road/lane segmented prior | 차량이 나타날 수 있는 공간을 lane/segment 단위로 제한 | 1.3-I: 전체 road envelope는 시간이 지날수록 과도하게 커짐 |
| entry-zone guard | 새로 진입하는 차량을 놓치지 않도록 진입 구간을 항상 감시 | 1.3-I: 새 차량 진입이 velocity/hold-memory 실패의 핵심 원인 |
| segment 내부 tracker/refresh | active segment 안에서만 짧은 refresh/hold 유지 | 1.3-D, 1.3-H: 단순 hold-memory는 segment 밖 전체 적용 시 약하지만, 좁은 영역 안에서는 여전히 유효할 가능성이 높음 |
| packing/budget | 여러 active segment를 동시에 처리할 때 ROI 수/면적 제한 | 1.3-I: segment 수가 늘어나면 면적 절감 효과가 약해질 위험 |

Velocity-only tracker는 확정 후보에서 제외한다(1.3-H 결론 유지). Kalman filter는 필요 시 lane prior 위의 보조 tracker로만 재검토한다.

이 방향은 production 수준 lane segmentation 구현을 포함하지 않는다. Phase 1.3 시점에서는 recommendation-level 확정으로 충분하며, 실제 segment 분할/entry-zone 정의/packing 구현은 Phase 2 범위다.

## 2. Domain / Scene Recommendation Matrix

| Domain | 추천 ROI Gate family | Confidence | 근거 run | 실패 위험 | Phase 2로 이동 | Deferred/Dropped |
|---|---|---|---|---|---|---|
| Traffic / parking | `road/lane segmented prior + entry-zone guard + tracker/refresh in active segments + packing` | medium | 1.3-H, 1.3-I | segment 미분할 시 전체 envelope가 full-frame에 근접; entry-zone 정의가 부정확하면 신규 차량 recall 손실 | lane/segment 정의, entry-zone guard, segment 내부 tracker, packing 구현 및 600-frame 재검증 | velocity-only tracker(제외), 비분할 whole-road envelope(제외) |
| Logistics / smart factory | `static_zone_prior + tracker_memory + temporal_refresh_guard` | high | 1.3-D(120f), 1.3-J(600f) | guard가 refresh interval보다 짧으면 recall 0.60까지 붕괴(static 단독 recall 1.5%에 불과); ROI/memory frame ~130개로 packing 필요 | non-oracle detector refresh, ROI merge/packing, stale-track handling, production static profile 확정 | 짧은 guard(guard < refresh interval) 조합 |
| Surveillance / security | `static_zone_prior + lightweight_visual_priority` (dilation 필수) | medium | 1.3-E(120f), 1.3-K(600f) | static 단독 recall 8% 수준; dilation 없이는 recall 14% 수준으로 무의미; dilation 적용 시 area 26-56%까지 증가 | raw edge/texture dilation을 ROI/tile merge 또는 objectness 후속 신호로 대체, ROI budget/packing layer | dilation 없는 조합(recall 부족) |
| Retail / space analytics | `static_zone_prior + lightweight_visual_priority` (dilation 필수) | medium | 1.3-E(120f), 1.3-K(600f) | static 단독 recall 18% 수준; head-point proxy-box GT라 실제 bbox 기준 recall은 별도 검증 필요; dilation 시 area 37-53% | proxy-box 대신 실제 bbox annotation으로 재검증, ROI budget/packing layer, objectness 후속 신호 검토 | dilation 없는 조합(recall 부족), static-only(recall 부족) |
| General multi-class stress | `static_zone_prior + tracker_memory + temporal_refresh_guard` | high (generalization stress로 해석) | 1.3-D(120f), 1.3-J(464f, 요청 600f 중 가용 최대) | camera가 고정 CCTV가 아닌 drone 이동 카메라; ROI/memory frame ~225개로 packing 필수; oracle refresh 기반이라 non-oracle 성능 미검증 | ROI packing, camera-motion 보정 여부 판단, non-oracle detector refresh 검증 | 없음(compression signal은 전체 domain 공통으로 deferred) |

## 3. Common Cross-Domain Findings

- Motion/tile primary gate는 PhysicalAI 외 모든 domain에서 baseline failure다(1.3-A). 이 결론은 변하지 않았고, Phase 2부터는 motion/tile을 primary gate로 취급하지 않는다.
- Temporal gate 단독 skip은 어떤 domain에서도 안전한 primary가 아니다(1.3-B). Refresh cadence guard로만 사용한다.
- Static zone prior는 모든 domain에서 강한 spatial anchor이지만, bbox containment 관점에서는 어떤 domain에서도 단독으로 충분하지 않다(1.3-C, 1.3-J, 1.3-K에서 static-only recall이 1.5~18% 수준). 항상 다른 signal과 결합해야 한다.
- Lightweight visual signal(edge/texture)은 dilation 없이는 어떤 domain에서도 실질적 ROI 생성기로 쓸 수 없다(1.3-E, 1.3-K).
- Compression signal은 여전히 deferred다(1.3-F). 현재 dataset이 encoded stream metadata를 제공하지 않는다.

## 4. Phase 2로 이동할 Architecture Family (2-3개로 압축)

Phase 1.3 종료 기준에 따라 아래 2개 family만 Phase 2 구현 대상으로 압축한다. Traffic은 별도 family로 유지한다.

1. **`static_zone_prior + tracker_memory + temporal_refresh_guard`**
   - 대상: Logistics/smart-factory, General multi-class stress
   - Phase 2 구현 우선순위: non-oracle detector refresh, guard >= refresh interval 제약을 profile validation에 반영, ROI merge/packing

2. **`static_zone_prior + lightweight_visual_priority`**
   - 대상: Surveillance/security, Retail/space analytics
   - Phase 2 구현 우선순위: raw edge/texture dilation을 ROI/tile merge 기반 packing으로 대체, objectness 후속 신호 검토, retail은 proxy-box가 아닌 실제 bbox로 재검증

3. **`road/lane segmented prior + entry-zone guard + tracker/refresh in active segments + packing`** (Traffic 전용)
   - 대상: Traffic/parking
   - Phase 2 구현 우선순위: segment 정의, entry-zone guard, segment 내부 tracker, packing, 600-frame 재검증

이 세 family로 압축됨에 따라, 아래는 명시적으로 제외/보류한다.

- Motion-primary gate: Phase 2 primary 후보에서 제외(baseline failure)
- Temporal gate 단독 primary: 제외, guard 역할로만 유지
- Velocity-only tracker(traffic): 제외
- Raw edge/texture without dilation: 단독 ROI 생성기로는 제외
- Compression-domain pre-gate: deferred, encoded stream 접근 가능 시점에 재검토
- Heatmap/contour ROI, detector-assisted gate(별도 objectness 모델): 현재 명시적 실험이 없으므로 Phase 2 초반 objectness 후속 검토 항목으로만 남김

## 5. Phase 1.3 Finish Criteria Check

| 기준 | 상태 |
|---|---|
| 모든 공식 domain axis에 recommendation이 있는가 | 충족. 5개 domain 모두 위 표에 recommendation 존재 |
| 2개 shortlisted hybrid family에 대해 600-frame validation을 시도했는가 | 충족. `static_zone_prior + tracker_memory + temporal_refresh_guard`(PhysicalAI 600f, VisDrone 464f/가용 최대), `static_zone_prior + lightweight_visual_priority`(Mall 600f, MOT17 600f) |
| Traffic이 명확한 전용 방향을 가지는가 | 충족. `road/lane segmented prior + entry-zone guard + tracker/refresh in active segments + packing`으로 확정, recommendation-level(구현은 Phase 2) |
| 2-3개 architecture family만 Phase 2로 이동하는가 | 충족. 3개 family로 압축(logistics/general 공용 1개, surveillance/retail 공용 1개, traffic 전용 1개) |
| 남은 작업이 폭넓은 탐색이 아니라 구현/runtime 검증 중심인가 | 충족. 남은 작업은 non-oracle detector refresh, ROI packing/merge, segment 정의, proxy-box 재검증 등 구현/검증 항목으로 정의됨 |

Phase 1.3은 위 기준을 모두 충족하여 종료 가능한 상태로 판단한다.

## 6. Next Phase Implication

`docs/plan/vision_frontend_validation_roadmap.md`의 Phase 2(ROI Gate Architecture Implementation)는 아래 순서로 시작하는 것을 권고한다.

1. `static_zone_prior + tracker_memory + temporal_refresh_guard`를 logistics 대상으로 non-oracle 버전으로 먼저 구현한다(가장 confidence가 높고 domain이 단순).
2. 같은 family를 general multi-class(VisDrone류) 대상으로 확장하되 camera-motion 보정 여부를 별도 판단한다.
3. `static_zone_prior + lightweight_visual_priority`를 surveillance/retail 대상으로 구현하면서 dilation을 ROI/tile merge로 대체한다.
4. Traffic lane/segment prior는 별도 workstream으로 진행하며, segment 정의와 entry-zone guard부터 구현한다.
5. 세 family 모두 ROI/tile packing과 budget controller를 공통 구성요소로 설계한다(1.3-D, 1.3-J, 1.3-K 전부 ROI count가 packing 없이는 과도함을 보여줌).

## Verification

- `.venv/bin/python -m unittest tests.evaluation_tests.test_temporal_gate_report tests.evaluation_tests.test_static_zone_prior_report tests.evaluation_tests.test_tracker_memory_report tests.evaluation_tests.test_lightweight_visual_signal_report tests.evaluation_tests.test_compression_signal_report tests.evaluation_tests.test_hybrid_gate_selection_report tests.evaluation_tests.test_velocity_prior_tracker_report tests.evaluation_tests.test_road_region_prior_report tests.evaluation_tests.test_static_tracker_temporal_hybrid_report tests.evaluation_tests.test_static_lightweight_hybrid_report`
