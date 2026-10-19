"""상수와 피처 정책. 경로는 호출 시 넘기며, 기본 산출물 폴더는 저장소 루트/artifacts (로컬 개발용)."""
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parents[1]            # engine/ (zip 안에서는 scripts/)
REPO_ROOT = ENGINE_ROOT.parent
DEFAULT_OUT_ROOT = REPO_ROOT / "artifacts"

# ---- 피처 정책(엔진에서 강제) ----
# 민감 속성: 어떤 경로(규칙·모델·스펙 override)로도 점수에 들어갈 수 없다. 피처 테이블에도 싣지 않는다.
SENSITIVE_COLUMNS = ("sex", "nationality", "residence_status", "marital_status", "family_type", "housing_type",
                     "residence_district", "korean_proficiency", "military_service", "birth_date", "age_group")
# 개인 위험 가중치에서 제외하는 신호(조직 집계·현황에는 쓸 수 있다): 건강·소통 참여도로 개인을 추론하지 않기 위해
EXCLUDED_FROM_INDIVIDUAL_WEIGHTS = ("sick_days_m6", "survey_nonresponse")

RATING_SCORE = {"S": 5, "A": 4, "B": 3, "C": 2, "D": 1}
RECENT_MONTHS = 6          # 근태 최근 구간
TREND_MONTHS = 3           # 추세 비교 구간(최근 3개월 vs 그 전 3개월)
MIN_POSITIVES_FOR_MODEL = 10   # 모델 '실행 가능' 조건일 뿐 출시 기준이 아니다(P5)
RISK_BANDS = (("높음", 0.70), ("주의", 0.40), ("낮음", 0.0))
LABEL_SHEETS = ("퇴사라벨", "labels", "hr_labels")
RESULT_FILENAME = "퇴사위험_결과.xlsx"
DATA_SHEET, META_SHEET = "_data", "_meta"   # 결과 워크북 안의 기계용 시트(대시보드 입력)
SPEC_SCHEMA = "hr-attrition-spec/2"
RESULT_SCHEMA = "hr-attrition-result/2"
ANALYSIS_MODES = ("diagnostic", "change", "predictive")   # 제품 수준 모드. heuristic/model은 계산 방식


def risk_band(p: float) -> str:
    for name, lo in RISK_BANDS:
        if p >= lo:
            return name
    return RISK_BANDS[-1][0]
