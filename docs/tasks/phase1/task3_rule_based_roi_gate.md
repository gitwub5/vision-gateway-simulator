# Task 3. Rule-based ROI Gate Emulator 구현 정리

## 목적

Task 3의 목적은 `FramePacket` 입력을 받아 GPU에 전달할 ROI 또는 full-frame trigger 결정을 만드는 rule-based Vision Frontend Gate를 구현하는 것이다.

Phase 1에서는 실제 NPX 하드웨어나 SNN을 사용하지 않고, 다음 흐름을 소프트웨어로 에뮬레이션한다.

```text
FramePacket
    ↓
gray 변환
    ↓
analysis frame resize
    ↓
frame difference / event-like map
    ↓
motion filtering
    ↓
connected component ROI
    ↓
ROI merge / margin / original coordinate restore
    ↓
temporal hold / periodic full-frame / fallback policy
    ↓
GateDecision
```

## 변경한 주요 파일

- `npx_emulator/gate.py`
- `npx_emulator/__init__.py`
- `npx_emulator/temporal_hold.py`
- `requirements.txt`
- `tests/test_npx_gate.py`
- `docs/plan/phase1_implementation_plan.md`
- `README.md`

## 핵심 설계 결정

### `RuleBasedNpxGate`

Task 3의 중심 클래스다.

```python
gate = RuleBasedNpxGate(config)
decision = gate.process(frame_packet)
```

`process()`는 한 frame을 받아 `GateDecision`을 반환한다.

`GateDecision`에는 다음 정보가 들어간다.

- `trigger_type`
- `rois`
- `should_run_full_frame`
- `original_frame_size`
- `analysis_frame_size`
- `gate_latency_ms`
- `event_maps`

이 구조를 둔 이유는 Task 4 ROI metadata 저장, Task 5/6 YOLO inference, Task 7 workload/latency evaluation이 같은 gate 결과를 공유할 수 있게 하기 위해서다.

### 첫 frame은 full-frame trigger

Frame difference는 이전 frame이 있어야 계산할 수 있다. 따라서 첫 frame은 ROI를 생성하지 않고 `FULL_FRAME` trigger로 보낸다.

```text
frame_id = 0 → full-frame check
```

이 결정은 초기 detection baseline 확보와 정지 객체 누락 방지에도 유리하다.

### ON/OFF event-like map 분리

`event_encoder.py`의 `encode_event_maps()`는 `on_event`, `off_event`, `motion_map`을 함께 만든다.

Phase 1에서는 `motion_map`만 사용하지만, Phase 2의 SNN 입력이 `ON/OFF event-like tensor`가 될 예정이므로 이 구조를 유지한다.

### ROI 생성과 좌표 변환

ROI는 analysis frame에서 먼저 생성한 뒤 원본 frame 좌표로 변환한다.

```text
analysis ROI
    ↓
scale_roi_to_original()
    ↓
add_margin_and_clip()
    ↓
original frame ROI
```

이렇게 한 이유는 저해상도 analysis frame에서 빠르게 움직임 후보를 찾고, 실제 crop은 원본 frame에서 수행하기 위해서다.

### Temporal hold

움직임이 잠깐 사라져도 ROI를 일정 frame 동안 유지한다.

사람이나 차량이 잠깐 멈추면 frame difference에서는 motion이 사라질 수 있기 때문에, Task 3에서는 `TemporalHold`를 gate orchestration에 연결했다.

### Periodic full-frame check

`full_frame_interval`마다 full-frame trigger를 발생시킨다.

이 정책은 움직임 기반 ROI만으로 놓칠 수 있는 정지 객체를 보완하기 위한 것이다.

### Full-frame fallback

ROI가 너무 많거나 전체 ROI 면적이 너무 크면 ROI crop inference가 full-frame inference보다 비효율적일 수 있다.

그래서 다음 조건에서 `FALLBACK_FULL_FRAME`을 반환한다.

- ROI 개수 > `max_roi_per_frame`
- 전체 ROI 면적 비율 > `max_total_roi_area_ratio`

## 실행 방법

Task 3는 아직 실제 dataset end-to-end 실행 script를 완성하지 않는다. 실제 frame stream과 연결하는 orchestration은 Task 4 이후 `run_rule_roi_baseline.py`에서 확장한다.

현재는 Python API 기준으로 다음처럼 사용할 수 있다.

```python
from npx_emulator import NpxGateConfig, RuleBasedNpxGate

gate = RuleBasedNpxGate(NpxGateConfig())

for packet in stream:
    decision = gate.process(packet)
    print(decision.trigger_type, decision.rois)
```

## 검증 방법

```bash
python3 -m compileall common data_loader npx_emulator experiments tests
python3 -m unittest tests.test_npx_gate
```

검증 항목:

- 첫 frame이 full-frame trigger를 내는지 확인
- motion ROI가 ROI trigger를 내는지 확인
- motion이 사라졌을 때 temporal hold가 동작하는지 확인
- periodic full-frame check가 동작하는지 확인
- ROI 개수/면적 기준 fallback이 동작하는지 확인

현재 로컬 환경에는 OpenCV/NumPy가 설치되어 있지 않을 수 있으므로, unit test는 gate 내부 helper를 monkeypatch하여 정책과 orchestration을 검증한다. 실제 video/image frame 처리에는 `requirements.txt` 설치가 필요하다.

## 다음 Task와의 연결

Task 4에서는 `GateDecision` 결과를 `ROIMetadata`로 변환하고 `outputs/roi_metadata/rule_roi.jsonl`에 저장한다.

Task 5/6에서 Owner B는 이 결과를 사용해 full-frame YOLO와 ROI YOLO inference를 연결한다.

## 알려진 제한사항

- 실제 OpenCV/NumPy 기반 frame processing은 의존성 설치 후 sample video/image로 추가 검증이 필요하다.
- ROI merge는 bounding box 간 거리 기반 단순 병합이다.
- Temporal hold는 현재 frame의 ROI가 발생하면 hold 상태를 새 ROI 목록으로 갱신하는 단순 정책이다.
- Tracking ID나 객체별 hold 관리는 Phase 1 범위에서 제외한다.
