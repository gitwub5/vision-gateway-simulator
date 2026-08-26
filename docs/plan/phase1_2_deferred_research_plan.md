# Phase 1.2 ROI Gate Exploration Plan

이 문서는 Phase 1.1 이후 실제로 진행할 Phase 1.2 후보만 남긴다.

Phase 1.2의 목표는 Phase 1.1에서 남긴 tile/overlap/recall 경로를 baseline으로 삼되, 더 나은 방법이 확인되면 Phase 1.1 기술을 대체하거나 일부 제거할 수 있는 비교 실험을 진행하는 것이다.

따라서 Phase 1.2는 단순 tuning phase가 아니다. 다음 세 범주를 같은 기준으로 비교한다.

1. Phase 1.1 continuation: 기존 tile/overlap/recall 경로를 튜닝
2. Hybrid candidates: 기존 경로에 feedback, neighbor rescue 등을 결합
3. Alternative candidates: 기존 tile/overlap 구조를 덜 쓰거나 빼고 다른 signal/policy를 사용

실험이 해결하려는 우선 문제는 다음 두 가지다.

1. 아주 작은 경계 차이로 GT bbox가 ROI 밖에 걸리는 boundary miss
2. 노이즈/일시적 motion 때문에 ROI가 불필요하게 생기는 false ROI

## 1. Phase 1.2 Baseline And Replacement Rule

Phase 1.2는 아래 profile을 기준선으로 둔다. 기준선은 유지 대상이 아니라 비교 대상이다.

| 역할 | Profile |
|---|---|
| Tile baseline | `tile_mask_recall_12x12` |
| Practical default candidate | `small_object_tile_recall_12x12_overlap` |
| Margin tuning reference | `small_object_tile_recall_12x12_overlap_margin_plus` |
| Feedback challenger | `feedback_assisted_tile_12x12_overlap_top2` |

Phase 1.1에서 검토한 `tile_dilation_down1`은 active code로 남기지 않는다. Recall은 올랐지만 selected tile count, tensor cost, fallback 증가가 커서 Phase 1.2의 기본 출발점으로 적합하지 않다.

대체 규칙:

- 새 후보가 `small_object_tile_recall_12x12_overlap`보다 containment/cost 균형이 좋으면 Phase 1.1 default 후보를 교체한다.
- 새 후보가 tile/overlap 없이도 더 좋은 성능을 내면 tile/overlap 경로는 baseline 또는 fallback으로 강등한다.
- 새 후보가 특정 miss/noise 타입만 해결하면 optional assist profile로 남긴다.

## 2. Active Questions

Phase 1.2에서 답해야 할 질문은 네 가지로 제한한다.

| 질문 | 의도 |
|---|---|
| 실제 selected tile과 ROI boundary miss가 어떻게 연결되는가? | margin 문제인지, tile selection 문제인지 분리 |
| dense heatmap/contour가 grid boundary miss를 줄이는가? | tile grid에 묶이지 않는 ROI 후보 검증 |
| weak neighbor tile을 조건부로 살리면 boundary miss를 줄일 수 있는가? | 무조건 dilation 대신 근거 있는 인접 tile만 포함 |
| tile/overlap 없이 다른 signal만 써도 더 좋은가? | Phase 1.1 기술 제거 가능성 확인 |

## 3. Stage A: True Tile Trace Baseline

### 목표

Phase 1.2의 모든 실험은 실제 selected tile 위치를 남긴 상태에서 비교한다.

Phase 1.1 minimal diagnostics run은 `selected_tile_count`만 남기고 tile별 row/col selection은 남기지 않았다. 이 때문에 시각화에서 ROI 기반으로 재구성한 blue tile overlay와 실제 selected tile이 섞여 해석 혼란이 있었다.

### 작업

- Stage B/C/D 주요 후보를 `diagnostics-level full` 또는 tile trace 전용 lightweight mode로 재실행
- `tile_metadata.jsonl` 기반 시각화만 Phase 1.2 판단 artifact로 사용
- boundary miss frame을 다음 타입으로 분류
  - selected tile은 맞지만 ROI margin이 부족한 경우
  - adjacent/near-threshold tile이 선택되지 않은 경우
  - motion signal 자체가 없는 경우
  - feedback/temporal memory가 필요한 경우

### 산출물

- true selected tile comparison artifact
- boundary miss taxonomy run log

Stage A 공식 baseline과 실행 provenance는
`docs/runs/phase1_2/phase1_2_readiness_baselines_20260826.md`를 따른다.
이 baseline은 `diagnostics-level=tile_trace`로 실제 selected tile 위치를 남기며,
이전 minimal diagnostics run은 tile-level 원인 판단에 사용하지 않는다.

## 4. Stage B: Alternative Signal Probes

### 목표

Phase 1.1의 tile/overlap policy가 최선이라는 가정을 깨고, 다른 signal 또는 더 단순한 policy가 더 좋은지 확인한다.

이 단계는 production-grade 구현이 아니라 120-frame/600-frame으로 빠르게 가능성을 거르는 probe다.

### 후보

| 후보 | 설명 | 남기는 이유 |
|---|---|---|
| heatmap ROI | tile id가 아니라 low-res motion/event heatmap에서 threshold/contour로 ROI 생성 | grid 경계 문제를 줄일 수 있음 |
| event polarity map | motion map 단독이 아니라 on/off event map을 분리해 ROI signal 생성 | 노이즈와 실제 이동 edge를 분리할 가능성 |
| no-overlap tile baseline | overlap 없이 tile selection만 적용 | overlap이 실제로 필요한지 검증 |
| feedback-only limited | tile 없이 periodic/full-frame detector feedback만 제한적으로 ROI 생성 | Stage D feedback이 tile path를 대체할 수 있는지 확인 |

### 보류 후보

| 후보 | 보류 이유 |
|---|---|
| Compressed-domain motion vector ROI | 해볼 가치는 있지만 codec/decoder 접근성 확인이 먼저라 Stage C 후반 probe로 둔다 |
| Non-uniform tile layout optimization | fixed 12x12의 temporal/signal 개선 효과를 본 뒤 비교해야 함 |

## 5. Stage C: Near-Threshold Neighbor Rescue

### 목표

무조건 인접 tile을 확장하지 않고, selected tile 주변의 weak evidence tile만 조건부로 포함한다.

Phase 1.1의 `dilation_down1`은 아래 tile을 무조건 포함해서 recall은 올렸지만 cost/fallback이 증가했다. Phase 1.2에서는 다음처럼 근거 있는 주변 tile만 살린다.

```text
selected tile group 주변 1-ring tile 중
motion_density 또는 event evidence가 weak threshold 이상이면
해당 tile을 group에 포함
```

### 후보 방식

| 후보 | 설명 |
|---|---|
| `neighbor_motion_weak` | 인접 tile의 현재 motion density가 main threshold의 일정 비율 이상이면 포함 |
| `neighbor_event_weak` | 인접 tile의 on/off event evidence가 weak threshold 이상이면 포함 |
| `boundary_only_rescue` | GT miss가 자주 발생하는 ROI boundary 방향에만 후보 적용 |

### 채택 기준

- `margin_plus 0.35` 대비 containment가 좋아지거나 비슷하다.
- `dilation_down1`보다 tile/frame, tensor cost, fallback이 낮다.
- 시각화에서 boundary miss는 줄고 noise tile 확장은 제한된다.

## 6. Stage D: Feedback Tuning Or Replacement

### 목표

`feedback_assisted_tile_12x12_overlap_top2`는 Phase 1.1에서 challenger로 남겼지만 detector dependency와 cost가 크다. Phase 1.2에서는 feedback을 기본 방향으로 밀기보다, tile/heatmap/event signal로 해결되지 않는 miss 타입에만 제한적으로 쓴다.

### 후보

| 후보 | 설명 |
|---|---|
| feedback confidence decay | 오래된 detector bbox의 score를 시간에 따라 낮춤 |
| stale refresh reason | feedback이 오래되거나 불확실할 때만 refresh/full-frame reason 기록 |
| low-frequency feedback assist | 매 프레임 보조가 아니라 no-ROI risk 또는 repeated miss 구간에만 사용 |

### 착수 조건

Stage B/C 이후에도 `motion signal 자체가 없는 경우` 또는 `정지/느린 target miss`가 주요 실패 타입으로 남을 때만 진행한다.

대체 가능성:

- feedback-only limited가 tile/overlap보다 containment/cost 균형이 좋으면 Phase 1.1 tile path를 대체 후보로 올린다.
- feedback이 특정 정지/느린 객체 miss에만 강하면 assist path로 제한한다.

## 7. Deferred, Not Active For Now

아래 항목은 지금 문제와 직접성이 낮거나 구현 비용이 커서 Phase 1.2 초반 active scope에서 제외한다. 단, Stage A-D 결과가 해당 방향을 강하게 지지하면 후반 probe로 승격할 수 있다.

| 항목 | 보류 이유 |
|---|---|
| Online profile controller | 현재는 controller보다 signal/state 품질 문제가 먼저 |
| Advanced ROI packing/batching | 지금 병목은 packing보다 selected tile quality와 boundary miss |
| Large merged ROI split | tile-first path에서 우선순위 낮음 |
| ROI quality / QP action | ROI 생성이 아니라 encoding policy 영역 |
| ROI enhancement / idle GPU reuse | ROI gate가 안정화된 뒤 검토 |

## 8. Evaluation Rule

Phase 1.2는 실험 수를 늘리더라도 판단 기준은 작게 유지한다.

항상 비교할 기준:

- `tile_mask_recall_12x12`
- `small_object_tile_recall_12x12_overlap`
- best Phase 1.1 challenger when relevant
- 새 후보

핵심 지표:

- target ROI containment
- missed target GT count
- small-object containment / missed small GT
- ROI/frame
- selected tile/frame
- tensor cost/frame
- effective input area reduction
- fallback frame count
- false ROI rate

시각화:

- 실제 `tile_metadata.jsonl` 기반 selected tile
- final ROI
- contained/missed GT
- feedback ROI가 있으면 tile ROI와 색상 분리

## 9. Recommended Order

1. Stage A: true tile trace baseline과 boundary miss taxonomy 생성
2. Stage B: heatmap/event/no-overlap/feedback-only 대안 probe를 작게 비교
3. Stage B에서 살아남은 후보 1-2개만 600-frame 검증
4. Stage C: near-threshold neighbor rescue를 surviving tile 후보 위에 추가
5. Stage D: 남은 miss 타입이 feedback 계열일 때만 confidence decay/stale refresh 또는 feedback replacement 검토

Phase 1.2의 1차 성공 기준은 새 default 확정이 아니라, `small_object_tile_recall_12x12_overlap`의 Keep/Tune 상태를 다음 중 하나로 좁히는 것이다.

- Keep as default
- Replace with heatmap/event/feedback-limited profile
- Keep default but add near-threshold rescue or feedback as optional high-recall profile
