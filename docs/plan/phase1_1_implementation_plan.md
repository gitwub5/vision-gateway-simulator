# Phase 1.1 ROI/Gate Policy Implementation Plan

이 문서는 Phase 1.1에서 ROI crop/ROI generator policy를 개선하기 위한 공유 구현 계획이다.

Phase 1.1의 목표는 ROI crop 면적을 무조건 줄이는 것이 아니다. 산업/장면별 target class에 필요한 ROI를 충분히 포함하면서 모델 입력 픽셀량, ROI 개수, full-frame refresh/fallback 비용을 줄일 수 있는지 검증한다.

## 1. 원칙

Phase 1.1의 모든 변경은 가설 단위로 구현한다.

이번 Phase 1.1 작업은 단독 작업 기준으로 진행한다. 별도 R&R 섹션은 두지 않는다.

각 가설은 다음 중 하나로 판정한다.

| 판정 | 의미 | 처리 |
|---|---|---|
| Keep | 기준 metric이 baseline보다 개선되거나 동일 성능에서 비용이 줄어듦 | 기본 후보로 유지 |
| Tune | 방향은 맞지만 특정 dataset/profile에서 기준 미달 | config나 threshold를 조정한 뒤 재검증 |
| Disable | 일부 환경에서만 유효하거나 불안정함 | feature flag로 비활성화하고 코드 경로는 보존 |
| Remove | 성능 개선 근거가 없고 복잡도만 늘어남 | 구현 제거 또는 실험 branch로 격리 |

따라서 Phase 1.1 구현은 반드시 feature flag/config로 켜고 끌 수 있어야 한다.

체크박스는 실제 구현, 최소 동작 확인, 검증 산출물 생성이 끝났을 때만 완료 처리한다. 단순 파일 생성이나 미사용 코드 추가만으로 완료 처리하지 않는다.

## 2. 구현 체크리스트

### 2.1 선행 작업: annotation 기반 보조 검증

- [x] OD-VIRAT Tiny annotation JSON reader 구현
- [x] `image_id`, `file_name`, dataset `frame_id` mapping 확정
- [x] GT bbox/class를 공통 annotation 포맷으로 변환
- [x] GT detection matching 구현
- [x] annotation 품질 metadata 추가
  - [x] `annotations.quality.completeness: partial`
  - [x] `annotations.quality.expected_exhaustive: false`
- [x] annotated-object report 생성
  - [x] annotated object recall
  - [x] annotated class recall
  - [x] annotated ROI containment
  - [x] missed annotated object count
  - [x] false ROI rate caution 처리
  - [x] duplicate detection rate
- [x] GT bbox 포함 failure visualization 생성
- [x] OD-VIRAT Tiny 120-frame quick run으로 annotation report 검증
- [x] `docs/runs/`에 annotation 기반 run 결과 위치 기록
- [x] target-aware ROI validation scope를 dataset config에 추가
- [x] `experiments/run_roi_proposal_validation.py` 구현
- [x] PhysicalAI row 709 120-frame ROI Proposal quick run으로 target GT 기준 report 검증

### 2.2 Stage A0: ROI Candidate Quality / Noise Filtering

- [x] ROI generator processing size를 config로 키울 수 있는 옵션 추가
- [x] `balanced_highres` config 추가
- [x] ROI generator debug trace 시각화 추가
- [x] UA-DETRAC MVI_39051 / PhysicalAI row 709 120-frame ROI debug run으로 candidate 품질 문제 유형 확인
- [ ] merge 전 noise component filtering feature flag 추가
- [ ] connected component size/shape/density metadata를 debug summary에 기록
- [ ] 너무 작은 component 제거 기준 추가
- [ ] 너무 얇거나 긴 component 제거 기준 추가
- [ ] motion density가 과도한 frame의 diagnostic reason 추가
- [ ] filtering 이후 가까운 ROI merge 또는 기존 merge policy 확장
- [ ] minimum padding / margin 보강으로 작은 target ROI 보존
- [ ] `candidate_noise_filter_balanced` config 추가
- [ ] `candidate_recall_balanced` config 추가
- [ ] baseline balanced 대비 UA-DETRAC quick run 비교
- [ ] PhysicalAI row 709 quick run 비교
- [ ] OD-VIRAT Tiny annotated-object 보조 run 비교
- [ ] A0 Keep/Tune/Disable/Remove 판정 기록

### 2.3 Stage A: ROI Budget / Fallback Policy

- [ ] Stage A0 candidate quality 개선안 확정
- [ ] `roi_budget.enabled` feature flag 추가
- [ ] `max_roi_per_frame` 초과 시 full-frame fallback policy를 feature flag 뒤로 이동
- [ ] `max_total_roi_area_ratio` 초과 시 full-frame fallback policy를 feature flag 뒤로 이동
- [ ] budget decision reason을 `gate_decisions.jsonl`에 기록
- [ ] `budget_balanced` config 추가
- [ ] A0 확정 profile 대비 UA-DETRAC quick run 비교
- [ ] PhysicalAI row 709 quick run 비교
- [ ] OD-VIRAT Tiny annotated-object 보조 run 비교
- [ ] ROI count latency benchmark 생성
- [ ] Stage A Keep/Tune/Disable/Remove 판정 기록

### 2.4 Stage B: Adaptive Full-frame Refresh

- [ ] `adaptive_refresh.enabled` feature flag 추가
- [ ] base/min/max refresh interval config 추가
- [ ] ROI 없음 지속 기반 force refresh 구현
- [ ] ROI count 급증 기반 force refresh 구현
- [ ] motion density 변화 기반 force refresh 구현
- [ ] refresh decision reason을 `gate_decisions.jsonl`에 기록
- [ ] `adaptive_refresh_balanced` config 추가
- [ ] fixed refresh/no-refresh 대비 UA-DETRAC quick run 비교
- [ ] OD-VIRAT Tiny annotated-object 보조 run 비교
- [ ] Keep/Tune/Disable/Remove 판정 기록

### 2.5 Stage C: Tracking-assisted ROI

- [ ] `tracking_roi.enabled` feature flag 추가
- [ ] IoU/centroid 기반 lightweight track memory 구현
- [ ] track age, last seen, confidence moving average 관리
- [ ] 살아 있는 track 주변 predicted ROI 생성
- [ ] motion ROI와 track ROI merge
- [ ] track confidence 저하 시 refresh risk 증가
- [ ] `tracking_balanced` config 추가
- [ ] failure visualization에서 정지/느린 객체 miss 감소 여부 확인
- [ ] Keep/Tune/Disable/Remove 판정 기록

### 2.6 Stage D: Combined Policy

- [ ] `combined_balanced` config 추가
- [ ] candidate quality / budget / refresh / tracking profile을 scene state에 따라 선택하는 controller 후보 정리
- [ ] budget, adaptive refresh, tracking ROI 간 decision priority 정리
- [ ] decision reason을 report에 요약
- [ ] profile summary에 policy label 추가
- [ ] ROI count latency benchmark에 policy label 추가
- [ ] full matrix 실행
  - [ ] `baseline_balanced`
  - [ ] `candidate_quality_baseline`
  - [ ] `budget_balanced`
  - [ ] `adaptive_refresh_balanced`
  - [ ] `tracking_balanced`
  - [ ] `combined_balanced`
  - [ ] `baseline_recall`
  - [ ] `balanced_no_refresh`
- [ ] Phase 1.1 최종 Keep/Tune/Disable/Remove 판정

### 2.7 Stage E: Compressed-domain Probe

- [ ] FFmpeg 또는 PyAV로 motion vector 접근 가능성 확인
- [ ] motion vector 기반 ROI prototype 작성 여부 결정
- [ ] frame difference ROI와 noise/coverage 비교
- [ ] Jetson/DeepStream pipeline metadata 전달 가능성 조사
- [ ] Phase 1.2 후보 승격 또는 research 보류 판정

### 2.8 문서화

- [ ] 구현 결과를 `docs/tasks/phase1_1/` 아래에 task 문서로 정리
- [ ] 실행 결과 위치를 `docs/runs/`에 기록
- [ ] 공유 가능한 결론은 `docs/plan/` 또는 README에 반영
- [ ] 비공개 기술 판단은 `docs/idea/`에 유지
- [ ] 제거 또는 비활성화한 feature의 이유 기록

## 3. Baseline

기본 baseline은 목적별로 분리한다.

| 목적 | Baseline |
|---|---|
| 산업/창고 target-aware ROI proposal | `PhysicalAI row 709 + person + balanced profile` |
| 실사 temporal vehicle ROI proposal | `UA-DETRAC MVI_39051 + vehicle target classes + balanced profile` |
| E2E inference compatibility | 각 dataset의 동일 gate profile + `run_e2e_inference_validation.py` |

Construction Site Static Camera는 Phase 1.1 후보로 검토했지만 active baseline에서 제외했다. `IMG259`-`IMG457` 구간 high-res ROI generation 결과는 보존하되, official config는 거의 모든 frame에서 full-frame fallback으로 빠졌고 fallback을 끈 diagnostic run은 ROI가 거의 전체 프레임을 덮어 ROI proposal 품질 판단에 부적합했다.

OD-VIRAT Tiny는 annotation이 일부 객체만 포함하는 partial annotation dataset이므로 primary GT dataset으로 쓰지 않는다. 대신 annotated-object lower-bound 보조 평가와 public surveillance sample 확인에 사용한다.

비교 대상:

| Baseline | 목적 |
|---|---|
| `baseline_balanced` | 기본 비교 기준 |
| `baseline_recall` | recall upper bound |
| `balanced_no_refresh` | full-frame refresh ablation |

Phase 1.1 후보는 baseline balanced 대비 개선 여부를 판단한다.

## 4. 선행 작업: annotation 기반 보조 검증

Phase 1.1 policy 구현 전에 OD-VIRAT Tiny annotation loader를 구현한다.

다만 OD-VIRAT Tiny annotation은 모든 visible object가 표시된 exhaustive GT로 보지 않는다. 일부 frame에서는 실제 차량/사람이 여러 개 있어도 annotation은 일부 객체만 포함할 수 있다.

따라서 이 데이터의 annotation metric은 "실제 전체 객체 recall"이 아니라 annotated-object lower-bound check로 해석한다. Phase 1.1 Keep/Tune/Disable/Remove의 hard criterion은 primary dataset의 target GT ROI containment, missed target GT, ROI area/count, effective input area reduction, gate latency, ROI proposal failure visualization을 우선한다.

### 구현 항목

- OD-VIRAT Tiny annotation JSON reader 추가
- dataset frame id와 annotation image id mapping 확정
- annotation bbox/class를 공통 annotation 포맷으로 변환
- annotated-object 기반 report 생성
- annotation bbox가 포함된 failure visualization 생성

### 산출 metric

- annotated object recall
- annotated class recall
- annotated ROI containment
- missed annotated object count
- false ROI rate caution
- duplicate detection rate

### 완료 기준

- OD-VIRAT Tiny 120-frame quick run에서 annotation report가 생성된다.
- 기존 pseudo-reference report와 annotation report를 함께 비교할 수 있다.
- failure visualization에서 full-frame detection, ROI detection, annotation bbox를 함께 볼 수 있다.
- report와 config에 `expected_exhaustive: false`가 명시되어 있다.

## 5. Stage A0: ROI Candidate Quality / Noise Filtering

### 가설

Phase 1.1의 다음 policy 실험은 후보 ROI 품질이 일정 수준 이상일 때만 유효하다. 현재 debug run 결과, primary 문제는 budget/fallback 자체보다 **merge 전 후보 ROI 품질**이다.

UA-DETRAC MVI_39051에서는 나무, 그림자, 미세 배경 변화가 작은 connected component를 대량 생성하고, 이 component들이 merge 단계에서 거의 전체 프레임 ROI로 합쳐진 뒤 `max_total_roi_area_ratio` fallback으로 빠진다. 따라서 noise component를 merge 전에 제거하고, motion density가 과도한 frame을 diagnostic reason으로 분리하면 full-frame fallback 의존을 줄일 수 있다.

PhysicalAI row 709에서는 반대로 motion map이 희박하고 ROI 면적이 작아 target person을 충분히 포함하지 못한다. 따라서 Stage A0는 noise 억제만이 아니라 작은 target을 보존하기 위한 minimum padding/margin 보강을 함께 검증한다.

Stage A0가 해결되지 않으면 Stage A-D의 budget, refresh, tracking 결과는 candidate 품질 문제를 함께 측정하게 되므로 의사결정 근거로 쓰기 어렵다. 따라서 Stage A0는 이후 Stage A-D의 선행 조건으로 둔다.

### 구현 항목

- `component_filter.enabled` feature flag 추가
- merge 전 connected component filtering 추가
  - 너무 작은 component 제거
  - 너무 얇거나 긴 component 제거
  - frame 전체 motion density가 과도한 경우 diagnostic reason 기록
- filtering 전/후 candidate count, merged ROI count, ROI area ratio를 ROI debug summary에 표시
- filtering 이후 가까운 ROI merge 또는 기존 merge policy 확장
- minimum padding 또는 margin 보강으로 작은 target ROI 보존
- ROI generator processing size config를 이용한 high-res analysis profile 비교

### 비교 run

| Run | 설명 |
|---|---|
| `baseline_balanced` | 기존 balanced |
| `baseline_balanced_highres` | ROI generator high-res analysis 적용 |
| `candidate_noise_filter_balanced` | merge 전 noise component filtering 적용 |
| `candidate_recall_balanced` | 작은 target 보존을 위한 padding/margin 강화 |
| `baseline_recall` | recall upper bound |

### Keep 기준

- UA-DETRAC에서 candidate ROI count와 large merged ROI/fallback frame rate가 감소한다.
- UA-DETRAC target GT ROI containment가 `baseline_balanced`보다 개선된다.
- PhysicalAI에서 target GT ROI containment가 `baseline_balanced`보다 악화되지 않고 가능하면 개선된다.
- missed target GT count와 no-ROI target frame count가 줄어든다.
- effective input area reduction이 fallback 때문에 0으로 무너지는 상황이 해소되거나, Stage A budget 실험이 가능한 후보 ROI 분포가 만들어진다.
- ROI count와 average total ROI area ratio가 baseline보다 안정화된다.
- gate latency가 허용 범위 안에 있다.

### Tune/Disable/Remove 기준

- UA-DETRAC noise는 줄지만 PhysicalAI 작은 target miss가 늘면 Tune 또는 dataset별 profile 분리
- UA-DETRAC large merged ROI는 줄지만 target GT containment가 개선되지 않으면 Tune
- 특정 dataset에서만 유효하면 Disable 가능 상태로 유지
- latency가 개선되지 않고 복잡도만 늘면 Remove

## 6. Stage A: ROI Budget / Fallback Policy

### 선행 조건

Stage A0에서 candidate ROI 품질 개선안을 Keep 또는 Tune 가능한 상태로 확정한다. Budget policy는 정리된 candidate ROI를 입력으로 받을 때만 실험한다.

### 가설

ROI 후보 품질이 안정화된 뒤에도 ROI가 여러 개로 늘어나는 구간에서는 crop 면적이 줄어도 detector 호출 비용이 full-frame보다 커질 수 있다. ROI 개수와 총 ROI 면적을 기준으로 full-frame fallback을 명시적으로 제어하고 decision reason을 기록하면 latency 병목과 fallback 의존을 해석 가능하게 줄일 수 있다.

### 구현 항목

- `roi_budget.enabled` feature flag 추가
- `max_roi_per_frame` 초과 시 full-frame fallback policy를 feature flag 뒤로 이동
- `max_total_roi_area_ratio` 초과 시 full-frame fallback policy를 feature flag 뒤로 이동
- budget decision reason을 `gate_decisions.jsonl`에 기록
- `budget_balanced` config 추가

### 비교 run

| Run | 설명 |
|---|---|
| `candidate_quality_baseline` | Stage A0 확정 profile |
| `budget_balanced` | Stage A0 확정 profile + ROI budget/fallback 적용 |
| `baseline_recall` | recall upper bound |

### Keep 기준

- target GT ROI containment가 Stage A0 확정 profile보다 악화되지 않는다.
- missed target GT count와 no-ROI target frame count가 늘지 않는다.
- effective input area reduction이 유지되거나 개선된다.
- ROI count와 average total ROI area ratio가 budget 안에 들어온다.
- gate latency가 허용 범위 안에 있고, full-frame fallback/check 의존이 과도하게 늘지 않는다.
- E2E pseudo recall은 downstream compatibility 보조 지표로 확인한다.

### Tune/Disable/Remove 기준

- recall은 유지되지만 full-frame fallback이 과도하게 늘면 Tune
- 특정 dataset에서만 유효하면 Disable 가능 상태로 유지
- latency가 개선되지 않고 복잡도만 늘면 Remove

## 7. Stage B: Adaptive Full-frame Refresh

### 가설

Full-frame refresh는 필요하지만 고정 주기일 필요는 없다. Stage A0/A로 candidate quality와 budget policy가 정리된 뒤 scene risk 기반 adaptive refresh를 적용하면 recall은 유지하면서 full-frame check count를 줄일 수 있다.

### 구현 항목

- `adaptive_refresh.enabled` feature flag 추가
- base/min/max refresh interval 추가
- ROI 없음 지속, ROI count 급증, motion density 변화 기반 force refresh
- refresh decision reason을 `gate_decisions.jsonl`에 기록

### 비교 run

| Run | 설명 |
|---|---|
| `baseline_balanced` | 기존 fixed refresh |
| `adaptive_refresh_balanced` | adaptive refresh 적용 |
| `balanced_no_refresh` | refresh 제거 ablation |

### Keep 기준

- target GT ROI containment가 `baseline_balanced` 수준으로 유지된다.
- full-frame check count와 effective input area가 `baseline_balanced`보다 줄어든다.
- no-refresh 대비 target miss case가 충분히 회복된다.
- gate latency 또는 estimated model input cost가 개선된다.
- E2E pseudo recall은 downstream compatibility 보조 지표로 확인한다.

### Tune/Disable/Remove 기준

- recall이 떨어지면 min/max interval과 force refresh 조건을 Tune
- 특정 scene에서만 안정적이면 Disable 가능 상태로 유지
- fixed refresh보다 recall과 비용이 모두 나쁘면 Remove

## 8. Stage C: Tracking-assisted ROI

### 가설

Motion-only ROI는 정지 객체와 느린 객체에 취약하다. 최근 detection을 short-term track으로 유지하면 miss case를 줄일 수 있다.

### 구현 항목

- `tracking_roi.enabled` feature flag 추가
- IoU/centroid 기반 lightweight track memory 추가
- track age, last seen, confidence moving average 관리
- 살아 있는 track 주변 predicted ROI 생성
- motion ROI와 track ROI merge
- track confidence 저하 시 refresh risk 증가

### 비교 run

| Run | 설명 |
|---|---|
| `baseline_balanced` | 기존 balanced |
| `tracking_balanced` | tracking-assisted ROI 적용 |
| `adaptive_refresh_balanced` | refresh 개선만 적용한 비교군 |

### Keep 기준

- primary dataset의 missed target GT count가 줄어든다.
- target GT ROI containment가 개선되거나 baseline과 동일하다.
- ROI count 증가로 gate latency와 effective input area가 악화되지 않는다.
- ROI proposal failure visualization에서 정지/느린 target miss가 줄어든다.
- E2E pseudo-reference miss count는 secondary compatibility 지표로 확인한다.

### Tune/Disable/Remove 기준

- track ROI가 너무 오래 살아 false ROI가 늘면 max age/confidence를 Tune
- latency 악화가 크면 tracking ROI를 restricted class/scene에만 Enable
- miss 감소 없이 ROI count만 늘면 Remove

## 9. Stage D: Combined Policy / ROI Policy Controller

### 가설

Stage A0의 candidate quality 개선, ROI budget, adaptive refresh, tracking-assisted ROI를 함께 적용하면 recall과 비용의 균형이 가장 좋을 수 있다. 다만 고정 config 하나로 모든 scene을 처리하기보다, frame별 ROI 수, 총 ROI 면적, motion density, 최근 miss/fallback pattern을 기준으로 profile 또는 policy branch를 선택하는 controller가 필요할 수 있다.

### 구현 항목

- `combined_balanced` config 추가
- scene state 기반 profile/controller 후보 정리
  - ROI count bucket
  - total ROI area ratio
  - motion density
  - recent fallback/check streak
  - recent miss/failure pattern
- budget, adaptive refresh, tracking ROI 간 decision priority 정리
- decision reason을 report에 요약
- profile summary와 ROI count latency benchmark에 policy label 추가

### 비교 run

| Run | 설명 |
|---|---|
| `baseline_balanced` | 기본 기준 |
| `candidate_quality_baseline` | Stage A0 확정 profile |
| `budget_balanced` | budget 단독 |
| `adaptive_refresh_balanced` | adaptive refresh 단독 |
| `tracking_balanced` | tracking 단독 |
| `combined_balanced` | 전체 조합 |
| `baseline_recall` | recall upper bound |
| `balanced_no_refresh` | refresh ablation |

### Keep 기준

- target GT ROI containment가 유지되거나 개선된다.
- missed target GT count와 ROI proposal failure pattern이 줄어든다.
- ROI count/area budget과 gate latency가 허용 범위 안에 있다.
- full-frame check count와 effective input area가 `baseline_recall`보다 낮다.
- E2E pseudo recall은 regression guard로만 확인한다.

### Tune/Disable/Remove 기준

- 단독 feature보다 조합 성능이 나쁘면 decision priority를 Tune
- 일부 feature가 조합에서만 악화되면 해당 feature만 Disable
- 전체 조합이 baseline 대비 이득이 없으면 combined config는 Remove

## 10. Stage E: Compressed-domain Probe

### 가설

DeepStream과 겹치지 않는 장기 차별점은 pixel-domain ROI보다 bitstream/decoder metadata 기반 upstream gate에 있을 수 있다.

### 구현 항목

- FFmpeg 또는 PyAV로 H.264/H.265 motion vector 접근 가능성 확인
- motion vector 기반 ROI prototype 작성
- frame difference ROI와 noise/coverage 비교
- Jetson/DeepStream pipeline으로 metadata 전달 가능성 조사

### 판정 기준

- simulator에서 안정적으로 motion vector를 읽을 수 있으면 Phase 1.2 후보로 승격
- 로컬 구현 복잡도가 크거나 dataset 지원이 불안정하면 research note로 보류

## 11. 공통 검증 절차

각 stage는 동일한 절차로 검증한다.

1. PhysicalAI 또는 UA-DETRAC 120-frame ROI Proposal quick run 실행
2. target-aware ROI proposal report 생성
3. profile summary 생성
4. ROI count latency benchmark 생성
5. ROI proposal failure visualization과 ROI debug trace 수동 검토
6. E2E Inference quick run으로 downstream compatibility 보조 확인
7. OD-VIRAT Tiny 120-frame annotated-object 보조 run 실행
8. 결과를 `docs/runs/phase1_validation_runs.md` 또는 별도 run log에 기록
9. Keep/Tune/Disable/Remove 판정

## 12. Phase 1.1 완료 조건

Phase 1.1은 다음 중 하나로 종료한다.

### 성공 종료

- `combined_balanced` 또는 단독 policy가 baseline balanced 대비 target GT ROI containment를 유지하거나 개선한다.
- effective model input area, ROI count/area, gate latency 중 하나 이상이 개선된다.
- ROI proposal failure visualization에서 반복 target miss가 줄어든다.
- DeepStream과 겹치지 않는 frontend gate 방향성이 설명 가능하다.
- OD-VIRAT Tiny annotated-object report에서 명확한 regression이 없다.

### 보류 종료

- ROI proposal primary 지표와 E2E/annotated-object 보조 지표 간 해석이 충돌한다.
- MacBook latency로는 판단이 어렵고 NVIDIA/Jetson 측정이 필요하다.
- 구현 복잡도 대비 이득이 작다.

### 제거 종료

- policy가 recall을 악화시킨다.
- latency/call count가 개선되지 않는다.
- input area reduction 외에는 의미 있는 이득이 없다.

보류 또는 제거 판정을 받은 기능은 기본 config에서 꺼둔다. 반복 검증 가능한 evidence가 없으면 Phase 1.1 결과로 채택하지 않는다.
