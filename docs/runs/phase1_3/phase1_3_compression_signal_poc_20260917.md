# Phase 1.3-F Compression Signal Prototype

Date: 2026-09-17

## Scope

Compression Signal Prototype은 pixel decode 이후의 motion/edge/tile 신호가 아니라, encoded stream에서 얻을 수 있는 frame metadata를 ROI Gate 앞단 신호로 쓸 수 있는지 확인하는 feasibility track이다.

검토한 신호:

- frame type: I/P/B frame, key frame
- packet size / bitrate variation
- GOP/keyframe interval
- 향후 확장 후보: H.264/H.265 motion vector, residual energy

## Implementation

추가한 구현:

- `evaluation/reports/compression_signal.py`
- `experiments/phase1_3/run_compression_signal_poc.py`
- `experiments/phase1_3/run_compression_signal_matrix.py`
- `tests/evaluation_tests/test_compression_signal_report.py`

runner는 dataset이 video stream이면 `ffprobe`로 frame-level metadata를 추출하고, image sequence이면 encoded stream metadata가 보존되지 않았다고 기록한다.

## Matrix

Matrix output:

- `outputs/compression_signal_matrices/phase1_3_compression_signal_20260917_105124`

| Dataset | Type | Status | Reason |
|---|---|---|---|
| `phase1_3_traffic_ua_detrac_mvi_39361` | `image_sequence` | `unavailable` | dataset is an image sequence; encoded stream metadata is not preserved |
| `phase1_3_logistics_physicalai_row0709_after3m` | `video` | `unavailable` | ffprobe is not installed; cannot inspect encoded frame metadata locally |
| `phase1_3_surveillance_mot17_04` | `image_sequence` | `unavailable` | dataset is an image sequence; encoded stream metadata is not preserved |
| `phase1_3_retail_mall_dataset` | `image_sequence` | `unavailable` | dataset is an image sequence; encoded stream metadata is not preserved |
| `phase1_3_general_visdrone_uav0000086` | `image_sequence` | `unavailable` | dataset is an image sequence; encoded stream metadata is not preserved |

## Interpretation

현재 Phase 1.3 공식 dataset 대부분은 decoded image sequence 형태다. 이 경우 packet size, frame type, GOP structure, motion vector 같은 compressed-domain signal은 이미 사라져 있으므로 현재 artifact만으로는 평가할 수 없다.

PhysicalAI는 video file이므로 압축 신호 검증이 가능한 후보지만, 현재 로컬 환경에는 `ffprobe`/`ffmpeg`가 없어 metadata 추출을 수행하지 못했다.

따라서 1.3-F의 결론은 후보 기술의 성능 판정이 아니라 적용 조건 판정이다.

- 현재 5-domain ROI matrix에서는 compression signal을 정량 비교 후보로 쓰기 어렵다.
- encoded RTSP/video source와 metadata 접근 도구가 있는 runtime/integration 환경에서 다시 평가해야 한다.
- 실제 DeepStream/GStreamer pipeline에서는 decoder/parser stage에서 metadata 접근 가능성을 별도 확인해야 한다.

## Decision

Compression signal은 Phase 1.3의 immediate ROI candidate에서 제외하고, Phase 2 이후 integration/runtime track 후보로 유지한다.

다음 조건이 만족되면 재실험한다.

- `ffprobe`/`ffmpeg` 또는 GStreamer/DeepStream 기반 metadata extractor 사용 가능
- image sequence가 아닌 encoded video/RTSP sample 확보
- frame type, packet size, motion vector 또는 residual energy를 frame index와 annotation에 정렬 가능

## Verification

- `python -m unittest tests.evaluation_tests.test_compression_signal_report`
- `python -m py_compile evaluation/reports/compression_signal.py experiments/phase1_3/run_compression_signal_poc.py experiments/phase1_3/run_compression_signal_matrix.py tests/evaluation_tests/test_compression_signal_report.py`
