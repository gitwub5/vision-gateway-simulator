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
python tools/download_sample_data.py --dataset construction-site-static-camera
python tools/download_sample_data.py --dataset od-virat-tiny
python tools/download_sample_data.py --dataset internal-cctv
```

## Dataset 목록

| Dataset key | 준비 방식 | 카메라 특성 | Phase 1 용도 | 데이터 위치 | Config | 현재 권장도 | 비고 |
|---|---|---|---|---|---|---|---|
| `opencv-vtest` | 자동 다운로드 | 고정 카메라 | 초기 pipeline 검증, 보행자 ROI gate smoke test | `data/opencv_vtest/vtest.avi` | `configs/dataset.opencv_vtest.yaml` | 높음 | 작고 빠르게 실행 가능 |
| `construction-site-static-camera` | 수동 준비 | 고정 CCTV/static camera | 산업 관제형 사람/장비 ROI gate validation | `data/construction_site_static_camera/` | `configs/dataset.construction_site_static_camera.yaml` | 높음 | 4개 static camera, Person/장비/차량 class |
| `od-virat-tiny` | 수동 준비 | 고정 감시 카메라 중심 | annotation 포함 검증 후보 | `data/od_virat_tiny/` | `configs/dataset.od_virat_tiny.yaml` | 높음 | 패키징 방식에 맞춰 config 조정 필요 |
| `internal-cctv` | 수동 준비 | 사내 고정 CCTV | 회사 환경 기준 최종 smoke/validation | `data/internal_cctv/` | `configs/dataset.internal_cctv_sample.yaml` | 높음 | 사내 보안 정책 준수 필요 |

## 권장 사용 순서

| 순서 | Dataset | 목적 |
|---|---|---|
| 1 | `opencv-vtest` | 자동 다운로드 가능한 고정 카메라 샘플로 전체 pipeline 동작 확인 |
| 2 | `construction-site-static-camera` | 산업 관제형 고정 camera 환경에서 ROI gate 검증 |
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

### Construction Site Static Camera

- Phase 1.1 public validation의 기본 후보
- 4개 static camera에서 추출된 construction site image dataset
- `Person`, `Dump_truck`, `Excavator`, `Concrete_mixer_truck`, `Skid_steer`, `Tower_crane`, `Truck_crane`, `Truck` class를 포함
- 스마트팩토리와 완전히 같은 도메인은 아니지만, “고정 관제 + 작업자/장비/차량” 조건에 가깝다.
- 데이터 출처와 약관을 확인한 뒤 수동 준비
  - https://doi.org/10.26439/ulima.datasets.13359
  - dataset paper: https://pmc.ncbi.nlm.nih.gov/articles/PMC8933580/
- annotation txt 원본 포맷 확인 전까지 기본 config의 `annotations.enabled`는 `false`로 둔다.
- GT report를 hard criterion으로 쓰기 전에 visible `Person`/장비/차량이 빠짐없이 표기됐는지 샘플 visual QA로 확인한다.
- 표기 누락이 있으면 `false_roi_rate`, precision, false positive count는 보조/주의 지표로만 사용한다.

준비 위치:

```text
data/construction_site_static_camera/1-250/
data/construction_site_static_camera/251-500/
data/construction_site_static_camera/501-800/
data/construction_site_static_camera/801-1049/
```

각 폴더에는 이미지와 같은 stem의 YOLO txt label이 함께 있다. 이 dataset은 단일 연속 영상이 아니라 여러 static-camera scene이 묶인 image set이다. ROI gate의 temporal behavior를 검증할 때는 전체 폴더를 한 번에 돌리지 말고, 사람이 확인한 연속 scene 구간만 `start_frame`과 `frame_limit`으로 잘라서 실행한다.

현재 기본 config는 `251-500` 폴더에서 `IMG259`-`IMG457` 구간만 사용한다. 이 구간은 사용자가 공사현장 장면으로 수동 확인한 기본 validation segment다.

주의:

- 이 dataset은 GT loader와 failure visualization 검증에는 유용하다.
- 장면이 바뀌는 경계를 넘겨 실행하면 temporal hold, adaptive refresh, tracking ROI 지표가 왜곡된다.
- motion-based ROI gate 성능 판단에는 실제 연속 motion이 있는 segment인지 먼저 visual QA가 필요하다.
- ROI가 0개인 segment는 pipeline/GT smoke로만 기록하고 ROI policy 품질 판단에서 제외한다.

실행 예:

```bash
python experiments/run_phase1_experiment.py \
  --dataset-config configs/dataset.construction_site_static_camera.yaml \
  --gate-config configs/npx_gate.profile_balanced.yaml \
  --yolo-config configs/yolo.yaml \
  --experiment-name construction_static_balanced \
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
