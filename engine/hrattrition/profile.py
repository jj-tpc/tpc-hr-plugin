"""2단계 데이터 이해: 어떤 테이블이 있고 무엇을 뜻하는지, 행 수·직원 수·누락·중복·기간 범위를 확인한다."""
import pandas as pd

from .data import Dataset
from .features import FEATURE_DOCS

TABLE_MEANING = {
    "employees": ("직원 마스터(1인 1행): 입사일·학력·채용경로 등 고정 정보", "employee_id"),
    "employees_current": ("기준일 스냅샷: 소속·직급·직책·계약·연봉·재직상태·연차 잔액·최근 등급", "employee_id"),
    "compensation_history": ("기준연봉 변경 이력(효력기간·밴드·변경률)", "employee_id"),
    "promotion_reviews": ("승진 심사 결과(승진/보류)와 사유", "employee_id"),
    "personnel_actions": ("인사발령(입사·승진·전보·보직·휴직·복직)", "employee_id"),
    "performance_reviews": ("평가 주기별 자기평가·1차·확정 등급", "employee_id"),
    "attendance_monthly": ("직원·월별 근태 집계(연장·지각·결근·병가·인정시간)", "employee_id"),
    "leave_requests": ("휴가 신청과 상태(승인·취소·반려·대기)", "employee_id"),
    "training_enrollments": ("교육 수강·수료 기록", "employee_id"),
    "oncall_shifts": ("온콜 담당 주(IT)", "employee_id"),
    "surveys": ("설문 회차", "survey_id"), "survey_questions": ("설문 문항과 차원", "question_id"),
    "survey_responses": ("직원별 응답 상태", "employee_id"), "survey_answers": ("문항별 응답값", "employee_id"),
    "contracts": ("계약 버전(정규직·기간제)", "employee_id"),
    "labels": ("퇴사 라벨(employee_id, left)", "employee_id"),
    "roster": ("직원 명부 한 장(별칭으로 인식한 컬럼만 사용)", "employee_id"),
}
DATE_COLS = {"compensation_history": "effective_from", "promotion_reviews": "decided_at", "personnel_actions": "effective_date",
             "performance_reviews": "finalized_at", "leave_requests": "requested_at", "training_enrollments": "completed_at",
             "oncall_shifts": "week_start", "surveys": "closed_at"}


def _span(s: pd.Series) -> str:
    s = pd.to_datetime(s, errors="coerce").dropna()
    return f"{s.min().date()} ~ {s.max().date()}" if len(s) else "-"


def profile_dataset(ds: Dataset, features: pd.DataFrame, all_ids: set | None = None) -> dict:
    """features는 모집단(필터 적용 후), all_ids는 입력 파일의 전체 재직자. 명단 밖 사번은 전체 기준으로 판단한다."""
    ids = set(features.employee_id.astype(str))
    all_ids = set(all_ids) if all_ids is not None else ids
    tables = []
    for name, (meaning, key) in TABLE_MEANING.items():
        if not ds.has(name):
            if name in ("roster",) and ds.kind != "roster":
                continue
            tables.append(dict(table=name, meaning=meaning, present=False, rows=0))
            continue
        df = ds[name]
        row = dict(table=name, meaning=meaning, present=True, rows=int(len(df)))
        if "employee_id" in df:
            e = df.employee_id.astype(str)
            row["employees_covered"] = int(e[e.isin(ids)].nunique())
            row["coverage_pct"] = round(100 * row["employees_covered"] / max(len(ids), 1), 1)
            row["unknown_employee_rows"] = int((~e.isin(all_ids)).sum())
        if key == "employee_id" and name in ("employees", "employees_current", "roster"):
            row["duplicate_ids"] = int(df.employee_id.astype(str).duplicated().sum())
        if name in DATE_COLS and DATE_COLS[name] in df:
            row["date_span"] = _span(df[DATE_COLS[name]])
        if name == "attendance_monthly" and "pay_month" in df:
            m = df.pay_month.astype(str)
            row["date_span"] = f"{m.min()} ~ {m.max()}" if len(m) else "-"
            row["months"] = int(m.nunique())
        tables.append(row)

    # 신호별 결측률(모집단 기준)
    missing = []
    for c, (label, _, _) in FEATURE_DOCS.items():
        if c in features:
            pct = round(100 * float(features[c].isna().mean()), 1)
            if pct > 0:
                missing.append(dict(signal=label, missing_pct=pct))
    missing.sort(key=lambda r: -r["missing_pct"])

    issues = []
    dup = next((t for t in tables if t.get("duplicate_ids")), None)
    if dup:
        issues.append(f"{dup['table']}에 중복 사번 {dup['duplicate_ids']}건")
    for t in tables:
        if t.get("unknown_employee_rows"):
            issues.append(f"{t['table']}에 재직자 명단에 없는 사번의 행 {t['unknown_employee_rows']}건(제외)")
    if ds.kind == "roster":
        issues.append("직원 명부 한 장 모드: 이력 테이블이 없어 추세·설문 신호를 만들 수 없다")
    unavailable = features.attrs.get("unavailable", [])
    if unavailable:
        issues.append("계산하지 못한 신호: " + ", ".join(FEATURE_DOCS[c][0] for c in unavailable if c in FEATURE_DOCS))
    if len(ids) < len(all_ids):
        issues.insert(0, f"모집단 제한으로 전체 {len(all_ids)}명 중 {len(ids)}명만 분석(나머지 행은 제외)")
    return dict(kind=ds.kind, source=ds.source, as_of=ds.manifest.get("as_of"), employees=len(ids), employees_total=len(all_ids),
                column_mapping=ds.manifest.get("column_mapping"), tables=tables, missing_signals=missing, issues=issues)
