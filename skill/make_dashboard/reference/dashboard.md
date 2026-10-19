# 대시보드(HR 리스크 터미널) 패널과 데이터 출처

외부 리소스 없음(인라인 SVG). 색은 상태색(critical/warning/good)과 발산 스케일(파랑↔회색↔빨강)에만 뜻이 있고, 범주색은 파랑 하나와 회색 단계만 쓴다. 숫자는 tabular-nums.

| 패널 | 출처 | 비고 |
|---|---|---|
| 상태줄 6단계(Q D H V A R) | 결과 엑셀 `1 질문 정의`, `4 검증`(종합), `3 가설`, `5 팀별 확인사항` 존재 여부 | 검증 종합이 경고/실패면 V 등이 황/적 |
| 레일 트리·히어로 | `_data`의 division_name / org_unit_name / risk_band / risk_score | 히트셀 = 평균 위험(≥.7 빨강, ≥.4 황, 그 외 파랑) |
| 신호 보드 | `_data` 피처 + `_meta` metrics.coefficients | σ = 선택 범위 평균의 회사 대비 표준화 편차(위험 방향 부호). 전체 선택 시 생략. ≠ = 모델 계수 부호 ≠ 가설 방향 |
| 가설 | `3 가설` 시트 | 판정 칩, 가장 강한 신호의 AUC(라벨 있을 때) 또는 두드러진 인원 비율 |
| 팀×신호 히트맵 | `_data` 피처를 회사 전체에서 표준화한 z의 팀 평균 × 위험 방향 | 방향 0(참고) 신호는 진단 모드에서 제외, 예측 모드에서는 계수 부호 사용. 셀 호버로 값 |
| 워치리스트 | `_data` + 원본 `v_attendance_monthly`(스파크라인) | 체크 상태는 localStorage(이 브라우저만). P4에서 실행 관리로 승격 예정 |
| 검증·조치·팀별 | `4 검증`, `회사 전체 신호`, `조치 제안`, `5 팀별 확인사항` 시트 | 팀별 행 클릭 = 해당 팀 필터 |
| 구성 | `_data` (선택 범위) | 근속 구간·직급·고용형태·휴직·보직 |
| 월별 추세·설문 | 원본 `v_attendance_monthly`, `hr_surveys`/`hr_survey_questions`/`hr_survey_answers` | 기준일 이후 월·설문 제외. 축은 하나씩(소형 다중), 리커트 1~5와 eNPS 분리 |
| 드로어 | `_data`, `_meta`, SOURCE_TABLE | 불릿 = 위험 방향 z(가운데 선 = 회사 평균), 값의 출처 테이블은 라벨 호버 |

## 키보드

`/` 검색 · `↑↓` 워치리스트 이동 · `Enter` 상세 · `Esc` 드로어/필터 해제 · `1`/`2`/`3` 밴드 높음/주의/낮음 토글 · `s` 공유용(이름·사번 가림)

## 수정 포인트

- 템플릿(CSS/HTML/JS): `hrattrition/dashboard.py`의 `TEMPLATE`. 패널 추가는 `<section class="panel cN">` + 렌더 함수 한 쌍, `renderAll()`에 등록.
- 히트맵 열 머리글 약어: `dashboard.py`의 `SHORT`.
- 현황 집계·스파크라인: `hrattrition/overview.py`.
- 결과 엑셀에서 읽는 부가 정보: `hrattrition/report.py`의 `read_result_extras`.
