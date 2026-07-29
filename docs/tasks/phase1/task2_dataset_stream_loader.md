# Task 2. Dataset Stream Loader 구현 정리

## 목적

Task 2의 목적은 Phase 1 실험에서 사용할 입력 데이터를 공통 형태로 추상화하는 것이다.

Video 파일을 사용하든 image sequence를 사용하든, 이후 단계인 ROI Gate, YOLO inference, evaluation은 입력 형식을 직접 알 필요 없이 `FramePacket`만 받도록 만든다.

```text
video / image sequence
        ↓
DatasetStream
        ↓
FramePacket
        ↓
ROI Gate / YOLO / Evaluation
```

## 핵심 데이터 구조

공통 입력 단위는 `common/schemas.py`의 `FramePacket`이다.

```python
FramePacket(
    camera_id="cam_01",
    frame_id=0,
    timestamp=0.0,
    frame=frame,
    original_size=FrameSize(width=1920, height=1080),
)
```

필드 역할:

- `camera_id`: 현재 frame이 어떤 카메라 stream에서 왔는지 식별한다.
- `frame_id`: stream 내 frame 번호다.
- `timestamp`: frame 시간 정보다.
- `frame`: OpenCV가 읽은 실제 image array다.
- `original_size`: 원본 frame 크기다. ROI 좌표 복원과 workload 계산에 사용한다.

이 구조를 기준으로 이후 Task는 입력 source가 video인지 image folder인지 신경 쓰지 않고 구현할 수 있다.

## 구현 파일

주요 구현 파일:

- `data_loader/dataset_stream.py`
- `data_loader/__init__.py`
- `configs/dataset.yaml`
- `experiments/inspect_dataset_stream.py`
- `tests/test_dataset_stream.py`
- `requirements.txt`

## 구현 내용

### `VideoFrameStream`

OpenCV `VideoCapture`를 사용해 video frame을 순차적으로 읽고 `FramePacket`으로 변환한다.

지원 옵션:

- `camera_id`
- `fps_override`
- `frame_limit`
- `start_frame`

이 옵션을 둔 이유는 전체 영상을 매번 처리하지 않고, 일부 구간만 빠르게 반복 실험할 수 있게 하기 위해서다.

### `ImageSequenceStream`

이미지 폴더에서 `.jpg`, `.jpeg`, `.png`, `.bmp` 파일을 정렬된 순서로 읽고 `FramePacket`으로 변환한다.

VIRAT/OD-VIRAT처럼 frame dump 형태로 실험하거나, 디버깅용 sample frame을 넣어 확인할 때 사용할 수 있다.

### `DatasetConfig`

`configs/dataset.yaml`의 내용을 Python 객체로 옮기는 설정 구조다.

```yaml
dataset:
  type: video
  input_path: data/sample.mp4
  camera_id: cam_01
  fps_override: null
  frame_limit: null
  start_frame: 0
```

image sequence를 사용할 때는 다음처럼 바꿀 수 있다.

```yaml
dataset:
  type: image_sequence
  input_path: data/frames/cam_01
  camera_id: cam_01
  fps_override: 30
  frame_limit: 100
  start_frame: 0
```

### `create_dataset_stream()`

config를 보고 적절한 stream 구현체를 생성한다.

```python
stream = create_dataset_stream(config)
```

이 factory를 둔 이유는 experiment script가 `VideoFrameStream` 또는 `ImageSequenceStream`을 직접 선택하지 않게 하기 위해서다. 실행 코드는 유지하고 config만 바꿔서 입력 방식을 전환할 수 있다.

### `load_dataset_config()`

YAML config 파일을 읽어서 `DatasetConfig`로 변환한다.

```python
config = load_dataset_config("configs/dataset.yaml")
stream = create_dataset_stream(config)
```

## Inspect script

실제 데이터셋을 넣기 전에 loader가 정상적으로 `FramePacket`을 생성하는지 확인하기 위해 `experiments/inspect_dataset_stream.py`를 추가했다.

사용 예:

```bash
python experiments/inspect_dataset_stream.py --config configs/dataset.yaml --limit 5
```

출력 예:

```text
{'camera_id': 'cam_01', 'frame_id': 0, 'timestamp': 0.0, 'original_size': [1920, 1080]}
```

이 출력이 정상이어야 Task 3의 ROI Gate 입력으로 사용할 수 있다.

## 의존성

Task 2부터 실제 dataset loading에는 다음 dependency가 필요하다.

```text
opencv-python
PyYAML
```

가상환경 사용을 권장한다.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

현재 unit test는 실제 OpenCV 설치 없이도 loader 로직을 검증할 수 있도록 fake `cv2` 모듈을 사용한다. 실제 video/image를 읽는 실행에는 OpenCV가 필요하다.

## 검증 방법

Task 2 구현 검증:

```bash
python3 -m compileall common data_loader experiments tests
python3 -m unittest tests.test_dataset_stream
```

검증 항목:

- video stream이 `FramePacket`을 생성하는지 확인
- image sequence stream이 image 확장자만 읽는지 확인
- config 기반 factory가 올바른 stream type을 생성하는지 확인

## 후속 Task와의 연결

Task 3에서는 `DatasetStream`에서 생성한 `FramePacket`을 입력으로 받아 rule-based ROI Gate를 구현한다.

Task 5 이후 Owner B는 같은 `FramePacket` 구조를 사용해 full-frame YOLO baseline과 ROI YOLO pipeline을 연결할 수 있다.

핵심 의도는 다음과 같다.

```text
입력 형식(video/images)을 추상화한다
→ 모든 후속 단계는 FramePacket만 받는다
→ config만 바꿔 실험 입력을 전환한다
→ 실제 데이터 없이도 loader logic은 test한다
```
