# Phase 1.1 ROI Gate Policy Implementation Plan

이 문서는 Phase 1.1에서 GPU 앞단 ROI/Gate policy를 검증하기 위한 공유 구현 계획이다.

Phase 1.1의 목표는 ROI crop 면적을 무조건 줄이는 것이 아니다. 산업/장면별 target class에 필요한 ROI를 충분히 포함하면서, 모델 입력 픽셀량, ROI 개수, tile 개수, tensor batch slot, full-frame refresh/fallback 비용을 함께 줄일 수 있는지 검증한다.

리서치 검토에 따라 Phase 1.1의 중심을 `component_filter` 개선에서 **ROI Gate policy contract 검증**으로 수정한다.

## 1. 핵심 결론

현재 구현된 경로는 유지한다.

```text
frame difference -> motion map -> connected component -> bbox ROI -> YOLO
```

다만 이 경로를 최종 방향으로 고정하지 않고, 새 계획에서는 `component_bbox` baseline으로 재정의한다. Phase 1.1에서 비교할 policy family는 다음 세 가지다.

| Policy | 의미 | 현재 구현과의 관계 |
|---|---|---|
| `component_bbox` | motion connected component를 bbox ROI로 변환 | 이미 구현된 현재 방식. baseline으로 유지 |
| `tile_mask` | 화면을 grid/tile로 나누고 tile activity/GT containment 기준으로 tile set 선택 | CrossRoI, TileClipper, TASM 리서치 반영 신규 경로 |
| `hybrid_component_tile` | component bbox 후보를 만들되 tile score/history/budget으로 살리거나 버림 | component path와 tile path를 연결하는 후보 |

수정된 Phase 1.1의 구조는 다음이다.

```text
low-level signal
  -> tile/component candidates
  -> budget-aware selection
  -> downstream ROI batch contract
```

## 2. 원칙

Phase 1.1의 모든 변경은 가설 단위로 구현한다. 각 가설은 feature flag/config로 켜고 끌 수 있어야 한다.

각 가설은 다음 중 하나로 판정한다.

| 판정 | 의미 | 처리 |
|---|---|---|
| Keep | 기준 metric이 baseline보다 개선되거나 동일 성능에서 비용이 줄어듦 | 기본 후보로 유지 |
| Tune | 방향은 맞지만 특정 dataset/profile에서 기준 미달 | config나 threshold를 조정한 뒤 재검증 |
| Disable | 일부 환경에서만 유효하거나 불안정함 | feature flag로 비활성화하고 코드 경로는 보존 |
| Remove | 성능 개선 근거가 없고 복잡도만 늘어남 | 구현 제거 또는 실험 branch로 격리 |

체크박스는 실제 구현, 최소 동작 확인, 검증 산출물 생성이 끝났을 때만 완료 처리한다. 단순 파일 생성이나 미사용 코드 추가만으로 완료 처리하지 않는다.

## 3. 이미 구현된 것의 처리

이미 구현된 기능은 폐기하지 않고 새 구조 안에서 역할을 재배치한다.

| 기존 구현/계획 | 새 역할 | 처리 |
|---|---|---|
| 현재 ROI generator | `component_bbox` baseline | 유지 |
| `baseline_balanced` | `component_bbox_balanced` alias | 기존 이름 유지 가능, 설명 보강 |
| `balanced_highres` | `component_bbox_highres` profile | 유지 |
| `experiments/run_roi_proposal_validation.py` | 모든 policy 공통 검증 runner | 유지 |
| annotation 기반 GT containment / missed target report | 핵심 success metric | 유지 |
| ROI debug renderer | component/tile/hybrid 공통 visualization 기반 | 확장 |
| `component_filter.enabled` 계획 | `component_bbox` tuning option | Stage A1로 이동 |
| minimum final ROI size / padding 계획 | small-object policy option | Stage B로 이동 |
| adaptive refresh 단독 stage | reference detector feedback 일부 | Stage C로 흡수 |
| tracking-assisted ROI 단독 stage | feedback/hold policy 후보 | Stage C 이후 재검토 |
| compressed-domain probe | Phase 1.2 research 후보 | Phase 1.1에서 제외 |

## 4. 선행 완료 작업

다음 항목은 Phase 1.1의 공통 기반으로 완료된 상태다.

- [x] OD-VIRAT Tiny annotation JSON reader 구현
- [x] `image_id`, `file_name`, dataset `frame_id` mapping 확정
- [x] GT bbox/class를 공통 annotation 포맷으로 변환
- [x] GT detection matching 구현
- [x] annotation 품질 metadata 추가
  - [x] `annotations.quality.completeness: partial`
  - [x] `annotations.quality.expected_exhaustive: false`
- [x] annotated-object report 생성
- [x] GT bbox 포함 failure visualization 생성
- [x] OD-VIRAT Tiny 120-frame quick run으로 annotation report 검증
- [x] target-aware ROI validation scope를 dataset config에 추가
- [x] `experiments/run_roi_proposal_validation.py` 구현
- [x] PhysicalAI row 709 120-frame ROI Proposal quick run으로 target GT 기준 report 검증
- [x] ROI generator processing size config 옵션 추가
- [x] `balanced_highres` config 추가
- [x] ROI generator debug trace 시각화 추가
- [x] UA-DETRAC MVI_39051 / PhysicalAI row 709 120-frame ROI debug run으로 candidate 품질 문제 유형 확인
- [x] `roi_generator` 내부 구조를 `core/`, `signals/`, `candidates/`, `policies/`, `observability/` 중심으로 분리

## 5. 파일 단위 구현 계획

이 섹션은 Stage A0-A2 구현 전에 파일 추가/수정 위치를 고정하기 위한 기준이다. 새 기능은 가능한 한 policy, candidate, budget, report 단위로 분리하고, `gate.py`에는 orchestration만 남긴다.

### 현재 구조 기준

| 경로 | 역할 | Phase 1.1 처리 |
|---|---|---|
| `roi_generator/core/gate.py` | `FramePacket -> GateDecision` orchestration | 특정 policy 세부 구현을 넣지 않는다 |
| `roi_generator/core/config.py` | ROI generator config parsing | `roi_policy`, tile/budget/small-object config key 추가 |
| `roi_generator/core/contract.py` | downstream gate decision contract | policy label, decision reason, batch contract field 확장 |
| `roi_generator/core/budget.py` | ROI/batch/tile budget 판단 | A2 cost/fallback 판단 추가 |
| `roi_generator/observability/trace.py` | debug/observability trace | A0 component/tile/cost trace dataclass 추가 |
| `roi_generator/observability/metadata.py` | GateDecision/trace JSONL 변환 | 평가 artifact 생성만 담당 |
| `roi_generator/signals/` | frame diff, motion map, preprocessing | compressed-domain signal은 Phase 1.2로 보류 |
| `roi_generator/candidates/components.py` | component bbox candidate primitive | A0 component metadata 계산 지점 |
| `roi_generator/candidates/tiles.py` | tile grid/activity candidate primitive | A0/A1에서 신규 추가 |
| `roi_generator/policies/component_bbox.py` | 기존 baseline policy | `component_bbox_balanced`, noise filter, recall padding 확장 |
| `roi_generator/policies/tile_mask.py` | tile-first policy | A1에서 신규 추가 |
| `roi_generator/policies/hybrid_component_tile.py` | component + tile hybrid policy | A1에서 신규 추가 |
| `evaluation/reports/roi_proposal.py` | target-aware ROI proposal report | A0/A2 metric 확장 |
| `visualization/roi_debug_renderer.py` | ROI debug trace visualization | component/tile overlay 확장 |
| `experiments/run_roi_proposal_validation.py` | policy 공통 validation runner | output artifact path와 manifest 입력 확장 |

### Stage A0 파일 변경 계획

| 파일 | 변경 내용 | 산출물 |
|---|---|---|
| `roi_generator/core/contract.py` | `policy_label`, `decision_reason`, `batch_slot`, `processing_width`, `processing_height` contract 추가 | `gate_decisions.jsonl` schema 확장 |
| `roi_generator/observability/trace.py` | `ComponentTrace`, `TileTrace`, `CostTrace`, `PolicyTrace` 계열 dataclass 추가 | debug snapshot과 policy trace record |
| `roi_generator/candidates/components.py` | component area, bbox size, aspect ratio, fill density, center 계산 helper 추가 | component metadata |
| `roi_generator/candidates/tiles.py` | fixed grid, per-tile motion density, GT tile containment 계산 helper 추가 | tile metadata |
| `roi_generator/observability/metadata.py` | frame/ROI metadata writer가 policy/cost field를 기록하도록 확장 | JSONL metadata |
| `evaluation/reports/roi_proposal.py` | ROI count, tile count, batch slot, estimated tensor cost, size bucket summary 추가 | report JSON/Markdown |
| `visualization/roi_debug_renderer.py` | component bbox와 tile grid overlay를 함께 렌더링 | ROI debug image |
| `experiments/run_roi_proposal_validation.py` | `policy_traces.jsonl`, `component_metadata.jsonl`, `tile_metadata.jsonl` path 추가 | run artifact 고정 |

### Stage A1 파일 변경 계획

| 파일 | 변경 내용 | 산출물 |
|---|---|---|
| `roi_generator/core/config.py` | `roi_policy` selector와 policy별 config section 추가 | config-driven policy selection |
| `roi_generator/policies/base.py` | policy interface에 policy label, trace output contract 명확화 | 공통 policy contract |
| `roi_generator/policies/component_bbox.py` | noise filter, recall padding profile 지원 | `component_bbox_*` profiles |
| `roi_generator/policies/tile_mask.py` | fixed grid tile activity 기반 ROI 생성 | `tile_mask_balanced` |
| `roi_generator/policies/hybrid_component_tile.py` | component candidate를 tile score/history/budget으로 보정 | `hybrid_component_tile_balanced` |
| `configs/roi_generator/profile_component_bbox_noise_filter.yaml` | component noise filtering profile | 비교 run config |
| `configs/roi_generator/profile_component_bbox_recall_padding.yaml` | small target recall padding profile | 비교 run config |
| `configs/roi_generator/profile_tile_mask_balanced.yaml` | tile-first baseline profile | 비교 run config |
| `configs/roi_generator/profile_hybrid_component_tile_balanced.yaml` | hybrid baseline profile | 비교 run config |
| `tests/roi_generator_tests/test_roi_generator.py` | gate orchestration regression 유지 | 기존 behavior 보호 |
| `tests/roi_generator_tests/test_roi_policy_baselines.py` | component/tile/hybrid policy 단위 테스트 | baseline 보호 |

### Stage A2 파일 변경 계획

| 파일 | 변경 내용 | 산출물 |
|---|---|---|
| `roi_generator/core/budget.py` | `max_roi_per_frame`을 batch slot budget으로 재해석하고 tile/tensor cost budget 추가 | fallback decision |
| `roi_generator/core/contract.py` | `roi_batch_slots_used`, `tile_group_count`, `estimated_tensor_pixels`, `tensor_batch_cost`, `effective_input_area` field 추가 | downstream cost contract |
| `evaluation/reports/roi_proposal.py` | fallback reason distribution과 budget overflow case summary 추가 | cost summary |
| `experiments/run_roi_proposal_validation.py` | `reports/cost_summary.json` 생성 | policy 비교 산출물 |
| `tests/roi_generator_tests/test_roi_budget.py` | area/count/tile/batch fallback unit test 추가 | budget regression guard |
| `tests/roi_generator_tests/test_roi_metadata.py` | metadata serialization unit test 추가 | metadata schema guard |

### Output artifact 구조

Phase 1.1 run output은 기존 `outputs/roi_proposal_validation/<run_id>/` 구조를 유지한다. A0-A2에서 아래 파일을 추가한다.

```text
outputs/roi_proposal_validation/<run_id>/
  manifest.json
  roi_metadata/
    rule_roi.jsonl
    gate_decisions.jsonl
    policy_traces.jsonl          # diagnostics-level=full only
    component_metadata.jsonl     # diagnostics-level=full only
    tile_metadata.jsonl          # diagnostics-level=full only
  reports/
    roi_proposal_report.json
    roi_proposal_report.md
    roi_policy_summary.md
    cost_summary.json
  visualizations/
    failures/
    roi_debug/
    tile_debug/
```

### Config key 구조

```yaml
roi_generator:
  roi_policy: component_bbox
  policies:
    component_bbox:
      component_filter:
        enabled: false
    tile_mask:
      grid_rows: 8
      grid_cols: 8
      motion_density_threshold: 0.02
    hybrid_component_tile:
      tile_score_weight: 0.5

  budget:
    enabled: true
    max_roi_per_frame: 5
    max_total_roi_area_ratio: 0.5
    max_selected_tile_count: null
    max_tensor_batch_cost: null
```

## 6. Stage A0: Observability & ROI Batch Contract

### 목표

성능 개선보다 먼저, `component_bbox`, `tile_mask`, `hybrid_component_tile`을 같은 기준으로 비교할 수 있는 metadata/report contract를 만든다.

### 가설

현재 ROI 실패는 하나의 원인으로 설명되지 않는다. noise candidate 과다, 작은 target 누락, ROI/tile budget overflow, full-frame fallback, downstream batch slot overflow가 섞여 있다. 따라서 A0에서 실패 원인을 분해해 기록하지 않으면 이후 policy 비교가 불가능하다.

### 구현 항목

- [x] ROI debug summary 확장
  - [x] raw component count
  - [x] filtered component count
  - [x] merged ROI count
  - [x] motion density
  - [x] final ROI area ratio
  - [x] fallback reason
- [x] component metadata 기록
  - [x] component area ratio
  - [x] bbox width/height
  - [x] bbox aspect ratio
  - [x] fill density = component area / bbox area
  - [x] component center
- [x] tile metadata 계산
  - [x] tile grid
  - [x] per-tile motion density
  - [x] selected tile count
  - [x] selected tile area ratio
  - [x] GT tile containment / recall
  - [x] false tile ratio against target GT
- [x] downstream ROI batch contract 추가
  - [x] `source_id`
  - [x] `roi_id`
  - [x] `batch_slot`
  - [x] `processing_width`
  - [x] `processing_height`
  - [x] `decision_reason`
- [x] cost metadata 추가
  - [x] `roi_batch_slots_used`
  - [x] `tile_group_count`
  - [x] `estimated_tensor_pixels`
  - [x] `tensor_batch_cost`
  - [x] `effective_input_area`
- [x] fallback/decision reason 체계화
  - [x] `budget_overflow`
  - [x] `roi_area_near_full_frame`

### A0 산출물

- [x] `roi_metadata/policy_traces.jsonl` full diagnostics 산출물
- [x] `roi_metadata/component_metadata.jsonl` full diagnostics 산출물
- [x] `roi_metadata/tile_metadata.jsonl` full diagnostics 산출물
- [x] `reports/roi_policy_summary.md`
- [x] `reports/cost_summary.json`

### 후속 stage로 이관한 항목

아래 항목은 A0 완료 조건에서 제외한다. A0에서는 contract와 산출물 구조만 마련했고, 실제 condition은 해당 stage에서 구현한다.

- `tile_count_overhead_exceeds_gain`: A1 `tile_mask` baseline 이후
- `tile_history_insufficient`: tile history/profile 구현 이후
- `out_of_profile_distribution`: profile/controller 판단 데이터 축적 이후
- `batch_slot_overflow`: A2 batch slot budget 구현 이후
- `feedback_stale`: Stage C reference feedback 구현 이후
- object size bucket metric: Stage B small object policy에서 구현
  - small / medium / large GT count
  - bucket별 ROI containment
  - bucket별 missed target count

### A0에서 하지 않는 항목

- `tile_mask` 최종 selection 최적화
- adaptive refresh 단독 최적화
- tracking-assisted ROI 독립 구현
- detector confidence 기반 online controller
- compressed-domain motion vector prototype
- ROI packing/batching 고급 최적화
- large merged ROI split 알고리즘

### 완료 기준

- 기존 `component_bbox` 경로에서도 A0 metadata가 생성된다.
- 아직 `tile_mask` policy가 없어도 tile grid 기준 GT/motion summary를 계산할 수 있다.
- report에서 ROI area뿐 아니라 ROI count, tile count, batch slot, estimated tensor cost를 함께 볼 수 있다.
- failure visualization과 summary만 보고 실패 유형을 구분할 수 있다.

## 7. Stage A1: ROI Policy Baselines

### 목표

`component_bbox`, `tile_mask`, `hybrid_component_tile`을 같은 dataset과 metric으로 비교한다.

### 가설

`component_bbox`는 단순하고 이미 구현되어 있지만 noise와 merge failure에 취약하다. CrossRoI/TileClipper/TASM 계열의 `tile_mask`는 bbox noise에 덜 민감하고 budget/cost metric과 연결하기 쉽다. `hybrid_component_tile`은 두 접근의 중간점일 수 있다.

### 구현 항목

- [x] `roi_policy=component_bbox | tile_mask | hybrid_component_tile` config 추가
- [x] `component_bbox` path를 명시적 policy로 분리
- [x] `component_bbox_noise_filter` profile 추가
  - [x] `component_filter.enabled`
  - [x] min area ratio
  - [x] max aspect ratio
  - [x] min fill density
- [x] `component_bbox_recall_padding` profile 추가
  - [x] min final ROI width/height
  - [x] padding/margin 강화
- [x] `tile_mask_balanced` profile 추가
  - [x] fixed grid 기반 tile activity map
  - [x] tile motion density threshold
  - [x] selected tile -> rectangular ROI/group 변환
- [x] `hybrid_component_tile_balanced` profile 추가
  - [x] component bbox 후보 생성
  - [x] selected tile activity로 component 후보 gating
  - [x] A1 baseline에서는 tile overlap gating까지만 검증
- [x] 공통 report에 `policy_label` 추가
- [x] debug renderer에서 component ROI와 selected tile overlay를 함께 표시

### 비교 run

| Run | 설명 |
|---|---|
| `component_bbox_balanced` | 기존 balanced baseline |
| `component_bbox_highres` | 기존 balanced high-res profile |
| `component_bbox_noise_filter` | component path noise filtering |
| `component_bbox_recall_padding` | component path 작은 target 보존 |
| `tile_mask_balanced` | fixed grid tile selection |
| `hybrid_component_tile_balanced` | component + tile score hybrid |
| `tile_mask_recall_12x12` | recall-oriented finer tile grid |
| `hybrid_component_tile_cost` | cost-oriented hybrid tile threshold |

### 비교 metric

- target GT ROI/tile containment
- missed target GT count
- no-ROI target frame count
- selected area ratio
- ROI count
- selected tile count
- `roi_batch_slots_used`
- `tensor_batch_cost`
- fallback rate
- small/medium/large object bucket recall
- gate latency

### Keep 기준

- target GT containment가 `component_bbox_balanced`보다 악화되지 않는다.
- missed target GT count가 늘지 않는다.
- selected area ratio 또는 `tensor_batch_cost`가 개선된다.
- ROI count/tile count가 batch budget 안에 들어온다.
- small object bucket에서 baseline 대비 regression이 없다.

## 8. Stage A2: Budget / Cost / Fallback Policy

### 목표

ROI 면적 기준 fallback에서 벗어나, tile/ROI/batch cost를 함께 보는 budget policy를 만든다.

### 가설

ROI area가 줄어도 ROI count, tile count, tensor batch slot이 늘면 실제 GPU 앞단 비용은 줄지 않을 수 있다. Budget policy는 area뿐 아니라 downstream preprocessing/batching cost를 함께 봐야 한다.

### 구현 항목

- [x] `roi_budget.enabled` feature flag 유지/정리
- [x] `max_roi_per_frame`을 DeepStream식 batch slot budget으로 재해석
- [x] `max_total_roi_area_ratio`를 area budget으로 유지
- [x] `max_selected_tile_count` 추가
- [x] `max_tensor_batch_cost` 추가
- [x] `effective_input_area` 계산
- [x] `estimated_tensor_pixels` / `tensor_batch_cost` proxy 계산
- [ ] `tile_not_beneficial_dense_scene` fallback 추가
- [x] `batch_slot_overflow` fallback 추가
- [x] budget decision reason을 `gate_decisions.jsonl`에 기록
- [ ] hybrid policy의 tile history/budget 기반 후보 score 보정 검증

### A2에서 보류하는 항목

- advanced ROI packing
- non-uniform tile layout optimization
- dynamic GOP/SOT tile layout 변경

### Keep 기준

- target GT containment가 Stage A1 best profile보다 악화되지 않는다.
- `effective_input_area` 또는 `tensor_batch_cost`가 줄어든다.
- fallback reason 분포가 해석 가능하다.
- ROI/tile/batch budget overflow case가 report에서 분리된다.

## 9. Stage A3: Lean Validation Boundary

### 목표

A0-A2에서 만든 검증 구조를 새 ROI policy 실험에 부담이 되지 않는 최소 검증 contract로 정리한다. 상세 component/tile/policy trace는 기본 산출물이 아니라 diagnostic tier로만 사용한다.

### 가설

Phase 1.1에서는 ROI gate 구조가 계속 바뀔 가능성이 높다. 따라서 모든 실험에 상세 metadata를 강제하면 policy 구현 속도가 느려진다. 공통 비교에 필요한 최소 contract만 기본으로 유지하고, 실패 원인 분석이 필요할 때만 diagnostics를 켠다.

### Minimal validation contract

기본 run은 아래 산출물만 필수로 생성한다.

```text
roi_metadata/rule_roi.jsonl
roi_metadata/gate_decisions.jsonl
reports/roi_proposal_report.json
reports/roi_proposal_report.md
reports/roi_policy_summary.md
reports/cost_summary.json
visualizations/failures/
```

기본 판단 metric은 다음만 사용한다.

- target GT ROI containment
- missed target GT count
- no-ROI target frame count
- ROI/frame
- ROI batch slots/frame
- selected tiles/frame
- tile groups/frame
- effective input area reduction
- fallback rate / decision reason counts
- gate latency
- policy-specific visualization

### Diagnostics tier

아래 산출물과 지표는 `diagnostics-level=full`에서만 생성/해석한다.

- `roi_metadata/policy_traces.jsonl`
- `roi_metadata/component_metadata.jsonl`
- `roi_metadata/tile_metadata.jsonl`
- target GT tile containment
- false tile ratio
- raw/filtered component count
- motion density
- detailed component/tile failure analysis

### 구현 항목

- [x] duplicated proxy cost field 제거
  - [x] `estimated_preprocess_cost`
  - [x] `estimated_tensor_cost`
- [x] `component_metadata.jsonl`, `tile_metadata.jsonl`, `policy_traces.jsonl` 기본 생성 off
- [x] `--diagnostics-level minimal|full` 추가
- [x] minimal mode에서도 `gate_decisions.jsonl`만으로 selected tile count와 tile group count를 report에 집계
- [x] A3 이후 새 policy 완료 기준을 Minimal validation contract로 제한
- [x] detailed diagnostics는 이상 징후가 확인된 run에만 사용

### 완료 기준

- 새 ROI policy를 추가할 때 detailed metadata writer를 구현하지 않아도 baseline 비교가 가능하다.
- main report는 policy 선택에 필요한 metric만 노출한다.
- diagnostics 산출물은 필요할 때만 생성된다.
- A1/A2 결과 해석은 유지하되, 다음 stage의 실험 비용은 낮아진다.

## 10. Stage B: Small Object Policy

### 목표

small target miss를 단순 padding 문제가 아니라 small-object-specific tile/high-res path 문제로 검증한다.

### 가설

작은 객체는 full-frame downscale, global threshold, component filtering에서 쉽게 사라진다. EdgeDuet/SAHI 계열처럼 small object는 별도 tile/high-res path가 필요할 수 있다.

### 구현 항목

- [x] GT/object small/medium/large bucket 기준 확정
  - frame area 대비 GT bbox area ratio 기준: small `< 0.01`, medium `< 0.05`, large `>= 0.05`
- [x] bucket별 containment/miss report 추가
- [x] `small_object_boost` config 추가
- [x] `min_roi_width/height` config를 size bucket과 연결하지 않기로 결정
  - online gate는 GT size bucket을 알 수 없으므로 Stage B에서는 tile overlap profile로 small-object recall을 처리
  - 기존 `min_final_roi_width/height`는 component bbox tuning option으로 유지
- [x] `tile_overlap_ratio` 실험 추가
- [x] `small_object_tile_recall` profile 추가
- [x] `full_frame_lowres_context + selected_tile_highres` 후보 구현 여부 결정
  - Stage B에서는 구현하지 않고, Stage C reference detector feedback 이후 필요 시 재검토

### Stage B 판정

| Profile | 판정 | 역할 |
|---|---|---|
| `tile_mask_recall_12x12` | Keep | tile-first practical baseline |
| `small_object_tile_recall_12x12_overlap` | Keep/Tune | small-object practical candidate |
| `small_object_tile_recall` | Tune | high-recall, non-default candidate |

`small_object_tile_recall_12x12_overlap`은 ROI/tile/fallback count 증가 없이 small-object containment를 개선하므로 Stage B의 practical candidate로 유지한다. 다만 tensor cost가 증가하므로 기본 profile로 승격하지 않고, Stage D 최종 비교 후보로 넘긴다.

### Keep 기준

- small object bucket containment가 baseline보다 악화되지 않는다.
- small target missed frame count가 줄어든다.
- tile/ROI count 증가가 tensor cost budget 안에 머문다.

## 11. Stage C: Reference Detector Feedback

### 목표

Full-frame YOLO를 단순 fallback이 아니라 feedback provider로 사용한다.

### 가설

Motion-only ROI는 정지 객체, 느린 객체, sparse motion target에 취약하다. Periodic full-frame detector 결과를 feedback cache로 유지하면 component/tile candidate scoring을 보정할 수 있다.

### 구현 항목

- [x] C0 `reference_feedback.enabled` feature flag 추가
- [x] C0 full-frame detection bbox cache contract 추가
  - [x] class id/name
  - [x] confidence
  - [x] bbox
  - [x] last seen frame
  - [x] TTL 기반 age
- [x] C0 feedback bbox를 ROI 후보로 추가하는 기본 path 구현
- [x] C0 feedback metadata/report count 추가
- [x] C0 `feedback_assisted_tile_12x12_overlap` profile 추가
- [x] C1 validation runner에 reference feedback source 주입 연결
  - ROI proposal validation에서는 `--reference-feedback-source ground_truth` oracle proxy로 contract 효과 검증
  - 실제 full-frame detector output 연결은 E2E validation에서 별도 진행
- [x] C1.1 feedback candidate limit tuning
- [x] C2 actual full-frame YOLO feedback proposal smoke validation
- [x] C1 component/tile과 feedback bbox overlap scoring 추가 여부 결정
  - `duplicate_overlap_ratio` config를 추가하고 120-frame에서 검증
  - aggressive dedup은 actual YOLO feedback recall 이득을 대부분 제거하므로 default로 쓰지 않음
- [x] C1 feedback confidence decay 추가 여부 결정
  - Phase 1.1에서는 구현하지 않고 Phase 1.2 feedback tuning 후보로 보류
- [x] C1 `feedback_stale` refresh/fallback reason 추가 여부 결정
  - refresh/fallback policy는 full-frame check cost를 직접 바꾸므로 Phase 1.2 feedback tuning 후보로 보류
- [x] C1 no-ROI target risk refresh 추가 여부 결정
  - detector feedback coverage와 scene-level controller가 필요하므로 Phase 1.2 후보로 보류
- [x] C1 기존 adaptive refresh 조건은 feedback refresh reason으로 흡수
  - Phase 1.1에서는 흡수하지 않고, refresh reason redesign과 함께 Phase 1.2에서 재검토

### Keep 기준

- 정지/느린 target miss가 줄어든다.
- full-frame check count가 과도하게 증가하지 않는다.
- feedback stale / refresh reason이 report에 분리된다.

### Stage C 중간 판정

| Profile | 판정 | 역할 |
|---|---|---|
| `feedback_assisted_tile_12x12_overlap_top2` | Keep/Tune | feedback practical candidate |
| `feedback_assisted_tile_12x12_overlap` | Tune | high-recall, higher-cost feedback candidate |

`feedback_assisted_tile_12x12_overlap_top2`는 feedback 후보를 frame당 2개로 제한해 batch overflow 증가를 줄이면서 target/small-object containment 개선을 유지한다. 실제 detector output 연결 전 practical candidate로 유지한다.

C2 actual YOLO feedback smoke에서도 `feedback_assisted_tile_12x12_overlap_top2`는 Stage B practical candidate보다 target/small-object containment를 개선한다. Oracle feedback보다 효과는 낮고 tensor cost/fallback은 증가하므로, Stage C 최종 후보는 Keep/Tune 상태로 Stage D에 넘긴다.

Stage C는 Phase 1.1 범위에서 종료한다. 남은 confidence decay, stale refresh, no-ROI risk refresh는 새 policy complexity와 detector cost를 만들기 때문에 Phase 1.1 채택 조건이 아니라 Phase 1.2 feedback tuning backlog로 넘긴다.

## 12. Stage D: Final Policy Selection

### 목표

큰 online controller를 구현하지 않고, Phase 1.1에서 남길 policy와 버릴 policy를 결정한다.

### 최종 비교 후보

| Policy/Profile | 설명 |
|---|---|
| `component_bbox_balanced` | 기존 baseline |
| `hybrid_component_tile_cost` | component + tile gate cost candidate |
| `tile_mask_recall_12x12` | tile-first recall baseline |
| `small_object_tile_recall_12x12_overlap` | small object practical candidate |
| `small_object_tile_recall` | high-recall, non-default small object candidate |
| `feedback_assisted_tile_12x12_overlap_top2` | actual detector feedback practical candidate |
| `feedback_assisted_tile_12x12_overlap` | high-recall, higher-cost feedback candidate |

### Stage D 판정

| Policy/Profile | 판정 | 역할 |
|---|---|---|
| `component_bbox_balanced` | Keep | low-cost baseline |
| `hybrid_component_tile_cost` | Disable | component baseline 대비 recall 개선 없음 |
| `tile_mask_recall_12x12` | Keep | practical tile baseline |
| `small_object_tile_recall_12x12_overlap` | Keep | Phase 1.1 practical default candidate |
| `small_object_tile_recall` | Tune | high-recall, non-default small-object reference |
| `feedback_assisted_tile_12x12_overlap_top2` | Keep/Tune | strongest realistic candidate, cost tuning 필요 |
| `feedback_assisted_tile_12x12_overlap` | Tune | high-recall, higher-cost feedback reference |

`small_object_tile_recall_12x12_overlap`을 Phase 1.1의 practical default candidate로 둔다. `feedback_assisted_tile_12x12_overlap_top2`는 actual YOLO feedback에서도 개선이 있지만 ROI/tensor/fallback 비용이 증가하므로 Stage C 재검토 후 default 승격 여부를 판단한다.

### 완료 기준

- target GT containment가 baseline balanced 대비 유지되거나 개선된다.
- missed target GT count와 no-ROI target frame count가 줄거나 유지된다.
- `effective_input_area`, `tensor_batch_cost`, ROI/tile count 중 하나 이상이 개선된다.
- small object bucket에서 regression이 없다.
- fallback reason과 policy label이 report에 요약된다.
- Keep/Tune/Disable/Remove 판정이 기록된다.

## 13. 공통 검증 절차

각 stage는 동일한 절차로 검증한다.

1. PhysicalAI row 709 after 3m 또는 UA-DETRAC MVI_40204 120-frame ROI Proposal quick run 실행
2. target-aware ROI proposal report 생성
3. profile summary 생성
4. ROI/tile/batch cost summary 생성
5. ROI proposal failure visualization과 ROI debug trace 수동 검토
6. E2E Inference quick run으로 downstream compatibility 보조 확인
7. OD-VIRAT Tiny 120-frame annotated-object 보조 run 실행
8. 결과를 `docs/runs/`의 stage/topic별 run log에 기록
9. Keep/Tune/Disable/Remove 판정

## 14. Baseline Dataset

| 목적 | Baseline |
|---|---|
| 산업/창고 target-aware ROI proposal | `PhysicalAI row 709 after 3m + person + component_bbox_balanced` |
| 실사 temporal vehicle ROI proposal | `UA-DETRAC MVI_40204 + vehicle target classes + component_bbox_balanced` |
| E2E inference compatibility | 각 dataset의 동일 gate profile + `run_e2e_inference_validation.py` |

Construction Site Static Camera는 Phase 1.1 active baseline에서 제외한다.

OD-VIRAT Tiny는 annotation이 일부 객체만 포함하는 partial annotation dataset이므로 primary GT dataset으로 쓰지 않는다. 대신 annotated-object lower-bound 보조 평가와 public surveillance sample 확인에 사용한다.

## 15. Deferred to Phase 1.2

아래 항목은 Phase 1.1에서 제외하고 `docs/plan/phase1_2_deferred_research_plan.md`로 이동한다.

| 항목 | 제외 이유 |
|---|---|
| compressed-domain motion vector prototype | component/tile/hybrid baseline 판단이 먼저 |
| online profile controller | Reducto/TileClipper식 calibration data가 쌓인 뒤 가능 |
| tracking-assisted ROI 독립 구현 | feedback cache 없이 구현하면 scope가 커짐 |
| advanced ROI packing/batching | Phase 1.1에서는 batch/cost metric만 필요 |
| large merged ROI split 알고리즘 | tile policy baseline 비교 후 필요 여부 판단 |
| non-uniform tile layout optimization | A0/A1에서는 fixed grid baseline이 먼저 |
| ROI quality/QP action | ROI 생성보다 encoding quality policy에 가까움 |
| feedback confidence decay / stale refresh | actual detector feedback 후보는 Keep/Tune이나 refresh policy는 detector cost와 controller 범위를 키움 |
| no-ROI target risk refresh | scene/controller logic이 필요해 Phase 1.1 policy family 비교 범위를 넘음 |

## 16. Phase 1.1 종료 조건

### 성공 종료

- `tile_mask`, `hybrid_component_tile`, 또는 tuned `component_bbox` 중 하나가 baseline balanced 대비 target GT containment를 유지하거나 개선한다.
- `effective_input_area`, `tensor_batch_cost`, ROI/tile count, gate latency 중 하나 이상이 개선된다.
- ROI proposal failure visualization에서 반복 target miss가 줄거나 원인이 명확히 분리된다.
- small object bucket에서 regression이 없다.
- DeepStream과 겹치지 않는 frontend gate 방향성이 설명 가능하다.
- OD-VIRAT Tiny annotated-object report에서 명확한 regression이 없다.

### Phase 1.1 판정

Phase 1.1은 policy selection 관점에서 성공 종료한다.

- practical default candidate: `small_object_tile_recall_12x12_overlap`
- challenger: `feedback_assisted_tile_12x12_overlap_top2`
- low-cost baseline: `component_bbox_balanced`
- disabled candidate: `hybrid_component_tile_cost`

E2E/OD-VIRAT 보조 검증과 Jetson/DeepStream latency 계수 보정은 Phase 1.1 code closure 이후 별도 verification/backlog로 진행한다.

### 보류 종료

- ROI proposal primary 지표와 E2E/annotated-object 보조 지표 간 해석이 충돌한다.
- MacBook latency로는 판단이 어렵고 NVIDIA/Jetson 측정이 필요하다.
- tile/ROI/batch cost model의 계수가 실제 hardware와 달라 판단을 보류해야 한다.

### 제거 종료

- policy가 target containment나 small object recall을 악화시킨다.
- latency/call count/tensor cost가 개선되지 않는다.
- input area reduction 외에는 의미 있는 이득이 없다.

보류 또는 제거 판정을 받은 기능은 기본 config에서 꺼둔다. 반복 검증 가능한 evidence가 없으면 Phase 1.1 채택 후보로 두지 않는다.
