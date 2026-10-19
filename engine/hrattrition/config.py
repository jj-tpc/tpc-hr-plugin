"""상수. 경로는 호출 시 넘기며, 기본 산출물 폴더는 저장소 루트/artifacts (로컬 개발용)."""
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parents[1]            # engine/ (zip 안에서는 scripts/)
REPO_ROOT = ENGINE_ROOT.parent
DEFAULT_OUT_ROOT = REPO_ROOT / "artifacts"

# 공정성: 기본 피처에서 제외하는 민감 속성. 어떤 모드에서도 자동으로 쓰지 않는다.
SENSITIVE_COLUMNS = ("sex", "nationality", "residence_status", "marital_status", "family_type", "housing_type",
                     "residence_district", "korean_proficiency", "military_service")

RATING_SCORE = {"S": 5, "A": 4, "B": 3, "C": 2, "D": 1}
RECENT_MONTHS = 6          # 근태 최근 구간
TREND_MONTHS = 3           # 추세 비교 구간(최근 3개월 vs 그 전 3개월)
MIN_POSITIVES_FOR_MODEL = 10
RISK_BANDS = (("높음", 0.70), ("주의", 0.40), ("낮음", 0.0))
LABEL_SHEETS = ("퇴사라벨", "labels", "hr_labels")
RESULT_FILENAME = "퇴사위험_결과.xlsx"
DATA_SHEET, META_SHEET = "_data", "_meta"   # 결과 워크북 안의 기계용 시트(대시보드 입력)


def risk_band(p: float) -> str:
    for name, lo in RISK_BANDS:
        if p >= lo:
            return name
    return RISK_BANDS[-1][0]
