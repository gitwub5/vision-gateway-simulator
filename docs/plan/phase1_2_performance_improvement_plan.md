# Phase 1.2 ROI Gate Performance Improvement Plan

이 문서는 Phase 1.2에서 실제로 진행할 ROI Gate 성능 개선 계획만 남긴다.

Phase 1.1은 ROI policy 방향을 굳히고 비교/검증 기반을 만든 단계였다. Phase 1.2는 같은 기반 위에서 실제 성능을 개선하는 단계다.

우선 해결할 문제는 두 가지다.

1. GT bbox가 ROI 경계에 조금 걸려 완전히 포함되지 않는 boundary miss
2. motion noise나 일시적 변화가 ROI로 승격되는 false ROI

## 0. Validation Datasets

Phase 1.2는 main dataset과 secondary cross-check dataset을 고정한다.

Main dataset은 정책 튜닝과 default 후보 판정에 사용한다.

| 항목 | 값 |
|---|---|
| dataset config | `configs/datasets/physicalai/physicalai_row0709_after3m.yaml` |
| camera | `Camera_0002` |
| source | PhysicalAI Smart Spaces video + JSON annotation |
| target classes | `person` |
| frame range | `start_frame=5400`, `limit=600` |
| diagnostics | `tile_trace` |

Secondary dataset은 main dataset에서 선택된 후보가 vehicle/traffic scene에서도 유지되는지 확인하는 cross-check로만 사용한다.

| 항목 | 값 |
|---|---|
| dataset config | `configs/datasets/ua_detrac/ua_detrac_mvi_39361.yaml` |
| camera | `MVI_39361` |
| source | UA-DETRAC image sequence + XML annotation |
| target classes | `car`, `bus`, `truck` |
| frame range | `start_frame=0`, `limit=600` |
| diagnostics | `tile_trace` |

`MVI_39361` XML은 `camera_state="unstable"`로 표시되어 있으므로, secondary 결과는 default 승격 기준이 아니라 moving/unstable traffic scene robustness 확인으로 해석한다.

## 1. Baseline Policy

Phase 1.2는 baseline을 하나로 고정하지 않는다. 아래 두 profile을 모두 기준으로 둔다.

| Baseline | 역할 |
|---|---|
| `tile_mask_recall_12x12` | 가장 단순한 12x12 tile recall 기준선 |
| `small_object_tile_recall_12x12_overlap` | Phase 1.1 practical default 후보이지만 아직 tuning 대상 |

비교 원칙:

- 새 후보는 두 baseline 모두와 비교한다.
- `small_object_tile_recall_12x12_overlap`도 확정 default가 아니라 개선/대체 가능한 후보로 본다.
- feedback/fallback 후보는 별도 보조 기능이 아니라, ROI 품질을 실질적으로 개선할 수 있는지 Phase 1.2에서 다시 검증한다.
- 모든 판단 artifact는 실제 selected tile trace가 남는 diagnostics run을 기준으로 한다.

## 2. Active Workstreams

Phase 1.2 active workstream은 네 개로 제한한다.

진행 상태:

- [x] Workstream A: Failure Taxonomy And Baseline Lock
- [x] Workstream B: Adaptive Tile Threshold
- [x] Workstream C: Near-Threshold Neighbor Rescue
- [x] Workstream D: Feedback And Fallback Retuning

### Workstream A: Failure Taxonomy And Baseline Lock

목표:

- boundary miss와 false ROI를 같은 기준으로 분류한다.
- 이후 실험이 어떤 실패 타입을 줄였는지 확인할 수 있게 한다.

작업:

- [x] `tile_mask_recall_12x12`와 `small_object_tile_recall_12x12_overlap`를 tile-trace diagnostics로 재실행
- [x] `margin_plus`와 `feedback_actual_yolo` reference run 재실행
- [x] secondary `MVI_39361` cross-check matrix 실행
- [x] miss frame을 아래 타입으로 분류
  - selected tile은 맞았지만 ROI boundary/margin이 부족한 경우
  - adjacent/near-threshold tile이 빠진 경우
  - motion signal 자체가 약하거나 없는 경우
  - noise tile이 selected tile 또는 ROI로 승격된 경우
  - feedback/fallback이 필요한 경우
- [x] false ROI taxonomy 추가
- [x] 대표 frame visualization artifact 생성
- [x] run log 작성: `docs/runs/phase1_2/phase1_2_workstream_a_baseline_lock_20260901.md`

채택 기준:

- [x] Phase 1.2의 모든 후보가 이 baseline/run provenance를 기준으로 비교 가능해야 한다.

### Workstream B: Adaptive Tile Threshold

목표:

- TileClipper/Reducto 관점처럼 global threshold 대신 tile별 또는 구간별 threshold를 적용해 false ROI를 줄인다.

작업:

- [x] `per_tile_motion_threshold` 후보 구현
- [x] `scene_profile_threshold` 후보는 보류. `MVI_39361` 분석상 global motion/scene-state handling으로 분리하는 편이 낫다.
- [x] `rare_tile_guard` 후보 구현 또는 제외 근거 기록
- [x] main dataset 600-frame 비교 실행
- [x] secondary `MVI_39361` cross-check 실행
- [x] run log 작성: `docs/runs/phase1_2/phase1_2_workstream_b_adaptive_threshold_20260901.md`
- [x] `adaptive_threshold_ema`는 Disable, `rare_tile_guard`는 Workstream C 조합 후보로 유지

후보:

| 후보 | 설명 |
|---|---|
| `per_tile_motion_threshold` | tile별 최근/구간 motion density 분포를 기준으로 threshold 조정 |
| `scene_profile_threshold` | frame/segment motion 수준에 따라 threshold profile 전환 |
| `rare_tile_guard` | 거의 선택되지 않던 tile이 갑자기 켜질 때 약한 evidence면 보류 |

비교 기준:

- `tile_mask_recall_12x12` 대비 containment를 크게 잃지 않는다.
- `small_object_tile_recall_12x12_overlap` 대비 false ROI, tensor cost, fallback 중 하나 이상을 줄인다.
- boundary miss가 늘어나면 단독 default로 승격하지 않는다.

판정:

- `adaptive_threshold_ema`: Disable. Cost는 줄였지만 containment regression이 너무 크다.
- `rare_tile_guard`: Keep/Tune. 단독 default는 아니며 Workstream C neighbor rescue와 조합해 재평가한다.

### Workstream C: Near-Threshold Neighbor Rescue

목표:

- GT가 ROI 경계에서 살짝 잘리는 문제를 무조건 dilation이 아니라 evidence 기반 인접 tile 보강으로 해결한다.

작업:

- [x] `neighbor_motion_weak` 후보 구현
- [x] `boundary_only_rescue` 후보 구현 또는 제외 근거 기록
- [x] `rescue_with_budget_cap` 후보 구현
- [x] `margin_plus` 대비 containment/cost 비교 실행
- [x] boundary miss 회복 대표 frame visualization 생성

후보:

| 후보 | 설명 |
|---|---|
| `neighbor_motion_weak` | selected tile 주변 1-ring 중 motion density가 main threshold의 일정 비율 이상이면 포함 |
| `boundary_only_rescue` | miss가 자주 발생하는 ROI 방향에만 weak neighbor 적용 |
| `rescue_with_budget_cap` | 추가 tile 수와 tensor cost cap을 둔 neighbor rescue |

비교 기준:

- `small_object_tile_recall_12x12_overlap_margin_plus`와 비교해 containment/cost 균형이 좋아야 한다.
- Phase 1.1에서 rollback한 `dilation_down1`처럼 tile/frame, tensor cost, fallback이 크게 증가하면 제외한다.
- visualization에서 boundary miss 회복이 실제로 보여야 한다.

결과:

- `neighbor_motion_weak`: containment는 가장 크게 회복되지만 tensor cost와 fallback이 같이 증가한다.
- `rescue_with_budget_cap`: `margin_plus`보다 containment와 false ROI가 모두 개선되며, fallback 증가 없이 cost 증가를 제한한다.
- `boundary_only_rescue`: online policy에서 GT를 직접 사용할 수 없으므로 이번 단계에서는 별도 구현하지 않고 taxonomy 기반 분석 항목으로 보류한다.
- secondary `MVI_39361`: global motion fallback 지배 구간이라 neighbor rescue로 해결되지 않는다. 이 데이터는 계속 stress/cross-check로만 사용한다.

### Workstream D: Feedback And Fallback Retuning

목표:

- Phase 1.1 feedback 결과가 만족스럽지 않았으므로, feedback/fallback을 다시 설계해 볼 가치가 있는지 확인한다.
- feedback은 기본 경로가 아니라 motion/tile signal이 약한 구간을 보완하는 limited assist로 검증한다.

작업:

- [x] `feedback_confidence_decay` 후보 구현
- [x] `low_frequency_feedback_assist` 후보 구현
- [x] `fallback_reason_retune` 후보 구현
- [x] `feedback_roi_budget_cap` 후보 구현
- [x] actual YOLO feedback 기준 비교 실행

후보:

| 후보 | 설명 |
|---|---|
| `feedback_confidence_decay` | 오래된 detector bbox의 confidence를 시간에 따라 낮춰 stale ROI를 줄임 |
| `low_frequency_feedback_assist` | 매 프레임 feedback이 아니라 no-ROI risk 또는 repeated miss 구간에만 사용 |
| `fallback_reason_retune` | batch overflow, no ROI, dense scene fallback 조건을 분리해 threshold/cap 재조정 |
| `feedback_roi_budget_cap` | feedback ROI가 tile ROI보다 비용을 과하게 늘리지 않도록 별도 cap 적용 |

비교 기준:

- actual YOLO feedback 기준으로 평가한다. Oracle feedback은 upper bound로만 본다.
- `feedback_actual_yolo_top2`보다 ROI/frame, false ROI, fallback을 줄이면서 containment를 유지하거나 개선해야 한다.
- feedback이 특정 실패 타입만 해결하면 default가 아니라 optional high-recall profile로 남긴다.

결과:

- `feedback_confidence_decay`: actual YOLO 기준에서 containment와 false ROI가 모두 가장 좋다. 단 tensor cost가 높아 optional high-recall 후보로 유지한다.
- `feedback_roi_budget_cap`: feedback assist를 더 보수적으로 제한하지만, `feedback_confidence_decay`보다 recall이 낮다.
- `low_frequency_feedback_assist`: policy ROI가 대부분 존재하는 main dataset에서는 feedback이 거의 적용되지 않아 C baseline과 동일하다. registry에서는 disable한다.
- `fallback_reason_retune`: fallback은 1 frame 줄지만 recall 개선 폭이 작아 default 후보로 올리지 않는다.

## 3. Evaluation Rule

항상 비교할 baseline:

- `tile_mask_recall_12x12`
- `small_object_tile_recall_12x12_overlap`

필요할 때 비교할 reference:

- `small_object_tile_recall_12x12_overlap_margin_plus`
- `feedback_assisted_tile_12x12_overlap_top2`
- `feedback_actual_yolo_top2`

핵심 지표:

- target ROI containment
- missed target GT count
- missed target frame count
- false ROI count/rate
- ROI/frame
- selected tile/frame
- tensor cost/frame
- effective input area reduction
- fallback frame count and fallback reason
- feedback-assisted ROI/frame

시각화:

- actual `tile_metadata.jsonl` 기반 selected tile
- final ROI / downstream inference area
- contained/missed GT
- feedback ROI와 tile ROI 색상 분리
- 후보별로 같은 frame set side-by-side 비교

## 4. Recommended Execution Order

1. [x] Workstream A: 두 baseline의 true tile trace와 failure taxonomy 고정
2. [x] Workstream B: adaptive tile threshold로 noise ROI 감소 실험
3. [x] Workstream C: near-threshold neighbor rescue로 boundary miss 감소 실험
4. [x] Workstream B+C 조합 후보를 600-frame으로 검증
5. [x] Workstream D: feedback/fallback retuning을 actual YOLO 기준으로 재평가

Phase 1.2의 1차 성공 기준은 다음 중 하나다.

- `tile_mask_recall_12x12`를 유지하고 optional overlap/rescue profile을 분리한다.
- `small_object_tile_recall_12x12_overlap`를 더 낮은 noise/cost profile로 tune한다.
- adaptive threshold + neighbor rescue 조합을 새 practical default 후보로 올린다.
- feedback/fallback은 default가 아니라 limited high-recall assist로 정리한다.

## 5. Defer To Phase 1.3

아래 항목은 Phase 1.2에서 active로 다루지 않는다.

| 항목 | Phase 1.3로 넘기는 이유 |
|---|---|
| heatmap/contour ROI alternative | tile path의 adaptive/rescue 개선을 먼저 본 뒤 대체 후보로 비교하는 편이 낫다 |
| event polarity map | RGB frame-diff 기반에서 event-like signal 정의가 먼저 필요하다 |
| compressed-domain motion vector ROI | codec/decoder 접근성 확인 비용이 있고 현재 문제와 직접성이 낮다 |
| non-uniform tile layout optimization | fixed 12x12 baseline의 threshold/rescue 한계를 먼저 확인해야 한다 |
| online profile controller | profile별 장단점 데이터가 더 쌓인 뒤 controller를 설계해야 한다 |
| advanced ROI packing/batching | 지금 병목은 packing보다 selected tile quality와 fallback 조건이다 |
| ROI quality / QP action | ROI 생성 이후 encoding policy 영역이다 |
