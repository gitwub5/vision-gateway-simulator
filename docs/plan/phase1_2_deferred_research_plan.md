# Phase 1.2 Deferred Research Plan

이 문서는 Phase 1.1 ROI Gate policy 검증 범위에서 의도적으로 제외한 항목을 Phase 1.2 deferred research 후보로 관리한다.

Phase 1.2는 Phase 1.1에서 `component_bbox`, `tile_mask`, `hybrid_component_tile` baseline과 ROI/tile/batch cost metric이 정리된 뒤 진행한다.

## 1. 진입 조건

Phase 1.2 후보는 다음 조건 중 하나를 만족할 때 착수한다.

- Phase 1.1에서 ROI/tile/batch cost metric이 안정적으로 생성된다.
- Phase 1.1에서 `tile_mask` 또는 `hybrid_component_tile`이 Keep/Tune 판정을 받는다.
- MacBook 실험만으로 판단하기 어려워 Jetson/DeepStream 측정이 필요하다.
- GPU 앞단 ROI contract를 실제 deployment pipeline으로 옮길 준비가 되었다.

## 2. 후보 항목

| 항목 | 목적 | Phase 1.1에서 제외한 이유 | 착수 조건 |
|---|---|---|---|
| Compressed-domain motion vector ROI | RGB frame difference 대신 codec/decoder metadata로 ROI signal 생성 | component/tile/hybrid baseline 판단이 먼저 | PyAV/FFmpeg/DeepStream에서 motion vector 접근 가능성 확인 필요 |
| Online profile controller | scene state에 따라 ROI policy/profile 자동 선택 | calibration data가 충분히 쌓이기 전에는 과설계 | Reducto/TileClipper식 segment profile table 생성 후 |
| Tracking-assisted ROI 독립 구현 | 정지/느린 객체를 track memory로 보존 | feedback cache 없이 구현하면 scope가 커짐 | Stage C reference feedback 결과가 Keep/Tune일 때 |
| Advanced ROI packing/batching | ROI/tile을 downstream tensor batch에 맞게 최적 packing | Phase 1.1에서는 metric과 budget check만 필요 | `roi_batch_slots_used`, `tensor_batch_cost`가 실제 병목으로 확인될 때 |
| Large merged ROI split | 큰 merged ROI를 여러 유효 region으로 분할 | tile policy baseline 비교 전에는 필요 여부 불명확 | `component_bbox`가 Keep이고 large merge만 반복 실패할 때 |
| Non-uniform tile layout optimization | scene prior에 맞는 non-uniform tile grid 설계 | A0/A1에서는 fixed grid baseline이 먼저 | fixed `tile_mask`가 Keep/Tune이고 tile overhead가 병목일 때 |
| Feedback confidence decay / stale refresh | 실제 detector feedback의 오래된/불확실한 bbox를 비용 효율적으로 관리 | Phase 1.1에서는 feedback 후보 효과 확인까지만 수행 | `feedback_assisted_*`가 Keep/Tune이고 actual detector feedback 비용이 병목일 때 |
| No-ROI target risk refresh | ROI가 비는 구간에서 target miss 위험을 보고 full-frame refresh를 조정 | scene/controller logic이 필요해 Phase 1.1 범위를 넘음 | reference feedback과 refresh reason schema가 안정화된 뒤 |
| ROI quality / QP action | ROI와 non-ROI의 encoding quality를 다르게 제어 | ROI 생성보다 encoding policy에 가까움 | bandwidth/encoding PoC가 Phase scope에 들어올 때 |
| ROI enhancement / idle GPU reuse | 절약한 GPU budget을 low-quality ROI enhancement에 재투자 | ROI Gate baseline 전에는 범위가 큼 | ROI gate가 안정적으로 cost를 절감한 뒤 |

## 3. Compressed-domain Motion Vector Probe

### 질문

Pixel-domain frame difference보다 H.264/H.265 motion vector, macroblock, bitrate 같은 compressed-domain feature가 ROI candidate signal로 더 안정적인가?

### 확인 항목

- FFmpeg 또는 PyAV로 motion vector 접근 가능성
- dataset codec별 지원 여부
- motion vector 기반 tile activity map 생성 가능성
- frame difference ROI와 noise/coverage 비교
- Jetson/DeepStream pipeline metadata 전달 가능성

### 보류 기준

- dataset별 codec 차이로 재현성이 떨어진다.
- extraction cost가 frame difference보다 크다.
- motion vector가 target containment를 안정적으로 설명하지 못한다.

## 4. Online Profile Controller

### 질문

Scene state에 따라 `component_bbox`, `tile_mask`, `hybrid_component_tile`, small-object profile을 자동 선택할 수 있는가?

### 필요한 선행 데이터

- segment motion density distribution
- candidate count distribution
- selected area/tile count distribution
- fallback reason distribution
- small/medium/large miss distribution
- policy별 Keep/Tune 결과

### 착수 기준

Phase 1.1에서 최소 두 개 이상의 policy/profile이 서로 다른 scene에서 장단점을 보일 때 착수한다.

## 5. Advanced ROI Packing / Batching

### 질문

DeepStream/TensorRT batch constraint에 맞춰 ROI/tile을 더 잘 묶으면 실제 latency가 줄어드는가?

### 확인 항목

- `max_roi_per_frame`과 network input batch dimension 연결
- ROI resize target과 model input shape 연결
- tile grouping과 batch slot 사용량 비교
- ROI count가 많은 scene에서 grouping/packing 이득

### 착수 기준

Phase 1.1 A2에서 `batch_slot_overflow` 또는 `tensor_batch_cost`가 주요 fallback reason으로 확인될 때.

## 6. Non-uniform Tile Layout

### 질문

Fixed grid `tile_mask`보다 static scene prior 기반 non-uniform tile layout이 더 적은 tile count와 더 나은 containment를 제공하는가?

### 참고 근거

- CrossRoI: tile mask optimization
- TASM: non-uniform fine-grained tile layout and cost model
- TileClipper: per-tile adaptive threshold

### 착수 기준

Fixed grid `tile_mask`가 target containment는 좋지만 tile count/tensor cost가 높은 경우.

## 7. 문서화 기준

Phase 1.2 후보를 실제 구현으로 승격할 때는 별도 implementation plan을 만든다.

승격 전까지 이 문서는 deferred research plan이며, Phase 1.1 Keep/Tune/Disable/Remove 판정을 대체하지 않는다.
