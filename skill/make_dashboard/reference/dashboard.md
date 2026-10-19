# 대시보드 카드와 데이터 출처

## 인력 현황 탭

| 카드 | 출처 | 비고 |
|---|---|---|
| KPI(재직·휴직·기간제·보직자·평균 근속·평균 나이·입사 1년 미만) | 결과 엑셀 `_data`(피처) | 원본 없이도 표시 |
| 연차 사용률 KPI | 원본 `v_employees_current` | 원본 없으면 숨김 |
| 본부별 인원, 직군 구성, 직급 분포, 근속 분포, 연령대, 고용형태 | `_data` | 직급은 레벨 순 정렬 |
| 월별 근태 추세 | 원본 `v_attendance_monthly` | 월평균 연장근로(선) + 지각 합계(막대) |
| 설문 차원별 평균 | 원본 `hr_surveys`, `hr_survey_questions`, `hr_survey_answers` | 최근 2개 설문 비교 |

## 퇴사 위험 탭

| 카드 | 출처 |
|---|---|
| 밴드 KPI, 분포, 본부·직군별 평균, 산점도 | `_data`의 risk_score·risk_band |
| '높음' 그룹 주요 신호 | `_data` 피처를 표준화한 z의 '높음' 그룹 평균 |
| 직원 표·상세 | `_data` (drivers_plain을 "주요 신호"로 표시) |
| 하단 설명 | `_meta`의 mode·metrics·unavailable |

## 수정 포인트

- HTML/CSS/JS 템플릿: `hrattrition/dashboard.py`의 `TEMPLATE`. 카드 추가는 `<section class="card cN">` + 차트 코드 한 쌍.
- 현황 집계: `hrattrition/overview.py`의 `build_overview` / `_from_raw`.
- 결과 엑셀의 기계용 시트: `hrattrition/report.py`의 `write_result_workbook` / `read_result_workbook`.
