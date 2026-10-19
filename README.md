# HR 퇴사 위험 분석 스킬 2종 — predict_attrition / make_dashboard

HR 담당자가 claude.ai(채팅·Claude for Work)에 HR 엑셀 한 파일을 첨부해 쓰는 두 개의 스킬. 같은 SKILL.md를 Claude Code 플러그인(`hr-attrition`)으로도 쓴다.

| 스킬 | 입력 | 출력 |
|---|---|---|
| `/predict_attrition` | HR xlsx 한 파일(표준 HR 워크북 또는 직원 명부 한 장) | **퇴사위험_결과.xlsx**(1 질문 정의 · 요약 · 2 데이터 이해/이슈 · 3 가설 · 4 검증 · 5 팀별 확인사항 · 직원별 위험 · 팀별 · 회사 전체 신호 · 조치 제안 · 신호 상세 · 신호 설명 + 기계용 `_data`/`_meta`), summary.json, **analysis_spec.json**(재사용), scores.csv, features.csv, metrics.json |
| `/make_dashboard` | 퇴사위험_결과.xlsx (+ 원본 HR xlsx 권장) | **dashboard.html**: '인력 현황' 탭(인원 구조·근속·연령·고용형태, 원본이 있으면 월별 근태 추세·설문) + '퇴사 위험' 탭(밴드·분포·팀별·산점도·주요 신호·직원 표·상세) |

## 방법론: 질문 → 데이터 → 가설 → 검증 → 행동 → 재사용

`/predict_attrition`은 어떤 요청이 와도 여섯 단계로 진행하고 각 단계의 산출물을 남긴다(`skill/predict_attrition/reference/methodology.md`).

| 단계 | 엔진 모듈 | 산출물 |
|---|---|---|
| 1 질문 정의(대상·기간·모집단) | `question.py` (`--target --horizon-days --filter --prompt`) | `1 질문 정의` 시트, `summary.question` |
| 2 데이터 이해(테이블 의미·누락·중복·기간, 기준일 이후 기록 제외) | `profile.py`, `features.py`(cutoff) | `2 데이터 이해`, `2 데이터 이슈` |
| 3 가설 수립·탐색(H1~H9, 라벨 있으면 단변량 AUC) | `hypotheses.py` | `3 가설` |
| 4 검증(누수·반례·산정 방식·순위 안정성·한계) | `validation.py` | `4 검증` |
| 5 행동 연결(회사 신호·조치, 팀별 HR 확인 사항, 상위 직원) | `report.py` | `5 팀별 확인사항`, `조치 제안` 등 |
| 6 재사용(질문·가중치·입력 조건·절차·검증 기준·출력 양식) | `report.write_analysis_spec` (`--spec`로 재실행) | `analysis_spec.json` |

## 구성

```
hr_attrition_plugin/
├── engine/hrattrition/              공용 엔진(한 곳에서 관리, zip 생성 시 각 스킬에 동봉)
│   ├── data.py       xlsx 워크북 / 직원 명부 한 장 / 폴더 로더, 컬럼 별칭, 필요한 시트만 읽기
│   ├── features.py   신호 31개 + 설명 + 평이한 표현(PLAIN)
│   ├── model.py      규칙 기반 지수 / 로지스틱 회귀 / 요인 설명
│   ├── report.py     summary.json, 퇴사위험_결과.xlsx 쓰기·읽기(_data/_meta)
│   ├── overview.py   인력 현황 집계(결과 파일 + 선택적 원본)
│   ├── dashboard.py  두 탭 Chart.js 단일 HTML
│   └── cli.py        predict | dashboard | run
├── skill/predict_attrition/         SKILL.md, scripts/predict_attrition.py, reference/(features·interpretation·labels)
├── skill/make_dashboard/            SKILL.md, scripts/make_dashboard.py, reference/dashboard.md
├── .claude-plugin/                  Claude Code 플러그인 매니페스트, 로컬 마켓플레이스 "tpc-hr"
├── agents/hr-analyst.md             Claude Code용 분석가 서브에이전트
├── tests/test_pipeline.py
├── make_skill_zip.py                → dist/predict_attrition.zip, dist/make_dashboard.zip
└── artifacts/                       로컬 실행 산출물(git 제외)
```

## claude.ai에 올리기

```bash
python make_skill_zip.py
```

`dist/predict_attrition.zip`, `dist/make_dashboard.zip`을 claude.ai → 설정 → 기능(Capabilities) → Skills에 각각 업로드한다. Claude for Work는 관리자가 조직에 배포한다.
샌드박스 요구: pandas·numpy·openpyxl(모델 모드만 scikit-learn). 두 zip 모두 엔진을 동봉하므로 서로 없어도 동작한다(`/make_dashboard`는 결과 엑셀이 없으면 예측부터 수행).

## 로컬 실행

```bash
pip install -e ".[dev]"
python skill/predict_attrition/scripts/predict_attrition.py --input ~/project_tpc/offpiste_synthetic_HR_data/output/it_platform/synthetic_hr_it_platform.xlsx --out artifacts/it_platform
python skill/make_dashboard/scripts/make_dashboard.py --result artifacts/it_platform/퇴사위험_결과.xlsx --data ~/project_tpc/offpiste_synthetic_HR_data/output/it_platform/synthetic_hr_it_platform.xlsx --out artifacts/it_platform --open
python -m pytest tests -q
```

Claude Code: `/predict_attrition <xlsx 경로>`, `/make_dashboard <결과 xlsx> <원본 xlsx>`. 로컬 설치는 `claude plugin marketplace add ~/project_tpc/hr_attrition_plugin` 후 `claude plugin install hr-attrition@tpc-hr`, 저장소 배포 뒤에는 `/plugin install hr-attrition --marketplace <owner>/<repo>`.

## 모드

| 모드 | 조건 | 결과 |
|---|---|---|
| 규칙 기반 지수 | 라벨 없음(기본) | 신호별 공개 가중치 × 표준화 값의 합을 0~1로 누른 회사 내 상대 지수. 높음 ≥0.7(상위 15% 안팎), 주의 ≥0.4. **예측 확률 아님.** |
| 예측 모델 | `퇴사라벨` 시트/`퇴사여부` 컬럼/`--labels`, 양성·음성 각 10명 이상 | 로지스틱 회귀, 교차검증 AUC·계수 기록 |

성별·국적·체류자격·혼인·가족·주거·거주지·병역은 어떤 모드에서도 쓰지 않는다.

## 한계

- 합성 데이터셋에는 퇴사 라벨이 없어 기본은 규칙 기반 지수다. 라벨은 외부에서 공급해야 한다.
- 단면(기준일 하나) 분석이다. 시점 비교는 아직 없다.
