# HR Attrition Skills

**HR 엑셀 한 장을 올리면, 퇴사 관련 신호를 진단하고 근거와 함께 돌려주는 Claude 스킬 2종.**

> **30초 시작**
> 1. `dist/predict_attrition.zip`과 `dist/make_dashboard.zip`을 claude.ai → 설정 → Skills에 업로드
> 2. 새 대화에 HR xlsx를 첨부하고 **"퇴사 위험 분석해줘"**
> 3. 결과 엑셀을 받은 뒤 **"대시보드 만들어줘"**

v0.4.0 · 2 skills · 31 signals · 9 hypotheses · 9 validation checks · 한국어 우선

---

## 왜 만들었나

HR 담당자는 데이터 과학자가 아니고, 가진 것은 인사 시스템에서 내려받은 엑셀 한 장입니다. 그 파일로 "누가 위험한가"를 묻는 순간 AI 도구들은 세 가지 방식으로 실패합니다.

**1. 예측인 척하는 숫자.** 실제 퇴사 기록이 없는데 "퇴사 확률 73%"를 보여줍니다. 이 스킬은 라벨이 없으면 **진단 모드**로만 동작하고, "90일 내 퇴사 여부는 예측하지 않는다"고 결과에 적습니다. 라벨 시트가 있을 때만 예측 모드로 바뀌며, 그때도 무작위 교차검증은 출시 근거가 아니라고 함께 적습니다.

**2. 보이지 않는 편향.** 성별·국적·혼인·거주지가 "그냥 컬럼"으로 모델에 들어갑니다. 이 스킬은 민감 속성을 **엔진 수준에서 차단**합니다. 피처 테이블에 실리지 않고, 가중치로 지정할 수 없고, 섞여 들어오면 계산이 멈춥니다. 병가와 설문 미응답도 개인 점수에서 뺍니다.

**3. 검증 없는 "통과".** 보고서의 체크 표시가 상수로 적혀 있습니다. 이 스킬의 검증 9개 항목은 **실제 검사로 상태를 산출**합니다. 날짜 컬럼이 없으면 "평가 불가", 날짜를 못 읽은 행이 있으면 "경고", 민감 컬럼이 들어오면 "실패"입니다.

그리고 어떤 요청이 오든 같은 여섯 단계로 일합니다. **질문 정의 → 데이터 이해 → 가설 → 검증 → 행동 연결 → 재사용.** 각 단계의 산출물이 결과 엑셀의 시트로 남아서, 다음 달에 같은 질문을 같은 설정으로 다시 돌릴 수 있습니다.

## 무엇이 들어 있나

| 스킬 | 입력 | 출력 |
|---|---|---|
| **[`/predict_attrition`](./skill/predict_attrition/SKILL.md)** | HR xlsx 한 파일 | `퇴사위험_결과.xlsx` + 여섯 단계 한 줄 요약, 핵심 발견, HR이 확인할 일 |
| **[`/make_dashboard`](./skill/make_dashboard/SKILL.md)** | 결과 xlsx (+ 원본 xlsx) | `dashboard.html` — 인력 현황 탭 + 퇴사 위험 탭 |

Claude Code에서는 분석가 서브에이전트 [`hr-analyst`](./agents/hr-analyst.md)도 함께 설치됩니다.

### 여섯 단계가 만드는 것

| 단계 | 하는 일 | 결과 엑셀 시트 |
|---|---|---|
| 1 질문 정의 | 요청한 질문과 지금 데이터로 답할 수 있는 질문을 둘 다 기록. 기본값 "자발적 퇴사 / 90일 / 재직자 전원" | `1 질문 정의` |
| 2 데이터 이해 | 선검사(기준일·사번·구조·날짜) → 테이블 의미·커버리지·결측 → 기준일 이후 기록 제외 | `2 데이터 이해`, `2 데이터 이슈` |
| 3 가설 | H1 연장근로 ~ H9 온콜·휴가 반려. 라벨 있으면 단변량 AUC 판정, 없으면 탐색적 증거 | `3 가설` |
| 4 검증 | 9개 항목을 pass / warn / fail / not_evaluable / not_applicable + 근거 ID로 | `4 검증` |
| 5 행동 연결 | 회사 전체 신호와 조치, 팀별 두드러진 신호와 HR 확인 질문 | `5 팀별 확인사항`, `조치 제안` |
| 6 재사용 | 질문·모드·가중치·밴드·피처 정책·엔진 버전을 `analysis_spec.json`에 | — |

그 뒤로 `직원별 위험`, `팀별`, `회사 전체 신호`, `신호 상세`, `신호 설명` 시트가 이어지고, 끝의 `_data`·`_meta`는 대시보드 스킬이 읽는 기계용 시트입니다.

### 31개 신호

보상(밴드 내 위치·인상 후 개월·인상률), 승진(보류 횟수·승진 후 개월), 평가(최근 등급·추세·자기평가 차이), 근태(월평균 연장·연장 추세·지각·결근), 설문(몰입·보상 인식·워라밸·eNPS), 계약(기간제·만료 임박), 근속·직급·보직. 전체 목록과 계산 방식은 [`features.md`](./skill/predict_attrition/reference/features.md), 신호별 평이한 해석과 조치 예시는 [`interpretation.md`](./skill/predict_attrition/reference/interpretation.md)에 있습니다.

## 설치

<details>
<summary><strong>claude.ai / Claude for Work</strong> (주 사용 환경)</summary>

```bash
python make_skill_zip.py --check
```

`dist/predict_attrition.zip`, `dist/make_dashboard.zip`을 claude.ai → 설정 → 기능(Capabilities) → Skills에 각각 업로드합니다. Claude for Work는 관리자가 조직에 배포할 수 있습니다. 두 zip 모두 엔진을 동봉해 서로 없어도 동작하며, 샌드박스에는 pandas·numpy·openpyxl만 있으면 됩니다(예측 모드만 scikit-learn).

</details>

<details>
<summary><strong>Claude Code</strong></summary>

```bash
claude plugin marketplace add ~/project_tpc/hr_attrition_plugin
claude plugin install hr-attrition@tpc-hr
```

또는 GitHub 저장소에서 바로:

```
/plugin install hr-attrition --marketplace jj-tpc/tpc-hr-plugin
```

세션 안에서 `/predict_attrition <xlsx 경로>`, `/make_dashboard <결과 xlsx> <원본 xlsx>`. 로컬 폴더로 설치했으면 SKILL.md를 고친 뒤 다음 세션(또는 `/reload-plugins`)에 반영됩니다.

</details>

<details>
<summary><strong>로컬 CLI</strong> (개발·검증)</summary>

```bash
pip install -e ".[dev]"
python skill/predict_attrition/scripts/predict_attrition.py --input <HR.xlsx> --out artifacts/run1
python skill/make_dashboard/scripts/make_dashboard.py --result artifacts/run1/퇴사위험_결과.xlsx --data <HR.xlsx> --out artifacts/run1 --open
```

Windows 콘솔에서는 `PYTHONUTF8=1`을 켜고 실행합니다.

</details>

## 사용 예

채팅에서:

```
(HR xlsx 첨부) 퇴사 위험 분석해줘
(HR xlsx 첨부) 개발팀 이탈이 걱정되는데 어디부터 봐야 해?
검증 자세히 보여줘
데이터·AI팀만 보여줘                 ← 재실행 없이 표시 필터
(결과 xlsx + 원본 첨부) 대시보드 만들어줘
```

CLI에서 질문 정의와 재사용:

```bash
# 기준 모집단을 개발직으로 제한, 기간 180일, 요청 원문 기록
python skill/predict_attrition/scripts/predict_attrition.py --input HR.xlsx --out artifacts/dev \
  --filter 직군=개발직 --horizon-days 180 --prompt "개발팀에서 누가 나갈 것 같은지"

# 다음 달: 같은 설정으로 (명시적 인자가 스펙보다 우선)
python skill/predict_attrition/scripts/predict_attrition.py --input HR_next.xlsx --out artifacts/dev2 --spec artifacts/dev/analysis_spec.json
```

최초 결과는 여섯 줄로 옵니다.

```
1 질문 정의: 기준일 2026-10-16 현재 재직자 전원의 퇴사 관련 신호를 진단한다. 라벨이 없어 '90일 이내 자발적 퇴사' 여부는 예측하지 않는다.
2 데이터 이해: 테이블 15개 · 모집단 100/100명 · 계산 못 한 신호 0개 · 선검사 경고 0건 · 기준일 이후 제외 0행
3 가설: 탐색적 증거(라벨 없음) — 설문 몰입도 낮음, 보상 밴드 하단, 평가 하락이 두드러짐
4 검증: 종합 통과 — V9 정확도 검증은 라벨이 없어 평가 불가
5 행동 연결: 고객경험팀·마케팅팀 평균 위험 상위, 확인할 것: 관리자 1:1, 보상 밴드 위치
6 재사용: analysis_spec.json 저장
```

## 입력 파일

두 형식을 자동 인식합니다.

- **표준 HR 워크북** — `hr_employees`, `v_employees_current`, `hr_compensation_history`, `hr_performance_reviews`, `v_attendance_monthly`, `hr_survey_*` 시트. 일부가 없어도 되며 없는 시트에 기대는 신호만 빠집니다.
- **직원 명부 한 장** — 첫 시트에 1인 1행. 사번·이름·부서·직급·입사일·연봉·최근 평가 등을 한글/영문 별칭으로 인식합니다. 명부에는 기준일이 없으므로 `--as-of`를 지정합니다.

`퇴사라벨`(또는 `labels`) 시트에 `employee_id, left`가 있으면 예측 모드로 전환됩니다. 형식은 [`labels.md`](./skill/predict_attrition/reference/labels.md).

> [!NOTE]
> 기준일은 파일의 명시적 값(개요 시트 '기준일' 또는 스냅샷 `as_of`)만 씁니다. 없거나 충돌하면 멈추고 `--as-of`를 요구합니다. 오늘 날짜를 조용히 적용하지 않습니다. 사번이 중복되거나 비어 있어도 멈추고 `diagnostics.json`에 해결 방법을 남깁니다.

### 샘플 데이터

| 파일 | 내용 |
|---|---|
| `fixtures/hr_fixture_186.xlsx` | 합성 186명, 기준일 2026-04-30, 이후 180일 퇴사 58명과 `퇴사라벨` 시트 → **예측 모드** 경로 확인용. `python tools/make_fixture.py`로 재생성 |
| `../offpiste_synthetic_HR_data/output/<preset>/synthetic_hr_<preset>.xlsx` | IT 플랫폼 / 자동차 전장 제조, 현재 재직자 100명, 라벨 없음 → **진단 모드** |

픽스처는 난수에 약한 신호 편향을 심은 것이라 처리 경로 검증용이며, 모델 성능 근거로 쓸 수 없습니다.

## 하지 않는 것

- **라벨 없이 확률을 말하지 않습니다.** 진단 모드의 지수(0~1)는 공개 가중치로 신호를 합친 회사 내 상대 순위입니다.
- **민감 속성을 쓰지 않습니다.** 성별·국적·체류자격·혼인·가족·주거·거주지·병역·생년월일은 어떤 경로(규칙·모델·가중치 override·필터)로도 들어갈 수 없습니다. 병가·설문 미응답은 조직 집계에만 씁니다.
- **개인을 단정하지 않습니다.** 신호는 "확인해 볼 지점"이고 기본 답변은 조직 단위입니다. 개인 목록은 요청이 있을 때만.
- **대화에서 숫자를 만들지 않습니다.** 모든 수치·가중치·근거는 엔진 산출물에서만 옵니다.
- **입력 파일을 수정하지 않습니다.** 실행별 출력 폴더에만 씁니다.

## 검증 9항목

| ID | 항목 | 상태가 정해지는 방식 |
|---|---|---|
| V1 | 기준일 출처 | 파일 명시값 또는 사용자 지정 → pass, 없음 → fail |
| V2 | 기준일 이후 정보 제외 | 날짜 컬럼 검사 후 이후 행 제외 → pass, 못 읽은 날짜 있음 → warn, 날짜 컬럼 없음 → not_evaluable |
| V3 | 민감 속성·제외 신호 미사용 | 피처 테이블·실제 사용 신호 대조, 발견 시 fail |
| V4 | 점수 산정 방식 공개 | 가중치·근속 가산·scale·밴드 또는 알고리즘·AUC·양성 수 |
| V5 | 반례 확인 | "강한 신호인데 낮음" / "높음인데 강한 신호 없음" 건수·예시 |
| V6 | 순위 안정성 | 신호 하나 제거 시 순위 상관 ≥ 0.8 → pass, 미만 → warn. 모델 모드 not_applicable |
| V7 | 사용 신호 커버리지 | 50% 미만 신호 있으면 warn |
| V8 | 입력 선검사 | 경고 이슈 있으면 warn |
| V9 | 정확도 검증 | 라벨 없음 → not_evaluable. 있어도 무작위 CV는 warn(시간 분리 평가 아님) |

## 재현성

`analysis_spec.json`에 계산 설정 전체(질문, 요청/적용 모드, 가중치 22개, 근속 가산, scale, 밴드, 피처 정책, 엔진 버전)가 들어가고, `run_manifest.json`에 실행별 값(입력 해시, 스펙 해시, 실행 시각, 경고)이 분리되어 들어갑니다. 같은 입력·스펙·엔진이면 점수와 밴드가 같습니다. 설정 우선순위는 **명시적 CLI > 스펙 > 기본값**이고, 다른 minor 버전의 스펙은 오류로 거부합니다.

## 로드맵

[`Docs/HANDOFF_HR_RETENTION_UPGRADE_2026-10-19.md`](./Docs/HANDOFF_HR_RETENTION_UPGRADE_2026-10-19.md)의 순서를 따릅니다. 첫 고도화 출시의 대표 기능은 **전월 대비 조직 변화 + 원본 근거 + HR 확인사항**입니다.

| 단계 | 상태 | 내용 |
|---|---|---|
| P0 신뢰성 | ✅ v0.4.0 | 실제 검증 상태, 입력 선검사, 민감 속성 경로 폐쇄, 스펙 완전 재현, 버전 단일화, 진단/예측 표현 분리 |
| P1 엑셀 수용력·근거 | 예정 | 헤더 위치·단위·사번 형식·시트명 변화 처리, 애매한 매핑은 질문으로, 모든 수치에 원본 셀 근거 ID |
| P2 월별 변화 | 예정 | 두 스냅샷 비교, 동일 재직자 변화 vs 입·퇴사 구성 변화, 비교 기준 버전 고정 |
| P3 업무 시트·대화 | 예정 | 이번 달 요약 / 조직별 변화 / 근거 상세 / 실행 관리, 공유용·HR용 분리 |
| P4 실행 기록 | 예정 | HR 확인·조치 기록을 다음 달로 이어받기 |
| P5 예측 모드 | 별도 | 실제 라벨·시간 분리 평가·기준선 비교 후에만 활성화 |

## 프로젝트 구조

```
hr_attrition_plugin/
├── engine/hrattrition/          공용 엔진 (단일 원천, zip 생성 시 각 스킬에 동봉)
│   ├── data.py       xlsx 워크북 / 명부 한 장 / 폴더 로더, 컬럼 별칭
│   ├── precheck.py   입력 선검사 (기준일·사번·구조·날짜)
│   ├── features.py   신호 31개, 기준일 이후 기록 제외, 허용 피처 강제
│   ├── question.py   질문 정의, 분석 모드, 기준 모집단 제한
│   ├── profile.py    데이터 이해
│   ├── hypotheses.py H1~H9 탐색/검정
│   ├── model.py      규칙 지수 / 로지스틱 회귀, 가중치 정책
│   ├── validation.py 검증 V1~V9
│   ├── report.py     summary.json, 결과 엑셀, 스펙, 실행 매니페스트
│   ├── overview.py   인력 현황 집계
│   ├── dashboard.py  두 탭 Chart.js 단일 HTML
│   └── cli.py        predict | dashboard | run
├── skill/predict_attrition/     SKILL.md · scripts/ · reference/(methodology·features·interpretation·labels)
├── skill/make_dashboard/        SKILL.md · scripts/ · reference/dashboard.md
├── agents/hr-analyst.md         Claude Code 서브에이전트
├── tools/make_fixture.py        퇴사자 포함 합성 픽스처 생성
├── fixtures/hr_fixture_186.xlsx
├── tests/test_pipeline.py       회귀 + P0 신뢰성 테스트 (40개)
├── make_skill_zip.py            dist/*.zip 빌드 (버전 일치·단독 실행 검사)
└── Docs/                        고도화 핸드오프
```

## 개발

```bash
python -m pytest tests -q          # 합성 데이터셋이 있으면 전체, 없으면 데이터 의존 테스트 skip
python make_skill_zip.py --check   # zip 두 개 빌드 → 임시 폴더에 풀어 저장소 없이 단독 실행 확인
```

버전은 `engine/hrattrition/__init__.py`의 `__version__` 한 곳에서 관리합니다. pyproject는 이 값을 읽고, zip 빌드는 `plugin.json`과 다르면 거부합니다.

## 데이터 취급

- 엔진은 네트워크를 쓰지 않습니다. 대시보드 HTML만 브라우저에서 Chart.js를 cdnjs에서 불러옵니다.
- 결과 파일(`퇴사위험_결과.xlsx`, `features.csv`, `scores.csv`, `dashboard.html`)에는 직원 이름·사번이 들어 있습니다. 공유 범위를 정하고 다루세요. 공유용 익명 출력은 P3에서 분리합니다.
- `run_manifest.json`의 입력 해시는 재현성 확인용이며 익명화 수단이 아닙니다.

## 라이선스

Proprietary — The Prompt Company. 합성 데이터셋의 원천 페르소나는 [Nemotron-Personas-Korea](https://huggingface.co/datasets/nvidia/Nemotron-Personas-Korea) (CC BY 4.0).
