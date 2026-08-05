# Sample Data Utility

## 목적

검증용 sample data 준비 절차를 코드와 문서로 남겨 팀원이 같은 입력 데이터로 실험할 수 있게 한다.

원칙:

- 공개 배포 가능한 sample만 자동 다운로드한다.
- 약관 동의, 로그인, torrent, 사내 권한이 필요한 데이터는 자동 다운로드하지 않고 준비 방법만 안내한다.
- 원본 데이터는 `data/` 아래에 저장하고 Git에는 포함하지 않는다.
- 실험 결과는 `outputs/e2e_inference_validation/<run_id>/` 아래에 저장한다.

## 사용법

지원 dataset 목록 확인:

```bash
python tools/download_sample_data.py --list
```

자동 다운로드:

```bash
python tools/download_sample_data.py --dataset opencv-vtest
```

이미 받은 파일을 다시 받고 싶으면:

```bash
python tools/download_sample_data.py --dataset opencv-vtest --force
```

수동 준비 dataset 안내 확인:

```bash
python tools/download_sample_data.py --dataset od-virat-tiny
python tools/download_sample_data.py --dataset ua-detrac
python tools/download_sample_data.py --dataset internal-cctv
```

## Dataset 목록

| Dataset key | 준비 방식 | 카메라 특성 | Phase 1 용도 | 데이터 위치 | Config | 현재 권장도 | 비고 |
|---|---|---|---|---|---|---|---|
| `opencv-vtest` | 자동 다운로드 | 고정 카메라 | 초기 pipeline 검증, 보행자 ROI gate smoke test | `data/opencv_vtest/vtest.avi` | `configs/dataset.opencv_vtest.yaml` | 높음 | 작고 빠르게 실행 가능 |
| `od-virat-tiny` | 수동 준비 | 고정 감시 카메라 중심 | partial annotation 보조 검증 | `data/od_virat_tiny/` | `configs/dataset.od_virat_tiny.yaml` | 중간 | exhaustive GT가 아니므로 hard criterion 제외 |
| `ua-detrac` | 수동 준비 | 고정/준고정 교통 CCTV | ROI proposal primary validation | `data/ua_detrac/` | `configs/dataset.ua_detrac_mvi_39031.yaml` | 높음 | 연속 프레임, vehicle bbox GT, YOLOv8 class 적합 |
| `internal-cctv` | 수동 준비 | 사내 고정 CCTV | 회사 환경 기준 최종 smoke/validation | `data/internal_cctv/` | `configs/dataset.internal_cctv_sample.yaml` | 높음 | 사내 보안 정책 준수 필요 |

## 권장 사용 순서

| 순서 | Dataset | 목적 |
|---|---|---|
| 1 | `opencv-vtest` | 자동 다운로드 가능한 고정 카메라 샘플로 전체 pipeline 동작 확인 |
| 2 | `ua-detrac` | 연속 프레임과 bbox GT가 있는 primary ROI proposal validation |
| 3 | `od-virat-tiny` | annotation 기반 보조 평가와 public validation |
| 4 | `internal-cctv` | 사내 적용 환경 기준 최종 검증 |

## 공통 실행 방법

Dataset loader 확인:

```bash
python experiments/inspect_dataset_stream.py \
  --config <dataset_config> \
  --limit 3
```

전체 Phase 1 실험 실행:

```bash
python experiments/run_e2e_inference_validation.py \
  --dataset-config <dataset_config> \
  --gate-config <gate_config> \
  --yolo-config configs/yolo.yaml \
  --experiment-name <experiment_name> \
  --limit 120
```

예시:

```bash
python experiments/run_e2e_inference_validation.py \
  --dataset-config configs/dataset.opencv_vtest.yaml \
  --gate-config configs/npx_gate.yaml \
  --yolo-config configs/yolo.yaml \
  --experiment-name opencv_vtest \
  --limit 120
```

출력 위치:

```text
outputs/e2e_inference_validation/<timestamp>_<experiment_name>/
```

## Dataset별 메모

### OpenCV vtest

- 자동 다운로드 가능
- 작은 고정 카메라 보행자 영상
- 초기 pipeline 동작 확인에 적합
- 정확한 Phase 1 성능 판단용으로는 부족할 수 있음

### Removed: Construction Site Static Camera

Construction Site Static Camera는 Phase 1.1 후보로 검토했지만 active dataset에서 제외했다.

제외 이유:

- 단일 연속 CCTV 영상이 아니라 여러 static scene image가 섞여 있어 temporal ROI policy 검증이 왜곡된다.
- `IMG259`-`IMG457` 구간 high-res gate 검증에서도 official config는 거의 모든 frame에서 full-frame fallback으로 빠졌다.
- fallback을 끈 diagnostic run에서는 ROI가 거의 전체 프레임을 덮어 ROI proposal 품질 판단에 부적합했다.
- YOLOv8 COCO 기본 모델과 class/domain mismatch가 크다.

과거 실험 결과는 삭제하지 않고 `outputs/` 아래에 보존한다.

```text
outputs/experiments/construction_static_0259_0457_balanced_20260805/
outputs/roi_proposal_validation/construction_static_0259_0457_balanced_highres_20260805/
```

### UA-DETRAC

- Phase 1.1 ROI Proposal Validation의 primary public temporal GT dataset
- 고정/준고정 교통 CCTV에서 촬영된 연속 image sequence
- vehicle bbox annotation이 frame 단위 XML로 제공된다.
- YOLOv8 COCO 기본 class와 잘 맞는다.
  - `car` -> `car`
  - `bus` -> `bus`
  - `van` -> `car`
  - `others` -> `truck`
- 산업현장 도메인은 아니지만, ROI 생성/추적/fallback policy를 GT 기준으로 검증하기에 적합하다.

수동 다운로드:

```text
https://detrac-db.rit.albany.edu/Data/DETRAC-train-data.zip
https://detrac-db.rit.albany.edu/Data/DETRAC-Test-Annotations-XML.zip
```

기본 준비 위치:

```text
data/ua_detrac/DETRAC-Images/DETRAC-Images/MVI_39031/
data/ua_detrac/DETRAC-Test-Annotations-XML/DETRAC-Test-Annotations-XML/MVI_39031.xml
```

기본 quick config:

```text
configs/dataset.ua_detrac_mvi_39031.yaml
```

실행 예:

```bash
python experiments/run_e2e_inference_validation.py \
  --dataset-config configs/dataset.ua_detrac_mvi_39031.yaml \
  --gate-config configs/npx_gate.profile_balanced.yaml \
  --yolo-config configs/yolo.yaml \
  --experiment-name ua_detrac_mvi_39031_balanced \
  --limit 120
```

### OD-VIRAT Tiny

- partial annotation 보조 검증 후보
- 데이터 사용 약관과 접근 권한을 먼저 확인
- 공식 dataset 안내와 repository를 확인한 뒤 수동 준비
  - https://iscaaslab.com/datasets/
  - https://github.com/hayatkhan8660-maker/OD-VIRAT
  - https://github.com/hayatkhan8660-maker/OD-VIRAT/blob/main/DATA.md
  - OD-VIRAT Tiny Google Drive folder: https://drive.google.com/drive/folders/1MqVKIfS_RimUVVin1UHk_uwPmex5vid7?usp=drive_link
- 현재 placeholder config는 `configs/dataset.od_virat_tiny.yaml`
- Google Drive에서 받은 Tiny zip 파일들을 `data/od_virat_tiny/` 아래에 그대로 해제한다.
- 해제 후 package 폴더명은 upstream 그대로 둔다. 현재 config는 기본적으로 `data/od_virat_tiny/data/test`와 `data/od_virat_tiny/json_anntations/test_annotations.json`을 사용한다.
- annotation loader를 확장하면 GT 기반 recall/mAP 평가로 이어갈 수 있음

### Internal CCTV

- 사내 적용 환경에 가장 가까운 최종 검증 후보
- raw video와 annotation은 Git에 포함하지 않음
- 사내 보안 정책에 맞춰 접근 권한과 저장 위치를 관리
