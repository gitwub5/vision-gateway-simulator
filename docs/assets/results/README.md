# Result Assets

GitHub README에서 바로 확인할 수 있도록 `outputs/`의 집계 시각화 중 대표 자료만 복사해 둔 디렉터리입니다. 원본 dataset frame은 재배포 조건을 별도로 확인해야 하므로 포함하지 않습니다.

| 파일 | 내용 |
|---|---|
| `phase1_3_domain_tradeoff.png` | 5개 domain의 best observed profile에 대한 GT recall과 입력/면적 절감 비교 |
| `phase1_3_recommendation_matrix.png` | cross-domain recall, 입력 절감, tracker 계열 ROI count pressure 요약 |

원본 결과가 준비된 환경에서는 저장소 root에서 다음 명령으로 다시 생성할 수 있습니다.

```bash
python experiments/phase1_3/render_phase1_3_visualizations.py
```

생성 위치는 `outputs/visualizations/phase1_3/`입니다. `outputs/`는 Git에서 제외되므로 README에 사용할 최종 집계 그림만 이 디렉터리에 보관합니다.

수치의 출처와 해석상 주의점은 다음 문서를 기준으로 합니다.

- `docs/runs/phase1_3/phase1_3_hybrid_family_600frame_validation_20260917.md`
- `docs/runs/phase1_3/phase1_3_final_domain_recommendation_matrix_20260917.md`
