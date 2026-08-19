# ROI Generator Structure

이 디렉터리는 GPU 앞단 ROI Gate를 구성하는 코드만 둔다. Phase 1.1 A1부터는 런타임 ROI 생성 경로와 평가/관측용 artifact 생성 경로를 분리해서 본다.

## Top-Level Rule

| Path | Role |
|---|---|
| `__init__.py` | public package export. 실험 runner는 가능하면 여기서 필요한 API를 import한다 |
| `core/` | 실제 `FramePacket -> GateDecision` 실행 경로 |
| `signals/` | frame에서 cheap signal을 만드는 저수준 전처리 |
| `candidates/` | signal을 component/tile 후보로 바꾸는 primitive |
| `policies/` | 후보 중 어떤 ROI를 선택할지 결정하는 policy |
| `observability/` | trace, metadata, debug/report 입력 record 생성 |

## `core/`

실제 ROI gate runtime이다. downstream으로 넘길 decision을 만들거나 runtime budget/fallback을 판단하는 파일만 둔다.

| Path | Role |
|---|---|
| `core/gate.py` | `FramePacket`을 받아 signal 생성, policy 실행, budget 판단, `GateDecision` 생성을 조율하는 orchestrator |
| `core/config.py` | ROI generator 설정과 YAML loading |
| `core/contract.py` | downstream과 공유할 gate decision contract |
| `core/budget.py` | ROI count/area budget과 full-frame fallback 판단 |
| `core/decision_reasons.py` | decision/fallback reason 상수 |
| `core/temporal_hold.py` | motion이 사라진 직후 ROI를 짧게 유지하는 hold logic |

`core/`는 evaluation report를 직접 만들지 않는다. 필요한 숫자는 `GateDecision`과 trace에 담아서 넘긴다.

## `signals/`

저수준 frame signal을 만든다.

| Path | Role |
|---|---|
| `signals/preprocess.py` | frame을 grayscale/analysis size로 변환 |
| `signals/event_encoder.py` | frame difference 기반 ON/OFF/motion map 생성 |
| `signals/motion_detector.py` | motion map morphology filtering |

이 폴더는 policy 판단을 하지 않는다. Cheap signal을 만드는 단계까지만 담당한다.

## `candidates/`

Signal을 ROI/tile 후보로 변환하는 primitive를 둔다.

| Path | Role |
|---|---|
| `candidates/components.py` | connected component 후보, merge, margin/clip, original-frame scale 변환 |
| `candidates/tiles.py` | fixed grid tile 후보, per-tile motion density, selected tile count 계산 |

이 폴더는 최종 policy를 고르지 않는다. 후보 생성과 후보별 feature 계산까지만 담당한다.

## `policies/`

후보를 실제 ROI decision 후보로 선택하는 policy를 둔다.

| Path | Role |
|---|---|
| `policies/base.py` | policy interface |
| `policies/component_bbox.py` | 기존 방식. `component_bbox` baseline |

A1 추가 예정:

- `policies/tile_mask.py`
- `policies/hybrid_component_tile.py`

## `observability/`

검증, 평가, debugging에 필요한 record를 만든다. 실제 ROI 생성 정책은 여기에 두지 않는다.

| Path | Role |
|---|---|
| `observability/trace.py` | `RoiGenerationTrace`, component/tile/policy trace dataclass, debug snapshot |
| `observability/metadata.py` | `GateDecision`과 trace를 JSONL metadata record로 변환하고 writer 제공 |

## Dependency Direction

권장 의존 방향은 아래와 같다.

```text
core/gate.py
  -> signals/
  -> policies/
  -> core/budget.py
  -> core/contract.py
  -> observability/trace.py

policies/
  -> candidates/
  -> signals/ types only
  -> observability/trace.py

observability/
  -> core/contract.py
  -> common metadata types
```

`signals/`와 `candidates/`는 `core/gate.py`나 `experiments/`를 import하지 않는다. `observability/`는 record 변환만 담당하고 runtime policy를 호출하지 않는다.

## Removal Rule

새 policy를 제거할 때는 해당 `policies/*.py`, 관련 config, 관련 tests만 제거하면 된다. `core/gate.py`는 policy interface만 호출해야 하며, 특정 policy의 세부 threshold나 후보 생성 규칙을 직접 알면 안 된다.
