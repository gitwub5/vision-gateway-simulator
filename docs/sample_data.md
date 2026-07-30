# Sample Data Utility

## 목적

검증용 sample data 준비 절차를 코드와 문서로 남겨 팀원이 같은 입력 데이터로 실험할 수 있게 한다.

원칙:

- 공개 배포 가능한 sample만 자동 다운로드한다.
- 약관 동의, 로그인, torrent, 사내 권한이 필요한 데이터는 자동 다운로드하지 않고 준비 방법만 안내한다.
- 원본 데이터는 `data/` 아래에 저장하고 Git에는 포함하지 않는다.
- 실험 결과는 `outputs/experiments/<run_id>/` 아래에 저장한다.

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
python tools/download_sample_data.py --dataset oxford-town-centre
python tools/download_sample_data.py --dataset od-virat-tiny
python tools/download_sample_data.py --dataset internal-cctv
```

## Dataset 목록

| Dataset key | 준비 방식 | 카메라 특성 | Phase 1 용도 | 데이터 위치 | Config | 현재 권장도 | 비고 |
|---|---|---|---|---|---|---|---|
| `opencv-vtest` | 자동 다운로드 | 고정 카메라 | 초기 pipeline 검증, 보행자 ROI gate smoke test | `data/opencv_vtest/vtest.avi` | `configs/dataset.opencv_vtest.yaml` | 높음 | 작고 빠르게 실행 가능 |
| `oxford-town-centre` | 수동 준비 | 고정 CCTV | crowded pedestrian scene validation, ROI gate 한계 확인 | `data/oxford_town_centre/TownCentreXVID.mp4` | `configs/dataset.oxford_town_centre.yaml` | 높음 | 약관/미러/개인정보 이슈 확인 필요 |
| `od-virat-tiny` | 수동 준비 | 고정 감시 카메라 중심 | annotation 포함 검증 후보 | `data/od_virat_tiny/` | `configs/dataset.od_virat_tiny.yaml` | 높음 | 패키징 방식에 맞춰 config 조정 필요 |
| `internal-cctv` | 수동 준비 | 사내 고정 CCTV | 회사 환경 기준 최종 smoke/validation | `data/internal_cctv/` | `configs/dataset.internal_cctv_sample.yaml` | 높음 | 사내 보안 정책 준수 필요 |

## 권장 사용 순서

| 순서 | Dataset | 목적 |
|---|---|---|
| 1 | `opencv-vtest` | 자동 다운로드 가능한 고정 카메라 샘플로 전체 pipeline 동작 확인 |
| 2 | `oxford-town-centre` | crowded CCTV 환경에서 ROI gate 한계 확인 |
| 3 | `od-virat-tiny` | 실제 Phase 1 성능 판단과 annotation 기반 평가 확장 |
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
python experiments/run_phase1_experiment.py \
  --dataset-config <dataset_config> \
  --gate-config <gate_config> \
  --yolo-config configs/yolo.yaml \
  --experiment-name <experiment_name> \
  --limit 120
```

예시:

```bash
python experiments/run_phase1_experiment.py \
  --dataset-config configs/dataset.opencv_vtest.yaml \
  --gate-config configs/npx_gate.yaml \
  --yolo-config configs/yolo.yaml \
  --experiment-name opencv_vtest \
  --limit 120
```

출력 위치:

```text
outputs/experiments/<timestamp>_<experiment_name>/
```

## Dataset별 메모

### OpenCV vtest

- 자동 다운로드 가능
- 작은 고정 카메라 보행자 영상
- 초기 pipeline 동작 확인에 적합
- 정확한 Phase 1 성능 판단용으로는 부족할 수 있음

### Oxford Town Centre

- 고정 CCTV 기반 보행자 데이터셋
- crowded scene이라 ROI gate 한계 확인에 좋음
- 원 배포 페이지는 더 이상 안정적으로 접근되지 않을 수 있음
- Academic Torrents, Kaggle, OpenDataLab 등 미러는 약관, 로그인, torrent tooling이 필요할 수 있음
- 공개 CCTV 영상 기반 데이터셋이므로 개인정보/윤리 이슈를 검토한 뒤 사용
- Oxford 전용 gate 설정은 `configs/npx_gate.oxford.yaml`을 사용

준비 위치:

```text
data/oxford_town_centre/TownCentreXVID.mp4
data/oxford_town_centre/TownCentre-groundtruth.top
```

실행 예:

```bash
python experiments/run_phase1_experiment.py \
  --dataset-config configs/dataset.oxford_town_centre.yaml \
  --gate-config configs/npx_gate.oxford.yaml \
  --yolo-config configs/yolo.yaml \
  --experiment-name oxford_town_centre \
  --limit 120
```

### OD-VIRAT Tiny

- 실제 Phase 1 fixed-camera validation 후보
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
