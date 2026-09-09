# Phase 1.3 Scene/Domain ROI Gate PoC Plan

이 문서는 Phase 1.3에서 진행할 ROI Gate PoC 계획을 정리한다.

Phase 1.3의 목적은 특정 ROI policy를 하나 더 튜닝하는 것이 아니다. Phase 1, 1.1, 1.2에서 확인한 motion/tile 기반 한계를 바탕으로, 기존 CCTV와 GPU 서버를 사용하는 조건에서 어떤 scene/domain에 어떤 ROI Gate 방식이 맞는지 검증한다.

## 1. 핵심 질문

Phase 1.3의 핵심 질문은 다음이다.

```text
기존 CCTV/RGB 영상 환경에서 ROI를 충분히 정확하고 작게 생성해
GPU detector에 넘길 수 있는가?
```

이를 아래 질문으로 나눠 검증한다.

- motion map 기반 ROI Gate가 어느 scene condition에서 유효한가?
- motion map이 불안정한 scene에서는 어떤 보조 signal 또는 guard가 필요한가?
- tile 기반 contract를 유지하는 것이 좋은가, contour/heatmap/objectness 등 다른 ROI 표현이 나은가?
- 도메인별로 다른 gate architecture가 필요한가, 아니면 공통 적용 가능한 기술 조합이 있는가?
- ROI proposal 품질이 실제 GPU workload 절감으로 이어질 가능성이 있는가?

## 2. 전제

고정 전제:

- 기존 CCTV/camera를 교체하지 않는다.
- 기존 GPU 서버 기반 detector pipeline을 활용한다.
- ROI Gate의 1순위 목표는 GPU model에 넘길 입력 영역을 잘 고르는 것이다.
- SNN은 별도 roadmap phase로 고정하지 않는다. 필요하면 ROI signal 후보 또는 hardware-oriented 후보 중 하나로만 다룬다.

현재 기준선:

| 기준 | Profile |
|---|---|
| 단순 tile baseline | `tile_mask_recall_12x12` |
| Phase 1.1 practical candidate | `small_object_tile_recall_12x12_overlap` |
| Phase 1.2 practical candidate | `rescue_with_budget_cap` |
| High-recall feedback candidate | `feedback_confidence_decay` |

## 3. Phase 1.2에서 넘어온 문제

Phase 1.2 결과상 tile 기반 개선은 의미가 있었지만, motion 기반 신호 자체의 한계는 남아 있다.

남은 문제:

- 조도 변화, 그림자, 반사, flicker가 motion으로 잡힌다.
- 카메라 흔들림과 압축 노이즈가 global motion처럼 번진다.
- 정지/저속/small far-field target은 signal missing이 발생한다.
- threshold를 올리면 false ROI는 줄지만 containment가 깨진다.
- threshold를 낮추면 recall은 살지만 active area, tile count, fallback이 증가한다.
- dense scene에서는 ROI가 full-frame에 가까워져 GPU 절감 효과가 약해진다.

따라서 Phase 1.3은 tile profile 추가 튜닝보다 signal validity와 scene/domain fit 검증을 먼저 한다.

## 4. Scene/Domain Coverage

Phase 1.3의 도메인은 GPU/DeepStream 기반 video analytics 수요가 크고, 기존 CCTV/GPU 서버 환경을 그대로 활용할 가능성이 높은 분야를 우선한다.

1차 vertical:

| Vertical | 선정 이유 |
|---|---|
| Traffic / parking | 다중 CCTV, 24/7 처리, vehicle/person detection, incident monitoring, 조도/날씨 변화가 큼 |
| Surveillance / security | 기존 CCTV가 많고 intrusion, loitering, crowd, person tracking 등 실시간 관제 수요가 큼 |
| Logistics / smart factory | warehouse, factory, worker safety, forklift/robot/equipment monitoring, 반복 배경 motion이 많음 |
| Retail / space analytics | people flow, queue, dwell, checkout, shelf/product recognition 등 multi-camera 분석 수요가 있음 |

`General multi-class object detection`은 별도 business vertical이 아니라 공통 평가축으로 둔다. 목적은 person/vehicle 중심 profile에 과적합되지 않는지, class-agnostic objectness ROI가 가능한지 확인하는 것이다.

도메인명은 business mapping으로 보고, 실제 기술 판단은 scene condition 기준으로 한다.

초기 scene coverage:

| Scene Condition | 예시 도메인 | 검증 포인트 |
|---|---|---|
| Stable indoor fixed camera | 관제, 출입구, 물류 | motion-primary gate 가능성 |
| Outdoor illumination variation | 교통, 주차장, 플랜트 | 조도/그림자/반사 robustness |
| Global camera shake / unstable feed | 교통, 터널, 외부 폴대 CCTV | scene guard와 fallback 필요성 |
| Slow or stationary target | 관제, 안전, 점유 감지 | detector/tracker assist 필요성 |
| Small far-field target | 고속도로, 야드, 주차장 | tile 크기와 high-recall context 필요성 |
| Dense multi-object scene | 교차로, 플랫폼, 리테일 | ROI explosion과 full-frame switch |
| Periodic machine/background motion | 스마트팩토리, 물류 설비 | background model과 periodic mask 필요성 |
| Low-light / compressed feed | 야간 CCTV, 저 bitrate stream | denoise/normalized signal 필요성 |

## 5. Validation Dataset Plan

Phase 1.3은 새 dataset을 무작정 늘리기 전에, 현재 보유한 dataset을 scene condition 기준으로 재분류해서 시작한다.

### Tier 0. Smoke / Tooling Sanity

| Dataset config | 역할 | 사용 기준 |
|---|---|---|
| `configs/datasets/base/smoke.yaml` | synthetic smoke | 새 tool/runner의 빠른 동작 확인 |
| `configs/datasets/samples/opencv_vtest.yaml` | annotation 없는 sample video | E2E loader/visualization sanity. 알고리즘 판단에는 사용하지 않음 |

Tier 0은 signal 품질 판단용이 아니다. CLI, output artifact, visualization이 깨지지 않는지만 확인한다.

### Tier 1. Existing Annotated Baselines

| Dataset config | Scene coverage | Target | Phase 1.3 역할 |
|---|---|---|---|
| `configs/datasets/physicalai/physicalai_row0709_after3m.yaml` | synthetic smart-space / crowded person / indoor fixed camera | `person` | Phase 1.2 main baseline. `rescue_with_budget_cap`, `feedback_confidence_decay` 비교 기준 |
| `configs/datasets/ua_detrac/ua_detrac_mvi_39361.yaml` | traffic / unstable camera / broad motion | `car`, `bus`, `truck` | global motion/fallback stress case |

Tier 1의 목적은 현재 코드와 metric으로 바로 재현 가능한 baseline을 확보하는 것이다.

Phase 1.3 공식 matrix에서는 `UA-DETRAC MVI_*`를 여러 개 넣지 않는다. Traffic/vehicle 대표는 우선 `MVI_39361` 하나만 사용한다. `MVI_40204`, `MVI_39051`, `MVI_39031`은 기존 run 재현이나 ad-hoc debug에는 남겨둘 수 있지만, Phase 1.3의 domain diversity를 늘리는 용도로 중복 사용하지 않는다.

`od_virat_tiny`는 Phase 1/1.1의 annotation-loader sanity와 historical lower-bound check 용도로만 남긴다. Phase 1.3에서는 person/surveillance coverage가 PhysicalAI와 MOTChallenge 후보와 겹치고, partial annotation 때문에 false ROI/precision 판단이 불안정하므로 공식 dataset plan에서 제외한다.

### Tier 2. Public Candidate Datasets

Tier 1만으로는 scene/domain coverage가 부족하므로, Phase 1.3에서 공개 dataset 후보를 추가 검토한다. 이 단계의 dataset은 바로 official matrix에 넣지 않고, loader/config 추가 비용과 license를 확인한 뒤 120-frame probe로 승격한다.

| Candidate | Domain / Scene | Annotation | Phase 1.3 목적 | 주의 |
|---|---|---|---|---|
| MOTChallenge MOT17Det / MOT17 | pedestrian surveillance, crowd, night, moving/static camera | pedestrian bbox | dense person, low-light, moving-camera stress | license와 sequence별 camera motion 확인 필요 |
| VisDrone-VID / VisDrone-MOT | drone/aerial surveillance, moving camera, small far-field targets | bbox / tracking annotations | moving camera와 small far-field object stress | CCTV 고정 카메라와 다르므로 범용성 해석에 주의 |
| MVTec AD / AD 2 | industrial inspection, factory-like object/texture anomaly | image-level / pixel-level anomaly mask | smart-factory inspection류 ROI/objectness 후보 검토 | video CCTV가 아니라 static inspection image 중심 |
| Mall Dataset | retail / space analytics | fixed shopping-mall webcam, dense pedestrian flow | 매장/공간 분석의 crowd/queue ROI 검증 | head-point GT라 bbox containment가 아닌 point containment 또는 proxy box 필요 |
| 추가 public parking / warehouse / retail CCTV sample | parking, logistics, retail | dataset별 상이 | domain gap 보강 | license, annotation 품질, 유지 가능성 확인 필요 |

초기 우선순위는 아래처럼 잡는다.

| Required Scene | 필요한 이유 | annotation requirement |
|---|---|---|
| outdoor illumination variation | 조도/그림자/반사에 대한 motion robustness 확인 | 최소 target bbox subset |
| slow or stationary target | motion-only signal missing 검증 | target bbox 또는 detector-reviewed label |
| periodic machine/background motion | 스마트팩토리/설비성 false ROI 확인 | target 여부 frame-level label부터 가능 |
| low-light / compressed feed | 야간/저 bitrate CCTV robustness 확인 | subset bbox 또는 reviewed frame list |
| dense multi-object scene | ROI explosion/full-frame switch 확인 | target bbox subset |

Tier 2 annotation은 처음부터 exhaustive일 필요는 없다. 단, 어떤 metric을 신뢰할 수 있는지 `annotations.quality`에 명시해야 한다.

### Tier 3. Internal / Customer-like Samples

공개 dataset만으로는 실제 적용 도메인을 충분히 대표하기 어렵다. Phase 1.3 중후반에는 내부 또는 고객 유사 sample을 별도 local config로 추가한다.

우선 확보할 sample:

| Sample Type | Scene Coverage | 최소 annotation |
|---|---|---|
| fixed indoor surveillance | stable indoor, slow/stationary person | person bbox subset |
| outdoor parking or road CCTV | illumination variation, small vehicle/person | vehicle/person bbox subset |
| smart factory / equipment camera | periodic machine/background motion | target frame label 또는 bbox subset |
| logistics / warehouse camera | sparse object/person motion, occlusion | person/package/forklift bbox subset |
| low-light compressed CCTV | night, compression noise | reviewed frame list + bbox subset |

Tier 3는 Git에 dataset 자체를 올리지 않는다. 공유 가능한 것은 config template, scene metadata, aggregate report, anonymized visualization만 둔다.

### Dataset Selection Rule

새 dataset config를 추가할 때는 도메인명보다 scene condition을 먼저 기록한다.

필수 기록:

- business domain
- primary scene condition
- secondary scene condition
- camera stability
- illumination condition
- target class
- target motion pattern
- annotation completeness
- unreliable metrics

현재 `DatasetConfig` schema에는 scene condition field가 없으므로, Phase 1.3 초반에는 dataset YAML의 `validation.notes`와 run log에 기록한다. 반복 사용이 확정되면 `validation.scene_conditions` 같은 구조화 field를 추가한다.

### Phase 1.3 Initial Matrix 제안

초기 matrix는 작게 시작한다.

| Slot | Dataset | 이유 |
|---|---|---|
| Main existing | `physicalai_row0709_after3m` | Phase 1.2와 직접 비교 가능한 indoor/person baseline |
| Traffic stress | `ua_detrac_mvi_39361` | `UA-DETRAC MVI_*` 대표 하나. unstable/global motion stress |
| Dense pedestrian candidate | MOTChallenge sequence 1개 | crowd/night/moving camera 중 하나를 선택 |
| Moving/small target candidate | VisDrone video sequence 1개 | small far-field/moving camera stress |
| Factory/inspection candidate | MVTec sample, internal factory clip, or verified warehouse CCTV dataset | smart-factory 계열 motion 부적합성 확인 |
| Domain expansion candidate | Mall Dataset 또는 internal retail/store clip | 실제 CCTV/GPU server 적용 도메인 확장성 확인 |

이 matrix의 목적은 dataset 수를 늘리는 것이 아니라 scene failure mode를 넓히는 것이다.

### Required Domain Coverage

Phase 1.3에서는 도메인을 너무 잘게 쪼개지 않고, 우선 GPU/DeepStream 수요가 큰 네 vertical과 공통 multi-class 평가축으로 검증한다.

| Coverage Group | 목적 | 필수 scene condition | 현재 상태 | 우선 dataset 후보 |
|---|---|---|---|---|
| Traffic / parking | 차량/도로/주차 CCTV에서 global motion, 조도, small far-field target을 검증 | outdoor illumination, unstable feed, dense vehicle, small far-field | `ua_detrac_mvi_39361`로 최소 baseline 있음 | `UA-DETRAC MVI_39361`, internal parking clip, verified traffic CCTV dataset |
| Surveillance / security | 관제/보안에서 person, slow/stationary target, low-light를 검증 | indoor/outdoor surveillance, slow/stationary person, low-light, crowd | 아직 official Phase 1.3 dataset 없음 | MOTChallenge sequence, internal CCTV clip |
| Logistics / smart factory | 공장/창고/설비 환경에서 periodic background motion과 작업자/물체 ROI를 검증 | indoor fixed, periodic machine/background motion, worker/package/forklift | `physicalai_row0709_after3m`로 synthetic warehouse baseline 있음 | PhysicalAI, internal factory/warehouse clip, verified warehouse CCTV dataset |
| Retail / space analytics | 매장/공간 분석에서 사람 flow, queue, shopper/crowd ROI를 검증 | dense person, occlusion, static camera, slow temporal change | 아직 official Phase 1.3 dataset 없음 | Mall Dataset, internal retail/store clip |
| General multi-class check | vertical 공통으로 class-agnostic ROI 가능성과 person/vehicle 과적합을 확인 | multi-class, varied scale, non-person/non-vehicle object, clutter | 아직 official Phase 1.3 dataset 없음 | VisDrone, selected public multi-class video |

초기 official matrix의 최소 목표:

| Coverage Group | 최소 dataset 수 | 이유 |
|---|---:|---|
| Traffic / parking | 1 | UA-DETRAC 계열은 하나만 사용해 중복을 피한다. |
| Surveillance / security | 1 | person/crowd/low-light 또는 stationary target 문제를 별도로 봐야 한다. |
| Logistics / smart factory | 1 | PhysicalAI synthetic warehouse baseline을 우선 사용한다. |
| Retail / space analytics | 1 | queue, dwell, shelf/product 등 사람+객체 혼합 scene을 봐야 한다. |
| General multi-class check | 1 | person/vehicle 중심으로 과적합되지 않는지 확인한다. |

### Dataset Selection Criteria

남은 dataset은 아래 기준으로 하나씩만 선정한다.

| 기준 | 이유 |
|---|---|
| ROI Gate metric에 직접 쓸 수 있는 spatial annotation | GT bbox, mask, point 등 active signal/ROI overlap을 계산할 수 있어야 한다. |
| video 또는 frame sequence 형태 | frame-to-frame signal, temporal hold, feedback, tracker 후보를 검증해야 한다. |
| 현재 보유 dataset과 scene condition이 덜 겹침 | `physicalai`와 `UA-DETRAC`이 이미 person/warehouse와 traffic/vehicle을 일부 커버한다. |
| loader/config 구현 비용이 과도하지 않음 | 120-frame probe까지 빠르게 올릴 수 있어야 한다. |
| GPU/DeepStream 수요가 큰 실제 vertical과 연결됨 | Phase 2 이후 runtime/integration 검증으로 이어질 수 있어야 한다. |
| license와 접근성이 검토 가능함 | dataset을 장기 baseline으로 유지할 수 있어야 한다. |

### Selected Phase 1.3 Dataset Set

Phase 1.3의 1차 official candidate set은 아래로 고정한다.

| Coverage Group | Selected Dataset | 선정 이유 | 준비 도구 | 주의 |
|---|---|---|---|---|
| Traffic / parking | `UA-DETRAC MVI_39361` | 이미 loader/config가 있고, traffic/vehicle/global motion stress를 대표한다. | `tools/datasets/download_ua_detrac.py` | `UA-DETRAC MVI_*`는 official matrix에서 하나만 사용한다. |
| Logistics / smart factory | `PhysicalAI row0709_after3m` | synthetic `Warehouse_000` smart-space baseline으로 Phase 1.2와 직접 비교 가능하다. | `tools/datasets/download_physicalai_row.py` | 실제 공장/창고 영상은 후속 internal/customer-like sample로 보강한다. |
| Surveillance / security | MOTChallenge MOT17Det `MOT17-04` | dense pedestrian, night, elevated viewpoint 조건으로 crowd/관제 stress를 제공한다. | `tools/datasets/download_mot17.py` | person-only라 `physicalai`와 target class는 겹치지만 scene condition이 다르다. |
| Retail / space analytics | Mall Dataset | shopping-mall webcam 기반 crowd/flow/space analytics에 가깝고 시간축 frame sequence와 exhaustive pedestrian head-position GT가 있다. | `tools/datasets/download_mall_dataset.py` | head-point GT라 ROI metric은 point containment 또는 proxy box로 해석한다. |
| General multi-class check | VisDrone-VID validation set | multi-class bbox, small far-field object, scale/density/weather variation을 제공한다. | `tools/datasets/download_visdrone_vid.py` | drone/aerial view라 CCTV 대표가 아니라 camera-motion/generalization stress로만 해석한다. |

따라서 Phase 1.3 시작 전 필수 추가 dataset은 세 개다.

1. MOTChallenge MOT17Det `MOT17-04`
2. Mall Dataset
3. VisDrone-VID validation set

Smart factory/logistics는 현재 PhysicalAI로 시작할 수 있지만, 실제 공장/물류 적용성을 보려면 internal factory/warehouse clip을 후속 보강 dataset으로 추가하는 것이 좋다.

Dataset 준비 명령:

```bash
python tools/datasets/download_mot17.py --download-images --extract
python tools/datasets/download_mall_dataset.py --extract
python tools/datasets/download_visdrone_vid.py --split val --extract
```

현재 로컬 준비 상태:

- 준비됨: `UA-DETRAC MVI_39361`, `PhysicalAI row0709_after3m`, MOTChallenge MOT17Det `MOT17-04`, Mall Dataset, VisDrone-VID validation `uav0000086_00000_v`
- VisDrone-VID는 Google Drive quota 때문에 자동 다운로드가 실패했으나, 수동으로 받은 `VisDrone2019-VID-val.zip`을 `data/visdrone_vid/archives/`에 두고 압축 해제했다.

### Phase 1.3 Smoke Readiness

아래 20-frame smoke run으로 dataset path, stream loader, annotation loader, report generation이 모두 연결되는지 확인했다.

| Coverage Group | Config | Run ID | 상태 |
|---|---|---|---|
| Traffic / parking | `configs/datasets/ua_detrac/ua_detrac_mvi_39361.yaml` | `phase1_3_smoke_traffic_ua_detrac_mvi_39361` | ready |
| Logistics / smart factory | `configs/datasets/physicalai/physicalai_row0709_after3m.yaml` | `phase1_3_smoke_logistics_physicalai_row0709_after3m` | ready |
| Surveillance / security | `configs/datasets/motchallenge/mot17_04.yaml` | `phase1_3_smoke_surveillance_mot17_04` | ready |
| Retail / space analytics | `configs/datasets/mall/mall_dataset.yaml` | `phase1_3_smoke_retail_mall_dataset` | ready |
| General multi-class check | `configs/datasets/visdrone/visdrone_vid_val_uav0000086.yaml` | `phase1_3_smoke_general_visdrone_uav0000086` | ready |

Phase 1.3 본 실험의 1차 matrix는 위 5개 dataset에 대해 같은 policy/profile set을 돌리고, 아래 metric을 hard 비교 기준으로 둔다.

| Metric | 해석 |
|---|---|
| `target_gt_roi_containment` | target을 ROI로 놓치지 않았는지 보는 1순위 품질 지표 |
| `effective_input_area_reduction` | fallback/full-frame check까지 포함한 실제 GPU handoff 절감률 |
| `fallback_frame_rate` | ROI gate가 실제로 독립 동작하지 못하고 full-frame으로 돌아간 비율 |
| `no_roi_target_frame_count` | target이 있는데 ROI가 하나도 생성되지 않은 frame 수 |
| object size bucket containment | small/far-field target 취약성 확인 |

현재 smoke 결과 기준으로 기존 motion-primary gate는 PhysicalAI indoor warehouse 외의 domain에서 대부분 fallback 또는 no-ROI로 붕괴한다. Phase 1.3은 이 결과를 baseline failure로 두고, scene guard, detector feedback, tracker/objectness 계열 후보를 비교한다.

### Public Dataset References

공개 dataset 후보는 download 가능 여부, license, annotation format을 확인한 뒤 config/loader 추가 여부를 결정한다.

| Dataset | Reference |
|---|---|
| MOTChallenge MOT17Det | `https://motchallenge.net/data/MOT17Det/` |
| VisDrone | `https://github.com/VisDrone/VisDrone-Dataset` |
| MVTec AD | `https://www.mvtec.com/research-teaching/datasets/mvtec-ad` |
| Mall Dataset | `https://personal.ie.cuhk.edu.hk/~ccloy/downloads_mall_dataset.html` |

## 6. Codebase Strategy

Phase 1.3 시작 전에 기존 Phase 1.2 구현을 삭제하거나 크게 리팩토링하지 않는다.

이유:

- `rescue_with_budget_cap`과 `feedback_confidence_decay`는 Phase 1.3의 비교 기준선이다.
- tile metadata, cost summary, validation matrix, failure taxonomy는 새 signal/architecture 후보를 평가하는 데 재사용 가능하다.
- 기존 output artifact contract가 깨지면 Phase 1.1/1.2 결과와 비교하기 어려워진다.

### 유지할 것

| Area | 유지 이유 |
|---|---|
| `roi_generator/core/` | gate decision, budget, feedback, contract가 downstream 비교 기준 |
| `roi_generator/signals/` | frame diff/event maps가 baseline signal |
| `roi_generator/candidates/` | component/tile candidate primitive가 baseline과 비교군 |
| `roi_generator/policies/` | Phase 1.1/1.2 profiles 재현 필요 |
| `roi_generator/observability/` | metadata/report/debug artifact contract 유지 |
| `experiments/run_roi_proposal_validation.py` | ROI proposal validation의 canonical runner |
| `experiments/run_validation_matrix.py` | profile registry 기반 비교 실행 유지 |
| `configs/roi_generator/profiles.yaml` | baseline/challenger registry 유지 |

### 추가할 가능성이 높은 것

Phase 1.3에서는 기존 runtime path를 바로 바꾸기보다, probe/audit 도구를 먼저 추가한다.

| 후보 위치 | 역할 |
|---|---|
| `roi_generator/signals/` | normalized diff, background subtraction, optical-flow residual 등 cheap signal 후보 |
| `evaluation/metrics/` | signal coverage, active area, global activation metric |
| `evaluation/reports/` | signal validity report builder |
| `experiments/run_signal_validity_audit.py` | dataset + signal config 기준 signal 품질 audit |
| `configs/signals/` 또는 `configs/roi_generator/phase1_3/` | signal candidate config |
| `configs/experiments/phase1_3_*.yaml` | scene/domain PoC experiment matrix |
| `visualization/` | signal map, active region, GT overlap visualization |

### 리팩토링 판단 기준

초기에는 아래 변경을 피한다.

- `GateDecision` schema 대규모 변경
- 기존 Phase 1.1/1.2 profile 삭제
- `TileMaskPolicy` 내부에 scene/domain controller를 직접 삽입
- dataset loader schema의 대규모 변경
- E2E YOLO runner를 signal audit에 강하게 결합

리팩토링은 아래 조건이 충족될 때만 진행한다.

- 둘 이상의 signal 후보가 같은 interface를 요구한다.
- signal audit과 ROI generator runtime 사이에 중복 코드가 생긴다.
- 새 architecture family가 600-frame validation으로 승격되어 runtime path에 들어가야 한다.
- 기존 metadata/report contract를 유지한 채 확장할 수 있다.

### 삭제 판단 기준

Phase 1.3 시작 시점에는 삭제하지 않는다.

삭제 후보는 아래 조건을 만족할 때만 제거한다.

- profile registry에서 disabled 상태이고 재현 필요성이 사라졌다.
- 같은 역할의 더 명확한 baseline으로 대체되었다.
- 관련 run log에서 결과가 보존되어 있다.
- 제거해도 Phase 1.1/1.2 결과 재현과 비교에 영향이 없다.

그 전까지는 `status: disabled` 또는 `reference_only`로 남기는 편이 낫다.

## 7. Candidate Architecture Families

Phase 1.3은 개별 profile보다 architecture family를 비교한다.

| Family | 설명 | 기대 적용 scene |
|---|---|---|
| Motion-primary gate | 현재 motion/tile 방향 유지 | stable fixed camera, sparse motion |
| Motion + scene guard gate | global motion, illumination shift, camera shake를 먼저 감지 | outdoor/unstable scene |
| Background-model gate | running background와 foreground mask 기반 ROI | stable camera with noisy frame diff |
| Detector-assisted gate | low-frequency detector/feedback/cache로 motion miss 보완 | slow/stationary target, high miss cost |
| Tracker-assisted gate | keyframe detection 이후 short-term track으로 ROI 유지 | 관제, 안전, low-speed target |
| Heatmap/contour ROI gate | fixed tile 대신 signal heatmap contour에서 ROI 생성 | compact ROI가 필요한 scene |
| Compressed-domain pre-gate | H.264/H.265 motion vector 등 encoded cue 활용 | RTSP/CCTV stream integration 후보 |
| Lightweight objectness gate | cheap objectness/segmentation model로 target-likely region 생성 | motion이 불안정한 scene |

## 8. Workstreams

### Workstream A. Motion Signal Validity Audit

목표:

- 현재 motion map이 GT target을 실제로 얼마나 support하는지 수치화한다.
- ROI failure를 boundary miss가 아니라 signal failure 관점으로 다시 분류한다.

주요 지표:

- GT bbox와 active signal overlap
- GT center in active signal
- target without signal
- active area ratio
- no-target frame false active area
- global activation frame count
- threshold sweep recall/cost curve

산출물:

- `signal_validity_report.json`
- `signal_validity_report.md`
- representative visualization

### Workstream B. Scene Guard Probe

목표:

- ROI selection 전에 global motion, illumination shift, camera shake를 분리할 수 있는지 본다.

후보 feature:

- active area ratio
- selected tile count spike
- tile activation entropy
- mean luminance delta
- histogram distance
- global optical flow consistency

성공 조건:

- fallback-dominated scene을 정상 scene과 구분한다.
- 정상 target motion을 과하게 global scene change로 분류하지 않는다.

### Workstream C. Cheap Signal Alternatives

목표:

- raw grayscale frame diff보다 안정적인 cheap ROI signal이 있는지 비교한다.

후보:

- luminance-normalized diff
- Y/Cr/Cb 또는 HSV channel-separated diff
- background subtraction
- running temporal median / running average
- temporal consistency filter
- edge-aware diff
- optical-flow residual

성공 조건:

- target signal coverage를 유지하면서 false active area를 줄인다.
- preprocessing latency가 ROI Gate 앞단에 둘 수 있는 수준이어야 한다.

### Workstream D. Assisted ROI Gate

목표:

- motion-only signal missing을 detector feedback, tracker, low-frequency refresh로 보완할 수 있는지 본다.

후보:

- `feedback_confidence_decay` cost tuning
- feedback ROI cap/merge scoring
- risk-based full-frame refresh
- short-term tracker ROI prediction
- no-policy-ROI risk assist

성공 조건:

- high-recall 효과를 유지하면서 tensor cost를 낮춘다.
- high miss-cost scene에서 practical assist path를 정의한다.

### Workstream E. Alternative ROI Shape

목표:

- tile contract를 유지할지, contour/heatmap/non-uniform tile로 바꿀지 판단한다.

후보:

- heatmap/contour ROI
- non-uniform tile layout
- hierarchical tile split/merge
- small far-field region-specific tile

성공 조건:

- current best tile profile보다 containment/cost 균형이 좋아야 한다.
- 특정 scene에만 좋은 경우 domain/scene-specific 후보로 남긴다.

## 9. Evaluation Rule

Phase 1.3은 처음부터 E2E YOLO 성능만 보지 않는다. 먼저 ROI proposal과 signal quality를 본다.

1차 probe 지표:

- signal coverage
- target without signal
- false active area
- active area ratio
- ROI/frame 또는 equivalent region/frame
- tensor cost/frame estimate
- fallback frame count and reason
- preprocessing latency

2차 validation 지표:

- target ROI containment
- missed target GT count
- missed target frame count
- false ROI count/rate
- ROI/frame
- tensor cost/frame
- effective input area reduction
- fallback frame count
- E2E detector recall, 필요 시

## 10. 실행 순서

1. Motion Signal Validity Audit 도구를 만든다.
2. PhysicalAI main segment와 UA-DETRAC secondary segment에 audit을 실행한다.
3. scene condition coverage 기준으로 추가 sample segment를 고른다.
4. scene guard와 cheap signal alternative를 120-frame probe로 비교한다.
5. assisted ROI gate를 high miss-cost scene 후보로 비교한다.
6. 살아남은 2-3개 architecture family만 600-frame validation으로 올린다.
7. 도메인/scene별 ROI Gate recommendation matrix를 작성한다.

## 11. Phase 1.3 종료 산출물

Phase 1.3은 단일 default profile보다 아래 산출물을 목표로 한다.

- motion map validity report
- scene condition taxonomy
- domain-to-scene mapping
- candidate gate architecture comparison
- reusable signal/ROI probe tooling
- 600-frame validation 대상 shortlist
- 다음 phase implementation target

## 12. 다음 Phase로 넘길 판단

Phase 1.3 이후에는 아래 중 하나를 선택한다.

| 판단 | 다음 단계 |
|---|---|
| 공통 적용 가능한 ROI Gate 조합이 보임 | 해당 architecture를 구현/고도화하는 Phase 2로 진행 |
| scene별로 다른 gate가 필요함 | scene classifier/controller와 profile family 구현으로 진행 |
| motion 기반 한계가 명확함 | detector-assisted, background-model, objectness, compressed-domain 중 유망 후보로 전환 |
| ROI proposal은 충분하지만 GPU 이득이 불확실함 | ROI handoff, batching, packing, full-frame switch 최적화로 진행 |
