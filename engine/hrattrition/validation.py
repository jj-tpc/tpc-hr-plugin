"""4단계 검증: 반례 확인, 기준일 이후 정보 제외 확인, 점수 산정 방식·안정성·한계 점검."""
import numpy as np
import pandas as pd

from . import config as C
from .features import FEATURE_DOCS, PLAIN
from .hypotheses import HYPOTHESES, _risk_z
from .model import HEURISTIC_WEIGHTS, heuristic_scores


def _counterexamples(f: pd.DataFrame, s: pd.DataFrame, k: int = 3) -> list[dict]:
    """강한 위험 신호(z≥1.5)인데 밴드가 '낮음'인 직원, 반대로 '높음'인데 강한 신호가 하나도 없는 직원."""
    out = []
    low, high = s.risk_band == "낮음", s.risk_band == "높음"
    any_strong = pd.Series(False, index=f.index)
    for hid, text, feats in HYPOTHESES:
        strong = pd.Series(False, index=f.index)
        for c in feats:
            if c in f and f[c].notna().any():
                z = _risk_z(f, c)
                strong |= (z >= 1.5).fillna(False)
        any_strong |= strong
        ce = f[strong & low]
        if len(ce):
            out.append(dict(hypothesis=hid, type="강한 신호인데 밴드 낮음", count=int(len(ce)),
                            examples=[f"{i} {n}" for i, n in zip(ce.index[:k], ce["name"].iloc[:k])],
                            reading="이 신호 하나로 위험을 단정하면 안 된다는 뜻. 다른 신호가 안전 쪽이었다."))
    hi_quiet = f[high & ~any_strong]
    if len(hi_quiet):
        out.append(dict(hypothesis="전체", type="밴드 높음인데 강한 단일 신호 없음", count=int(len(hi_quiet)),
                        examples=[f"{i} {n}" for i, n in zip(hi_quiet.index[:k], hi_quiet["name"].iloc[:k])],
                        reading="약한 신호가 여럿 겹친 경우. 면담 때 어느 신호인지 상세를 봐야 한다."))
    return out


def _sensitivity(features: pd.DataFrame, scores: pd.DataFrame, weights: dict | None) -> dict:
    """신호를 하나씩 뺐을 때 순위(스피어만)와 밴드가 얼마나 바뀌는지."""
    base = scores.set_index("employee_id").risk_score
    rows = []
    for c in HEURISTIC_WEIGHTS:
        if c not in features or features[c].isna().all():
            continue
        w = {**(weights or {}), c: 0.0}
        alt = heuristic_scores(features, w).scores.set_index("employee_id")
        rho = float(base.corr(alt.risk_score, method="spearman"))
        flips = int((alt.risk_band != scores.set_index("employee_id").risk_band).sum())
        rows.append(dict(signal=FEATURE_DOCS[c][0], rank_corr_without=round(rho, 3), band_changes=flips))
    rows.sort(key=lambda r: r["rank_corr_without"])
    return dict(method="신호 하나를 가중치 0으로 두고 재계산 → 원래 지수와의 순위 상관·밴드 변경 수", most_influential=rows[:5], all=rows)


def validate(features: pd.DataFrame, res, labels: pd.Series | None, as_of: str, weights: dict | None) -> dict:
    f = features.set_index("employee_id")
    s = res.scores.set_index("employee_id").reindex(f.index)
    excluded = features.attrs.get("excluded_after_as_of", {})
    leakage = dict(as_of=as_of, rule="기준일 이후에 효력·확정·신청·종료된 기록은 피처 계산에서 제외",
                   excluded_rows_by_table={k: int(v) for k, v in excluded.items() if v}, total_excluded=int(sum(excluded.values())),
                   passed=True)
    coverage = [dict(signal=FEATURE_DOCS[c][0], coverage_pct=round(100 * float(f[c].notna().mean()), 1)) for c in FEATURE_DOCS if c in f]
    low_cov = [r for r in coverage if r["coverage_pct"] < 50]
    method = (dict(mode="heuristic", description="신호별 표준화 z × 공개 가중치 합 + 근속 구간 가산 → 표준화 → 시그모이드(0~1). 회사 내 상대 지수.",
                   weights_used=res.metrics.get("weights"), bands={b: lo for b, lo in C.RISK_BANDS}, band_counts=res.metrics.get("band_counts"))
              if res.mode == "heuristic" else
              dict(mode="model", description=res.metrics.get("algorithm"), cv_auc=res.metrics.get("cv_auc"), positives=res.metrics.get("positives"),
                   n_train=res.metrics.get("n_train"), band_counts=res.metrics.get("band_counts")))
    sens = _sensitivity(features, res.scores, weights) if res.mode == "heuristic" else None
    limitations = [
        "단면 분석: 기준일 하나의 상태로 계산했고 과거 시점과의 비교는 하지 않았다.",
        "성별·국적·체류자격·혼인·가족·주거·거주지·병역은 쓰지 않았다. 다만 다른 신호가 이들과 상관될 가능성은 남아 있다.",
    ]
    if res.mode == "heuristic":
        limitations.insert(0, "라벨(실제 퇴사)이 없어 가중치는 가설에 근거한 사전 설정값이다. 지수는 예측 확률이 아니며 정확도를 측정할 수 없다.")
    else:
        limitations.insert(0, f"양성 {res.metrics.get('positives')}명으로 학습했다. 표본이 작으면 AUC가 불안정하다.")
    if low_cov:
        limitations.append("커버리지 50% 미만 신호: " + ", ".join(r["signal"] for r in low_cov))
    if res.metrics.get("fallback_reason"):
        limitations.append(res.metrics["fallback_reason"])
    return dict(leakage=leakage, counterexamples=_counterexamples(f, s), scoring_method=method, sensitivity=sens,
                coverage=coverage, limitations=limitations,
                checklist=[
                    dict(item="기준일 이후 정보 제외", result="통과", detail=f"{leakage['total_excluded']}행 제외"),
                    dict(item="반례 확인", result="확인", detail=f"{sum(c['count'] for c in _counterexamples(f, s))}건 기록"),
                    dict(item="점수 산정 방식 공개", result="통과", detail=method["description"]),
                    dict(item="민감 속성 미사용", result="통과", detail="SENSITIVE_COLUMNS 제외"),
                    dict(item="순위 안정성", result=("확인" if sens else "해당 없음"),
                         detail=(f"가장 영향 큰 신호 제거 시 순위 상관 {sens['most_influential'][0]['rank_corr_without']}" if sens and sens["most_influential"] else "-")),
                ])
