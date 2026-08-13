# ROI Generator Structure

이 디렉터리는 GPU 앞단 ROI Gate를 구성하는 코드만 둔다. Phase 1.1에서는 기존 component bbox 방식을 baseline으로 유지하면서 `tile_mask`, `hybrid_component_tile` policy를 추가할 수 있도록 역할을 분리한다.

## Root Files

| Path | Role |
|---|---|
| `gate.py` | `FramePacket`을 받아 signal 생성, policy 실행, budget 판단, `GateDecision` 생성을 조율하는 orchestrator |
| `config.py` | ROI generator 설정과 YAML loading |
| `contract.py` | downstream과 공유할 gate decision contract |
| `metadata.py` | `GateDecision`을 ROI/frame metadata JSONL record로 변환 |
| `budget.py` | ROI count/area budget과 full-frame fallback 판단 |
| `trace.py` | debug, observability, policy trace record |
| `temporal_hold.py` | motion이 사라진 직후 ROI를 짧게 유지하는 hold logic |
| `roi_generator.py` | 기존 import 호환을 위한 shim. 새 코드는 `candidates/`를 직접 import |
| `event_encoder.py`, `motion_detector.py`, `preprocess.py` | 기존 import 호환을 위한 shim. 새 코드는 `signals/`를 직접 import |

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

추후 `tile_mask` 구현 시 `candidates/tiles.py`를 추가한다.

## `policies/`

후보를 실제 ROI decision 후보로 선택하는 policy를 둔다.

| Path | Role |
|---|---|
| `policies/base.py` | policy interface |
| `policies/component_bbox.py` | 기존 방식. `component_bbox` baseline |

추후 추가 예정:

- `policies/tile_mask.py`
- `policies/hybrid_component_tile.py`

## Dependency Direction

권장 의존 방향은 아래와 같다.

```text
gate.py
  -> signals/
  -> policies/
  -> budget.py
  -> contract.py / metadata.py / trace.py

policies/
  -> candidates/
  -> signals/ types only
```

`signals/`와 `candidates/`는 `gate.py`나 `experiments/`를 import하지 않는다.

## Removal Rule

새 policy를 제거할 때는 해당 `policies/*.py`, 관련 config, 관련 tests만 제거하면 된다. `gate.py`는 policy interface만 호출해야 하며, 특정 policy의 세부 threshold나 후보 생성 규칙을 직접 알면 안 된다.
