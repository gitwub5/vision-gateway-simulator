# Phase 1.1 ROI/Gate Policy Implementation Plan

이 문서는 Phase 1.1에서 ROI crop/gate policy를 개선하기 위한 공유 구현 계획이다.

Phase 1.1의 목표는 ROI crop 면적을 무조건 줄이는 것이 아니다. 객체 보존 성능을 유지하면서 detector 호출 비용, ROI 다중 호출 병목, full-frame refresh 비용을 줄일 수 있는지 검증한다.

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

### 2.2 Stage A: ROI Budget / Fallback Policy

- [ ] `roi_budget.enabled` feature flag 추가
- [ ] `max_roi_per_frame` 초과 시 full-frame fallback 구현
- [ ] `max_total_roi_area_ratio` 초과 시 full-frame fallback 구현
- [ ] 가까운 ROI merge 구현 또는 기존 merge policy 확장
- [ ] 너무 작은 ROI 제거 또는 minimum padding 처리
- [ ] budget decision reason을 `gate_decisions.jsonl`에 기록
- [ ] `budget_balanced` config 추가
- [ ] baseline balanced 대비 Construction Site Static Camera quick run 비교
- [ ] OD-VIRAT Tiny annotated-object 보조 run 비교
- [ ] ROI count latency benchmark 생성
- [ ] Keep/Tune/Disable/Remove 판정 기록

### 2.3 Stage B: Adaptive Full-frame Refresh

- [ ] `adaptive_refresh.enabled` feature flag 추가
- [ ] base/min/max refresh interval config 추가
- [ ] ROI 없음 지속 기반 force refresh 구현
- [ ] ROI count 급증 기반 force refresh 구현
- [ ] motion density 변화 기반 force refresh 구현
- [ ] refresh decision reason을 `gate_decisions.jsonl`에 기록
- [ ] `adaptive_refresh_balanced` config 추가
- [ ] fixed refresh/no-refresh 대비 Construction Site Static Camera quick run 비교
- [ ] OD-VIRAT Tiny annotated-object 보조 run 비교
- [ ] Keep/Tune/Disable/Remove 판정 기록

### 2.4 Stage C: Tracking-assisted ROI

- [ ] `tracking_roi.enabled` feature flag 추가
- [ ] IoU/centroid 기반 lightweight track memory 구현
- [ ] track age, last seen, confidence moving average 관리
- [ ] 살아 있는 track 주변 predicted ROI 생성
- [ ] motion ROI와 track ROI merge
- [ ] track confidence 저하 시 refresh risk 증가
- [ ] `tracking_balanced` config 추가
- [ ] failure visualization에서 정지/느린 객체 miss 감소 여부 확인
- [ ] Keep/Tune/Disable/Remove 판정 기록

### 2.5 Stage D: Combined Policy

- [ ] `combined_balanced` config 추가
- [ ] budget, adaptive refresh, tracking ROI 간 decision priority 정리
- [ ] decision reason을 report에 요약
- [ ] profile summary에 policy label 추가
- [ ] ROI count latency benchmark에 policy label 추가
- [ ] full matrix 실행
  - [ ] `baseline_balanced`
  - [ ] `budget_balanced`
  - [ ] `adaptive_refresh_balanced`
  - [ ] `tracking_balanced`
  - [ ] `combined_balanced`
  - [ ] `baseline_recall`
  - [ ] `balanced_no_refresh`
- [ ] Phase 1.1 최종 Keep/Tune/Disable/Remove 판정

### 2.6 Stage E: Compressed-domain Probe

- [ ] FFmpeg 또는 PyAV로 motion vector 접근 가능성 확인
- [ ] motion vector 기반 ROI prototype 작성 여부 결정
- [ ] frame difference ROI와 noise/coverage 비교
- [ ] Jetson/DeepStream pipeline metadata 전달 가능성 조사
- [ ] Phase 1.2 후보 승격 또는 research 보류 판정

### 2.7 문서화

- [ ] 구현 결과를 `docs/tasks/phase1_1/` 아래에 task 문서로 정리
- [ ] 실행 결과 위치를 `docs/runs/`에 기록
- [ ] 공유 가능한 결론은 `docs/plan/` 또는 README에 반영
- [ ] 비공개 기술 판단은 `docs/idea/`에 유지
- [ ] 제거 또는 비활성화한 feature의 이유 기록

## 3. Baseline

기본 baseline은 Phase 1 결과의 `Construction Site Static Camera + balanced profile`로 둔다.

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

따라서 이 데이터의 annotation metric은 "실제 전체 객체 recall"이 아니라 annotated-object lower-bound check로 해석한다. Phase 1.1 Keep/Tune/Disable/Remove의 hard criterion은 primary dataset의 pseudo recall, ROI count latency, failure visualization을 우선한다.

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

## 5. Stage A: ROI Budget / Fallback Policy

### 가설

ROI가 여러 개로 늘어나는 구간에서는 crop 면적이 줄어도 detector 호출 비용이 full-frame보다 커질 수 있다. ROI 개수와 총 ROI 면적을 기준으로 full-frame fallback 또는 ROI merge를 적용하면 latency 병목을 줄일 수 있다.

### 구현 항목

- `roi_budget.enabled` feature flag 추가
- `max_roi_per_frame` 초과 시 full-frame fallback
- `max_total_roi_area_ratio` 초과 시 full-frame fallback
- 가까운 ROI merge
- 너무 작은 ROI 제거 또는 minimum padding 적용
- ROI budget decision을 `gate_decisions.jsonl`에 기록

### 비교 run

| Run | 설명 |
|---|---|
| `baseline_balanced` | 기존 balanced |
| `budget_balanced` | ROI budget/fallback 적용 |
| `baseline_recall` | recall upper bound |

### Keep 기준

- pseudo recall이 `baseline_balanced`보다 크게 낮아지지 않는다.
- ROI count `2-3`, `4-5`, `6-8` bucket의 latency delta가 개선된다.
- input area reduction이 `baseline_recall`보다 높다.
- Construction Site Static Camera failure visualization에서 반복 miss pattern이 늘지 않는다.
- OD-VIRAT Tiny annotated-object recall/containment가 악화되지 않는지 보조 확인한다.

### Tune/Disable/Remove 기준

- recall은 유지되지만 full-frame fallback이 과도하게 늘면 Tune
- 특정 dataset에서만 유효하면 Disable 가능 상태로 유지
- latency가 개선되지 않고 복잡도만 늘면 Remove

## 6. Stage B: Adaptive Full-frame Refresh

### 가설

Full-frame refresh는 필요하지만 고정 주기일 필요는 없다. scene risk 기반 adaptive refresh를 적용하면 recall은 유지하면서 full-frame check count를 줄일 수 있다.

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

- pseudo recall이 `baseline_balanced` 수준으로 유지된다.
- full-frame check count가 `baseline_balanced`보다 줄어든다.
- no-refresh 대비 miss case가 충분히 회복된다.
- latency 또는 detector call count가 개선된다.
- OD-VIRAT Tiny annotated-object recall/containment가 악화되지 않는지 보조 확인한다.

### Tune/Disable/Remove 기준

- recall이 떨어지면 min/max interval과 force refresh 조건을 Tune
- 특정 scene에서만 안정적이면 Disable 가능 상태로 유지
- fixed refresh보다 recall과 비용이 모두 나쁘면 Remove

## 7. Stage C: Tracking-assisted ROI

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

- primary dataset의 pseudo-reference miss count가 줄어든다.
- pseudo recall이 개선되거나 baseline과 동일하다.
- ROI count 증가로 latency가 악화되지 않는다.
- failure visualization에서 정지/느린 객체 miss가 줄어든다.
- OD-VIRAT Tiny missed annotated object count가 줄어드는지 보조 확인한다.

### Tune/Disable/Remove 기준

- track ROI가 너무 오래 살아 false ROI가 늘면 max age/confidence를 Tune
- latency 악화가 크면 tracking ROI를 restricted class/scene에만 Enable
- miss 감소 없이 ROI count만 늘면 Remove

## 8. Stage D: Combined Policy

### 가설

ROI budget, adaptive refresh, tracking-assisted ROI를 함께 적용하면 recall과 비용의 균형이 가장 좋을 수 있다.

### 구현 항목

- `combined_balanced` config 추가
- budget, adaptive refresh, tracking ROI 간 decision priority 정리
- decision reason을 report에 요약
- profile summary와 ROI count latency benchmark에 policy label 추가

### 비교 run

| Run | 설명 |
|---|---|
| `baseline_balanced` | 기본 기준 |
| `budget_balanced` | budget 단독 |
| `adaptive_refresh_balanced` | adaptive refresh 단독 |
| `tracking_balanced` | tracking 단독 |
| `combined_balanced` | 전체 조합 |
| `baseline_recall` | recall upper bound |
| `balanced_no_refresh` | refresh ablation |

### Keep 기준

- pseudo recall이 유지된다.
- ROI count latency benchmark에서 다중 ROI bucket의 latency가 개선된다.
- full-frame check count가 `baseline_recall`보다 낮다.
- input area reduction이 `baseline_recall`보다 높다.
- failure visualization에서 반복 miss pattern이 줄어든다.
- OD-VIRAT Tiny annotated-object recall/containment는 regression guard로만 확인한다.

### Tune/Disable/Remove 기준

- 단독 feature보다 조합 성능이 나쁘면 decision priority를 Tune
- 일부 feature가 조합에서만 악화되면 해당 feature만 Disable
- 전체 조합이 baseline 대비 이득이 없으면 combined config는 Remove

## 9. Stage E: Compressed-domain Probe

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

## 10. 공통 검증 절차

각 stage는 동일한 절차로 검증한다.

1. Construction Site Static Camera 120-frame quick run 실행
2. pseudo-reference report 생성
3. profile summary 생성
4. ROI count latency benchmark 생성
5. failure visualization 수동 검토
6. OD-VIRAT Tiny 120-frame annotated-object 보조 run 실행
7. annotation report와 pseudo-reference report를 함께 확인
8. 결과를 `docs/runs/phase1_validation_runs.md` 또는 별도 run log에 기록
9. Keep/Tune/Disable/Remove 판정

## 11. Phase 1.1 완료 조건

Phase 1.1은 다음 중 하나로 종료한다.

### 성공 종료

- `combined_balanced` 또는 단독 policy가 baseline balanced 대비 pseudo recall을 유지한다.
- detector invocation cost 또는 ROI count latency가 개선된다.
- failure visualization에서 반복 miss가 줄어든다.
- DeepStream과 겹치지 않는 frontend gate 방향성이 설명 가능하다.
- OD-VIRAT Tiny annotated-object report에서 명확한 regression이 없다.

### 보류 종료

- pseudo-reference와 annotated-object 보조 지표 간 해석이 충돌한다.
- MacBook latency로는 판단이 어렵고 NVIDIA/Jetson 측정이 필요하다.
- 구현 복잡도 대비 이득이 작다.

### 제거 종료

- policy가 recall을 악화시킨다.
- latency/call count가 개선되지 않는다.
- input area reduction 외에는 의미 있는 이득이 없다.

보류 또는 제거 판정을 받은 기능은 기본 config에서 꺼둔다. 반복 검증 가능한 evidence가 없으면 Phase 1.1 결과로 채택하지 않는다.
