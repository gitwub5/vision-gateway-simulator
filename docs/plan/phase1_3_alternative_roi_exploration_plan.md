# Phase 1.3 Alternative ROI Exploration Plan

이 문서는 Phase 1.2 이후 진행할 tile 기반 외 대안 실험 계획을 정리한다.

Phase 1.3의 목적은 Phase 1.2에서 강화한 tile-based ROI Gate를 기준선으로 두고, tile이 아닌 방식 또는 tile 구조를 크게 바꾸는 방식이 더 좋은지 검증하는 것이다.

Phase 1.3은 Phase 1.2의 연장 튜닝 단계가 아니다. 더 나은 대안이 확인되면 Phase 1.1/1.2의 tile 기반 기술을 대체하거나 hybrid로 흡수할 수 있다.

## 1. Entry Condition

Phase 1.3은 아래 조건이 충족된 뒤 시작한다.

- Phase 1.2에서 tile-based best practical profile이 정리된다.
- boundary miss와 false ROI의 주요 실패 타입이 run log로 분류되어 있다.
- actual selected tile trace와 final ROI를 같은 frame set에서 비교할 수 있는 visualization artifact가 있다.
- feedback/fallback이 default path인지 optional assist인지 Phase 1.2에서 1차 결론이 난다.

## 2. Baselines

Phase 1.3의 모든 대안은 아래 기준선과 비교한다.

| Baseline | 역할 |
|---|---|
| Phase 1.2 best tile profile | 대안이 넘어야 하는 practical 기준선 |
| `tile_mask_recall_12x12` | 가장 단순한 tile baseline |
| `small_object_tile_recall_12x12_overlap` | Phase 1.1/1.2 연결 기준 |
| best feedback/fallback assist profile | feedback 계열 대안 비교 기준 |

## 3. Candidate Workstreams

### Workstream A: Heatmap/Contour ROI

목표:

- fixed tile grid에 묶이지 않고 low-res motion/event heatmap에서 contour 기반 ROI를 생성한다.

검증 질문:

- tile boundary 때문에 잘리는 GT miss를 줄이는가?
- tile grouping보다 ROI/frame 또는 tensor cost가 낮은가?
- 작은 noise contour가 false ROI로 늘어나지 않는가?

### Workstream B: Event-Like Signal Separation

목표:

- RGB frame difference를 단일 motion map으로만 보지 않고, event-like 변화 signal을 분리해서 ROI 후보 품질을 높인다.

후보:

- positive/negative intensity change 분리
- edge-aware motion map
- short-window temporal consistency filter

검증 질문:

- 조명/배경 변화성 noise를 줄이는가?
- 사람 edge나 small target motion을 더 안정적으로 잡는가?

### Workstream C: Non-Uniform Or Learned Tile Layout

목표:

- fixed 12x12 grid가 장면 구조와 맞지 않을 때, 더 나은 tile layout이 가능한지 확인한다.

후보:

- scene prior 기반 non-uniform tile layout
- motion/GT 분포 기반 tile split/merge
- region-specific tile size

검증 질문:

- 같은 containment에서 selected tile/frame과 tensor cost를 줄이는가?
- 특정 camera/scene에 과적합되지 않는가?

### Workstream D: Compressed-Domain Motion Signal

목표:

- pixel-domain frame difference 대신 codec/decoder metadata를 ROI signal로 쓸 수 있는지 확인한다.

후보:

- H.264/H.265 motion vector 기반 tile activity
- macroblock-level motion density
- decoder-side ROI prefilter

검증 질문:

- extraction cost가 pixel-domain preprocessing보다 낮은가?
- dataset/codec 차이에도 재현 가능한가?
- Jetson/DeepStream pipeline으로 이어질 수 있는가?

## 4. Deferred Within Phase 1.3

아래 항목은 Phase 1.3에서도 후순위로 둔다.

| 항목 | 이유 |
|---|---|
| online profile controller | profile별 충분한 승패 데이터가 쌓인 뒤 설계해야 함 |
| advanced ROI packing/batching | ROI 후보 품질 개선 후 실제 bottleneck으로 확인될 때 착수 |
| ROI quality / QP action | ROI 생성이 아니라 encoding/action policy 영역 |
| idle GPU reuse / ROI enhancement | ROI gate 절감 효과가 안정화된 뒤 검토 |

## 5. Evaluation Rule

핵심 지표는 Phase 1.2와 동일하게 유지한다.

- target ROI containment
- missed target GT count
- missed target frame count
- false ROI count/rate
- ROI/frame
- selected tile/frame 또는 equivalent region count/frame
- tensor cost/frame
- effective input area reduction
- fallback frame count and reason

대안 채택 기준:

- Phase 1.2 best tile profile보다 containment/cost 균형이 좋아야 한다.
- 특정 실패 타입만 개선하면 default가 아니라 assist/hybrid 후보로 둔다.
- 구현 복잡도가 큰 후보는 120-frame probe에서 명확한 개선 신호가 있을 때만 600-frame 검증으로 올린다.

## 6. Recommended Order

1. Heatmap/contour ROI probe
2. Event-like signal separation probe
3. Heatmap/event 후보 중 살아남은 것만 600-frame 검증
4. Non-uniform tile layout probe
5. Compressed-domain motion signal feasibility check

Phase 1.3의 1차 성공 기준은 tile 기반을 반드시 대체하는 것이 아니라, Phase 1.2 best tile profile 이후에도 의미 있는 대안이 있는지 분명히 판단하는 것이다.
