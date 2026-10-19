"""현재 인력 현황(대시보드 '현황' 탭). 예측 결과의 피처만으로도 만들고, 원본 데이터가 있으면 월별 추세·설문을 더한다."""
import numpy as np
import pandas as pd

from .data import Dataset


def _counts(s: pd.Series, order: list | None = None) -> list[dict]:
    vc = s.fillna("미지정").astype(str).value_counts()
    if order:
        vc = vc.reindex([o for o in order if o in vc.index]).dropna().astype(int)
    return [dict(name=k, n=int(v)) for k, v in vc.items()]


def _bins(s: pd.Series, edges: list, labels: list) -> list[dict]:
    s = pd.to_numeric(s, errors="coerce").dropna()
    cut = pd.cut(s, bins=edges, labels=labels, right=False, include_lowest=True)
    vc = cut.value_counts().reindex(labels).fillna(0).astype(int)
    return [dict(name=str(k), n=int(v)) for k, v in vc.items()]


def build_overview(features: pd.DataFrame, as_of: str, raw: Dataset | None = None) -> dict:
    f = features.copy()
    n = len(f)
    tenure = pd.to_numeric(f.get("tenure_years"), errors="coerce")
    age = pd.to_numeric(f.get("age"), errors="coerce")
    grade_order = f.groupby("grade_title")["grade_level"].mean().sort_values().index.tolist() if "grade_level" in f and f["grade_level"].notna().any() else None
    status = f.get("employment_status", pd.Series(["재직"] * n)).fillna("재직").astype(str)
    etype = f.get("employment_type", pd.Series([""] * n)).fillna("").astype(str)
    ov = dict(
        as_of=as_of, headcount=n,
        on_leave=int(status.str.contains("휴직").sum()),
        fixed_term=int(etype.str.contains("기간제|계약").sum()),
        leaders=int(pd.to_numeric(f.get("is_leader"), errors="coerce").fillna(0).sum()),
        avg_tenure=round(float(tenure.mean()), 1) if tenure.notna().any() else None,
        avg_age=round(float(age.mean()), 1) if age.notna().any() else None,
        new_hires_12m=int((tenure < 1).sum()) if tenure.notna().any() else None,
        by_division=_counts(f.get("division_name", pd.Series(["전체"] * n))),
        by_family=_counts(f.get("job_family", pd.Series(["미지정"] * n))),
        by_grade=_counts(f.get("grade_title", pd.Series(["미지정"] * n)), grade_order),
        by_employment_type=_counts(etype.replace("", "미지정")),
        tenure_bins=_bins(tenure, [0, 1, 3, 6, 10, 15, 100], ["1년 미만", "1~3년", "3~6년", "6~10년", "10~15년", "15년 이상"]) if tenure.notna().any() else [],
        age_bins=_bins(age, [0, 30, 40, 50, 100], ["20대 이하", "30대", "40대", "50대 이상"]) if age.notna().any() else [],
        monthly=None, survey=None, leave=None,
    )
    if raw is not None:
        ov.update(_from_raw(raw, f))
    return ov


def _from_raw(ds: Dataset, f: pd.DataFrame) -> dict:
    out: dict = {}
    ids = set(f.employee_id.astype(str))
    am = ds["attendance_monthly"]
    if len(am):
        am = am[am.employee_id.astype(str).isin(ids)].copy()
        for c in ("overtime_hours", "late_count", "absent_days", "recognized_hours"):
            am[c] = pd.to_numeric(am[c], errors="coerce")
        g = am.groupby(am.pay_month.astype(str)).agg(overtime=("overtime_hours", "mean"), late=("late_count", "sum"),
                                                     absent=("absent_days", "sum"), hours=("recognized_hours", "mean")).sort_index()
        out["monthly"] = dict(labels=g.index.tolist(), overtime=[round(float(v), 1) for v in g.overtime.fillna(0)],
                              late=[int(v) for v in g.late.fillna(0)], absent=[int(v) for v in g.absent.fillna(0)],
                              hours=[round(float(v), 1) for v in g.hours.fillna(0)])
    sv, sq, sa = ds["surveys"], ds["survey_questions"], ds["survey_answers"]
    if len(sv) and len(sq) and len(sa):
        rows = []
        for _, s in sv.sort_values("closed_at").iterrows():
            q = sq[sq.survey_id == s.survey_id].set_index("question_id")
            ans = sa[sa.question_id.isin(q.index)].copy()
            ans["dimension"] = ans.question_id.map(q.dimension)
            ans["value"] = pd.to_numeric(ans.value, errors="coerce")
            dims = ans.groupby("dimension").value.mean()
            rows.append(dict(survey=str(s.survey_id), closed_at=str(pd.Timestamp(s.closed_at).date()) if pd.notna(s.closed_at) else "",
                             dims={k: round(float(v), 2) for k, v in dims.items()}))
        if rows:
            out["survey"] = rows[-2:]   # 최근 2개 설문 비교
    snap = ds["employees_current"]
    if len(snap) and "annual_leave_granted" in snap:
        g = pd.to_numeric(snap.annual_leave_granted, errors="coerce").sum()
        u = pd.to_numeric(snap.annual_leave_used, errors="coerce").sum()
        out["leave"] = dict(granted=float(g), used=float(u), rate=round(100 * u / g, 1) if g else None)
    return out
