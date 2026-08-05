# Phase 1 Validation Pipeline Plan

이 문서는 Phase 1.1 ROI crop/gate policy 개선으로 넘어가기 전에, Phase 1 검증 파이프라인을 공유 가능한 기준으로 고정하기 위한 작업 계획이다.

목표는 알고리즘 성공을 주장하는 것이 아니라, 다음 단계 개선안도 같은 방식으로 비교할 수 있는 재현 가능한 검증 체계를 만드는 것이다.

## 1. 검증 단계

Phase 1 검증은 두 단계로 나눈다.

| 단계 | 기준 | 목적 | 현재 상태 |
|---|---|---|---|
| Pipeline Qualification | full-frame YOLO pseudo reference | end-to-end 실행, report 생성, profile 비교 가능성 확인 | 우선 진행 |
| Annotation-aware Validation | dataset annotation | annotated object recall, ROI containment 보조 평가 | OD-VIRAT Tiny partial annotation loader 구현됨 |

Phase 1.1은 Pipeline Qualification이 끝난 뒤 진행한다. 현재 public annotation dataset은 exhaustive GT로 가정하지 않는다. 실제 object recall을 hard criterion으로 쓰려면 annotation completeness가 확인된 internal CCTV 또는 별도 curated validation set이 필요하다.

Phase 1.1부터 검증 파이프라인은 역할 기준으로 분리한다.

| Pipeline | Script | Output root | 목적 |
|---|---|---|---|
| ROI Proposal Validation | `experiments/run_roi_proposal_validation.py` (planned) | `outputs/roi_proposal_validation/` | downstream model 없이 ROI 생성 품질 평가 |
| E2E Inference Validation | `experiments/run_e2e_inference_validation.py` | `outputs/e2e_inference_validation/` | ROI 생성부터 GPU/model inference, workload, latency까지 평가 |

기존 `experiments/run_phase1_experiment.py`는 제거하고, E2E 검증은 `experiments/run_e2e_inference_validation.py`만 사용한다.

## 2. Dataset 기준

| Tier | Dataset | Config | 목적 | 판단 범위 |
|---|---|---|---|---|
| Tier 0 | `opencv-vtest` | `configs/dataset.opencv_vtest.yaml` | 빠른 smoke, end-to-end 확인 | 성능 판단 제외 |
| Tier 1 | `ua-detrac` | `configs/dataset.ua_detrac_mvi_20011.yaml` | 연속 프레임과 bbox GT가 있는 ROI proposal primary validation | vehicle GT ROI containment, ROI count/area, latency, failure visualization |
| Tier 2 | `od-virat-tiny` | `configs/dataset.od_virat_tiny.yaml` | partial annotation 포함 surveillance 보조 검증 | annotation 누락 한계를 명시한 annotated-object lower-bound 보조 평가 |
| Tier 3 | `internal-cctv` | 추가 필요 | 실제 PoC/사업성 검증 | 보안/annotation 기준 이후 |

우선순위는 Tier 0 smoke와 Tier 1 UA-DETRAC을 먼저 고정하는 것이다.

Construction Site Static Camera는 검토 후 active validation dataset에서 제외했다. `IMG259`-`IMG457` 구간의 balanced/high-res ROI gate 결과는 `outputs/`에 보존하되, 단일 연속 영상이 아니고 raw ROI가 거의 전체 프레임으로 확장되어 ROI proposal primary 검증에 부적합하다고 기록한다.

## 3. 고정 실험 Matrix

각 dataset/segment에 대해 가능한 한 같은 matrix를 적용한다.

| Run | Gate config | Full-frame checks | 목적 |
|---|---|---|---|
| `roi_aggressive` | `configs/npx_gate.profile_aggressive.yaml` | on | 절감 우선 profile |
| `roi_balanced` | `configs/npx_gate.profile_balanced.yaml` | on | 기본 profile |
| `roi_balanced_highres` | `configs/npx_gate.profile_balanced_highres.yaml` | on | 작은 객체가 많은 4K/static scene용 high-res ROI analysis |
| `roi_recall` | `configs/npx_gate.profile_recall.yaml` | on | 검출 유지 우선 profile |
| `roi_balanced_no_refresh` | `configs/npx_gate.profile_balanced.yaml` | off | periodic full-frame check 효과 분리 |
| `roi_dataset_specific` | dataset-specific config | on | dataset별 tuned config 비교 |

Full-frame baseline은 각 run 내부에서 동일하게 생성된다.

## 4. 실행 단위

| 단위 | Frame limit | Render limit | 목적 |
|---|---:|---:|---|
| Quick run | 120 | 30 | 코드 변경 후 빠른 확인 |
| Review run | 1000 이상 | 100 | profile 비교와 failure case 검토 |
| Validation run | 고정 segment 전체 | 필요 범위 | 결과 표 기준 run |

Run id 규칙:

```text
<dataset>_<segment>_<profile>_<yyyymmdd>
```

예:

```text
opencv_vtest_f0000_0120_balanced_20260729
ua_detrac_mvi_20011_f0000_0120_recall_20260805
```

## 5. 기본 실행 명령

OpenCV vtest quick:

```bash
python3 experiments/run_e2e_inference_validation.py \
  --dataset-config configs/dataset.opencv_vtest.yaml \
  --gate-config configs/npx_gate.profile_balanced.yaml \
  --yolo-config configs/yolo.yaml \
  --experiment-name opencv_vtest_balanced \
  --limit 120 \
  --render-limit 30
```

UA-DETRAC balanced review:

```bash
python3 experiments/run_e2e_inference_validation.py \
  --dataset-config configs/dataset.ua_detrac_mvi_20011.yaml \
  --gate-config configs/npx_gate.profile_balanced.yaml \
  --yolo-config configs/yolo.yaml \
  --experiment-name ua_detrac_mvi_20011_balanced \
  --limit 1000 \
  --render-limit 100
```

UA-DETRAC high-res ROI analysis review:

```bash
python3 experiments/run_e2e_inference_validation.py \
  --dataset-config configs/dataset.ua_detrac_mvi_20011.yaml \
  --gate-config configs/npx_gate.profile_balanced_highres.yaml \
  --yolo-config configs/yolo.yaml \
  --experiment-name ua_detrac_mvi_20011_balanced_highres \
  --limit 1000 \
  --render-limit 100
```

UA-DETRAC no-refresh ablation:

```bash
python3 experiments/run_e2e_inference_validation.py \
  --dataset-config configs/dataset.ua_detrac_mvi_20011.yaml \
  --gate-config configs/npx_gate.profile_balanced.yaml \
  --yolo-config configs/yolo.yaml \
  --experiment-name ua_detrac_mvi_20011_balanced_no_refresh \
  --limit 1000 \
  --render-limit 100 \
  --disable-full-frame-checks
```

## 6. 필수 산출물

각 run은 `outputs/e2e_inference_validation/<run_id>/` 아래에 생성된다.

```text
manifest.json
roi_metadata/rule_roi.jsonl
roi_metadata/gate_decisions.jsonl
detections/full_frame.jsonl
detections/roi_yolo.jsonl
reports/full_frame_metrics.json
reports/roi_yolo_metrics.json
reports/comparison_report.json
reports/comparison_report.md
visualizations/roi_overlay/
visualizations/comparison/
visualizations/failures/
```

## 7. 확인할 지표

Pipeline Qualification에서 확인할 지표:

- pseudo recall retention
- ROI containment rate
- YOLO call reduction
- YOLO input pixel area reduction
- full-frame check count
- average ROI count
- average ROI area ratio
- ROI YOLO average latency
- gate average/max latency
- failure case count
- hardware/backend snapshot

Annotation-aware Validation에서 추가할 지표:

- annotated object recall
- annotated class별 recall
- annotation bbox 기준 ROI containment
- false ROI rate
- missed annotated-object case taxonomy
- detection duplicate rate

Annotation metric 해석 기준:

- 새 annotation dataset을 추가할 때는 `annotations.quality.completeness`와 `expected_exhaustive`를 config에 명시한다.
- `expected_exhaustive: false` 또는 `completeness: unknown/partial`이면 recall과 ROI containment는 annotated-object lower-bound check로만 사용한다.
- visible object가 annotation에 누락될 수 있는 dataset에서는 false ROI rate, precision, false positive count를 hard criterion으로 쓰지 않는다.
- Phase 1.1 Keep/Tune 판단은 baseline balanced 대비 pseudo recall, ROI count latency, failure visualization을 우선하고, annotation metric은 annotation 품질 범위 안에서 보조 기준으로 사용한다.

## 8. Profile별 결과 정리

Phase 1.1 시작 전에는 같은 dataset/segment 기준으로 profile 결과를 한 표에 정리한다.

| 항목 | aggressive | balanced | recall | no-refresh | dataset-specific |
|---|---:|---:|---:|---:|---:|
| pseudo recall retention | | | | | |
| ROI containment | | | | | |
| input pixel area reduction | | | | | |
| YOLO call count | | | | | |
| full-frame check count | | | | | |
| average ROI count | | | | | |
| average ROI area ratio | | | | | |
| analysis frame size | | | | | |
| ROI YOLO average latency | | | | | |
| gate average latency | | | | | |
| failure case count | | | | | |

필요 작업:

- 여러 experiment output을 읽어 profile별 summary table을 생성하는 도구를 추가한다.
- 후보 파일명: `tools/summarize_phase1_profiles.py`

## 9. ROI 개수별 Latency Benchmark

Phase 1.1 전에 ROI 개수 증가가 실제 inference latency에 미치는 영향을 별도로 확인한다.

Bucket:

| Bucket | 의미 |
|---|---|
| `0` | ROI 없음 |
| `1` | 단일 ROI |
| `2-3` | 일반적인 ROI crop 이득 기대 구간 |
| `4-5` | overhead 경계 구간 |
| `6-8` | fallback 후보 구간 |
| `9+` | full-frame fallback 우선 검토 구간 |

필수 집계 항목:

- frame count
- average ROI count
- average total ROI area ratio
- ROI YOLO call count
- full-frame check count
- average ROI YOLO latency
- p95 ROI YOLO latency
- full-frame baseline latency
- latency delta vs full-frame
- pseudo recall retention
- failure case count

필요 작업:

- `comparison_report.json`은 평균 ROI count와 평균 latency만 제공하므로 bucket별 집계 도구를 추가한다.
- 후보 파일명: `tools/benchmark_roi_count_latency.py`

## 10. Pipeline Qualification 통과 조건

아래 조건을 만족하면 Phase 1.1 ROI crop/gate policy 개선으로 넘어간다.

- [x] `opencv-vtest` quick run이 end-to-end로 성공한다.
- [ ] `ua-detrac` quick run이 end-to-end로 성공한다.
- [x] `od-virat-tiny` quick run이 end-to-end로 성공한다.
- [x] aggressive/balanced/recall profile 3개 결과가 같은 형식으로 비교 가능하다.
- [x] no-refresh ablation으로 periodic full-frame check 효과를 분리할 수 있다.
- [ ] failure visualization으로 missed pseudo-reference case를 수동 검토할 수 있다.
- [x] ROI 개수 증가가 latency/call overhead에 미치는 영향을 report로 확인할 수 있다.
- [x] OD-VIRAT Tiny annotation 품질 한계와 loader 구현 범위가 문서화되어 있다.

## 11. 구현 작업 목록

- [x] Profile별 summary 도구 추가
  - `tools/summarize_phase1_profiles.py`
  - 여러 run의 `manifest.json`과 `comparison_report.json`을 읽어 Markdown/JSON summary 생성
- [x] ROI count latency benchmark 도구 추가
  - `tools/benchmark_roi_count_latency.py`
  - `roi_metadata`, `gate_decisions`, `roi_yolo_metrics`, `comparison_report`를 읽어 ROI count bucket별 report 생성
- [x] OD-VIRAT Tiny config 추가
  - `configs/dataset.od_virat_tiny.yaml`
  - partial annotation 품질 metadata 포함
- [x] Pipeline 실행 결과 기록 방식 정리
  - `docs/runs/phase1_validation_runs.md` 또는 output manifest 기준으로 관리
- [x] Unit test 추가
  - summary/benchmark 집계 로직은 작은 fixture로 테스트
- [x] Hardware/backend snapshot 기록
  - `manifest.json`에 platform, PyTorch CUDA/MPS, `nvidia-smi` availability를 기록
  - NVIDIA GPU utilization sampling은 추후 `nvidia-smi dmon` 또는 Jetson `tegrastats` 연동으로 확장

## 12. 다음 단계 연결

Phase 1.1 개선안은 이 문서의 matrix와 산출물 형식을 그대로 사용해 비교한다.

비교 대상:

- current rule-based ROI gate
- improved ROI policy controller
- tracking-assisted ROI
- confidence-aware refresh
- batching/packing decision
