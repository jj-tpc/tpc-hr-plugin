"""3단계 가설 수립·탐색: '무엇이 퇴사와 관련 있는가'를 가설 목록으로 두고 데이터로 살펴본다.

라벨이 있으면 가설별 단변량 AUC로 지지/기각/불명확을 판정한다.
라벨이 없으면 '탐색'만 한다: 신호가 두드러진 인원 비율, 어느 팀에 몰려 있는지, 위험 '높음' 그룹과의 동반 비율(지수 구성 요소라 순환 참조임을 명시).
"""
import numpy as np
import pandas as pd

from .features import FEATURE_DOCS, PLAIN

HYPOTHESES = [
    ("H1", "연장근로가 많거나 최근 증가한 직원은 퇴사 위험이 높다", ["ot_hours_m6", "ot_trend"]),
    ("H2", "평가가 낮거나 하락한 직원은 퇴사 위험이 높다", ["last_rating_score", "rating_trend", "self_manager_gap"]),
    ("H3", "근속 1~3년 구간이 가장 위험하다", ["tenure_years"]),
    ("H4", "보상 밴드 하단이거나 오래 인상이 없으면 위험이 높다", ["band_position", "months_since_raise", "last_raise_pct"]),
    ("H5", "승진 보류가 반복되거나 오래 승진이 없으면 위험이 높다", ["promotion_holds_2y", "months_since_promotion"]),
    ("H6", "설문 몰입·보상 인식·워라밸·추천의향이 낮으면 위험이 높다", ["survey_engagement", "survey_pay_perception", "survey_workload", "survey_enps", "survey_nonresponse"]),
    ("H7", "지각·결근·병가가 늘면 위험이 높다", ["late_count_m6", "absent_days_m6", "sick_days_m6"]),
    ("H8", "기간제이거나 계약 만료가 임박하면 위험이 높다", ["is_fixed_term", "contract_ending_90d"]),
    ("H9", "휴가 반려·온콜 부담이 크면 위험이 높다", ["leave_rejected_12m", "oncall_weeks_12m"]),
]


def _risk_z(features: pd.DataFrame, c: str) -> pd.Series:
    """위험 방향으로 부호를 맞춘 표준화 값. 근속은 1~3년 구간을 1, 그 외 0으로."""
    x = pd.to_numeric(features[c], errors="coerce")
    if c == "tenure_years":
        return ((x >= 1) & (x < 3)).astype(float).where(x.notna())
    sd = x.std(ddof=0)
    if not sd or np.isnan(sd):
        return pd.Series(np.nan, index=features.index)
    return ((x - x.mean()) / sd * FEATURE_DOCS[c][2]).clip(-3, 3)


def _auc(score: pd.Series, y: pd.Series) -> float | None:
    m = score.notna() & y.notna()
    s, t = score[m].to_numpy(), y[m].astype(int).to_numpy()
    if t.sum() == 0 or t.sum() == len(t):
        return None
    ranks = pd.Series(s).rank().to_numpy()
    pos = t == 1
    return float((ranks[pos].sum() - pos.sum() * (pos.sum() + 1) / 2) / (pos.sum() * (~pos).sum()))


def evaluate_hypotheses(features: pd.DataFrame, scores: pd.DataFrame, labels: pd.Series | None) -> dict:
    f = features.set_index("employee_id")
    s = scores.set_index("employee_id").reindex(f.index)
    high = s.risk_band == "높음"
    y = labels.reindex(f.index) if labels is not None else None
    rows = []
    for hid, text, feats in HYPOTHESES:
        avail = [c for c in feats if c in f and f[c].notna().any()]
        if not avail:
            rows.append(dict(id=hid, hypothesis=text, status="데이터 없음", signals=[], note="관련 신호를 계산하지 못했다"))
            continue
        sig_rows, aucs = [], []
        for c in avail:
            z = _risk_z(f, c)
            strong = z >= 1 if c != "tenure_years" else z >= 1
            n = int(z.notna().sum())
            r = dict(signal=FEATURE_DOCS[c][0], plain=PLAIN.get(c, ("",))[0], n=n, strong_n=int(strong.sum()),
                     strong_pct=round(100 * float(strong.sum()) / max(n, 1), 1))
            if "org_unit_name" in f and strong.any():
                top = f.loc[strong, "org_unit_name"].fillna("미지정").value_counts()
                r["concentrated_in"] = f"{top.index[0]} {int(top.iloc[0])}명"
            if high.any():
                r["share_in_high_pct"] = round(100 * float((strong & high).sum()) / max(int(high.sum()), 1), 1)
            if y is not None:
                a = _auc(z, y)
                r["auc"] = round(a, 3) if a is not None else None
                if a is not None:
                    aucs.append(a)
                    left, stay = f.loc[y == 1, c], f.loc[y == 0, c]
                    r["mean_left"], r["mean_stayed"] = round(float(pd.to_numeric(left, errors="coerce").mean()), 2), round(float(pd.to_numeric(stay, errors="coerce").mean()), 2)
            sig_rows.append(r)
        if y is not None and aucs:
            best = max(aucs)
            status = "지지(단변량)" if best >= 0.6 else "반대(단변량)" if best <= 0.4 else "불명확"
            note = f"가장 강한 신호의 단변량 AUC {best:.2f} (양성 {int(y.sum())}명). 무작위 교차검증이 아닌 전체 표본 단변량 값이며 시간 분리 검증이 아니다."
            kind = "검증 결과(라벨 기반)"
        else:
            status = "탐색적 증거(라벨 없음)"
            note = "실제 퇴사 라벨이 없어 검증하지 않았다. 신호가 두드러진 인원 비율과 분포만 확인했고, 규칙 지수에는 가중치로 반영된 사전 가설이다. 높음 그룹 동반 비율은 지수 구성 요소라 순환 참조이므로 근거로 쓰지 않는다."
            kind = "탐색 결과"
        rows.append(dict(id=hid, hypothesis=text, status=status, evidence_kind=kind, signals=sig_rows, note=note))
    return dict(method="단변량 AUC(라벨 있을 때) / 분포 탐색(라벨 없을 때)", evidence_kind="검증 결과" if y is not None else "탐색 결과", hypotheses=rows)
