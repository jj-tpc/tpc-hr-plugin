"""파이프라인 회귀 테스트. 합성 데이터셋 xlsx가 없으면 데이터 의존 테스트는 건너뛴다.

    python -m pytest tests -q
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from hrattrition import config as C
from hrattrition.dashboard import build_dashboard
from hrattrition.data import load_any, load_roster_frame
from hrattrition.features import FEATURE_DOCS, PLAIN, build_features, numeric_matrix
from hrattrition.labels import load_labels
from hrattrition.model import HEURISTIC_WEIGHTS, heuristic_scores, model_scores, score
from hrattrition.overview import build_overview
from hrattrition.report import build_summary, read_result_workbook, write_result_workbook

ROOT = Path(__file__).resolve().parents[1]
DATASET_ROOT = Path(os.environ.get("HR_DATASET_ROOT", "~/project_tpc/offpiste_synthetic_HR_data/output")).expanduser()
XLSX = sorted(DATASET_ROOT.glob("*/synthetic_hr_*.xlsx")) if DATASET_ROOT.exists() else []


@pytest.fixture(scope="session", params=XLSX or [pytest.param(None, marks=pytest.mark.skip(reason="합성 데이터셋 xlsx 없음"))],
                ids=lambda p: p.parent.name if p else "none")
def workbook(request):
    ds = load_any(str(request.param))
    return ds, build_features(ds)


def test_workbook_loads_as_standard_dataset(workbook):
    ds, f = workbook
    assert ds.kind == "workbook" and ds.manifest["employee_count"] == len(f) == 100
    assert ds.manifest["company"]["name"].startswith("(주)")
    assert ds.has("employees_current") and ds.has("compensation_history") and ds.has("survey_answers")
    assert not ds.has("attendance_daily")   # 큰 시트는 읽지 않는다
    assert f.attrs.get("unavailable") == []
    for k in FEATURE_DOCS:
        assert k in f.columns, k
    for col in C.SENSITIVE_COLUMNS:
        assert col not in f.columns
    assert f.band_position.dropna().between(0, 1).all()


def test_heuristic_weights_match_documented_direction_and_have_plain_text():
    for k, w in HEURISTIC_WEIGHTS.items():
        assert k in FEATURE_DOCS and k in PLAIN
        assert FEATURE_DOCS[k][2] != 0 and np.sign(w) == FEATURE_DOCS[k][2], k


def test_heuristic_scores_schema_and_plain_drivers(workbook):
    _, f = workbook
    res = heuristic_scores(f)
    s = res.scores
    assert list(s.columns) == ["employee_id", "risk_score", "risk_band", "top_drivers", "drivers_plain", "mode"]
    assert s.risk_score.between(0, 1).all() and set(s.risk_band) <= {"높음", "주의", "낮음"}
    assert 5 <= (s.risk_band == "높음").sum() <= 30
    assert s.drivers_plain.str.contains("강함|뚜렷|약함|뚜렷한 신호 없음").all()
    assert score(f, None, "auto").mode == "heuristic"


def test_model_mode_with_synthetic_labels(workbook):
    _, f = workbook
    X = numeric_matrix(f)
    rng = np.random.default_rng(0)
    signal = -X["survey_engagement"].fillna(X["survey_engagement"].mean()) + X["ot_hours_m6"].fillna(0) / 5
    p = 1 / (1 + np.exp(-(signal - signal.mean()) / signal.std()))
    y = pd.Series((rng.random(len(p)) < p).astype(int), index=X.index)
    y.iloc[: C.MIN_POSITIVES_FOR_MODEL] = 1
    res = model_scores(f, y)
    assert res.mode == "model" and 0 <= res.metrics["cv_auc"] <= 1
    assert res.metrics["coefficients"]["survey_engagement"] < 0


def test_roster_single_sheet_mode(tmp_path: Path):
    df = pd.DataFrame({
        "사번": ["A1", "A2", "A3", "A4"], "이름": ["가", "나", "다", "라"], "부서": ["영업", "영업", "개발", "개발"], "직급": ["대리", "과장", "사원", "차장"],
        "입사일": ["2024-03-01", "2018-01-02", "2025-09-01", "2012-05-01"], "연봉(만원)": [4200, 6000, 3600, 8000],
        "최근 평가": ["B", "A", "C", "S"], "월평균 연장": [12, 4, 20, 2], "성별": ["여", "남", "여", "남"],
    })
    p = tmp_path / "roster.xlsx"
    df.to_excel(p, index=False)
    ds = load_any(str(p))
    assert ds.kind == "roster" and ds.manifest["employee_count"] == 4
    f = build_features(ds)
    assert "sex" not in f.columns and f.tenure_years.notna().all() and f.last_rating_score.tolist() == [3, 4, 2, 5]
    assert "survey_engagement" in f.attrs["unavailable"]
    res = heuristic_scores(f)
    assert len(res.scores) == 4 and "survey_engagement" in res.metrics["weights_skipped_no_data"]
    summary = build_summary(f, res, ds.manifest, top_n=3)
    assert summary["n_employees"] == 4 and "설문 몰입·관리자·성장(1~5)" in summary["unavailable_signals"]
    ov = build_overview(f, ds.manifest["as_of"])
    assert ov["headcount"] == 4 and ov["monthly"] is None and sum(b["n"] for b in ov["tenure_bins"]) == 4


def test_labels_from_sheet_and_csv(tmp_path: Path):
    roster = pd.DataFrame({"사번": [f"E{i}" for i in range(30)], "입사일": ["2020-01-01"] * 30, "퇴사여부": ["예"] * 12 + ["아니오"] * 18})
    ds = load_roster_frame(roster, "mem")
    s = load_labels(ds)
    assert s is not None and s.sum() == 12 and len(s) == 30
    p = tmp_path / "labels.csv"
    p.write_text("employee_id,left\nE0,1\nE1,0\n", encoding="utf-8")
    assert load_labels(ds, p).tolist() == [1, 0]
    p.write_text("employee_id,left\nE0,maybe\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_labels(ds, p)


def test_result_workbook_roundtrip_and_dashboard(workbook, tmp_path: Path):
    ds, f = workbook
    res = heuristic_scores(f)
    summary = build_summary(f, res, ds.manifest, top_n=10)
    assert len(summary["top_employees"]) == 10 and sum(summary["bands"].values()) == 100
    assert summary["company_signals"] and summary["actions"] and summary["caveats"]
    xlsx = write_result_workbook(f, res, summary, ds.manifest, tmp_path)
    sheets = pd.read_excel(xlsx, sheet_name=None)
    assert {"요약", "직원별 위험", "팀별", "회사 전체 신호", "조치 제안", "신호 상세", "신호 설명", C.DATA_SHEET, C.META_SHEET} <= set(sheets)
    f2, s2, meta = read_result_workbook(xlsx)
    assert len(f2) == 100 and set(s2.employee_id) == set(f.employee_id) and meta["mode"] == "heuristic"
    assert meta["manifest"]["company"]["name"] == ds.manifest["company"]["name"]
    ov = build_overview(f2, meta["manifest"]["as_of"], ds)
    assert ov["monthly"] and ov["survey"] and ov["by_division"] and ov["leave"]["rate"] is not None
    html = build_dashboard(f2, s2, meta["metrics"], meta["manifest"], ov, tmp_path / "d.html", meta["unavailable"]).read_text(encoding="utf-8")
    assert html.startswith("<!doctype html>") and "cdnjs.cloudflare.com" in html and "__DATA__" not in html and "__OVERVIEW__" not in html
    assert "인력 현황" in html and "퇴사 위험" in html
    json.loads(html[html.index("const DATA = ") + 13: html.index(";\nconst DOCS")])


def test_methodology_steps_produce_artifacts(workbook, tmp_path: Path):
    """질문→데이터→가설→검증→행동→재사용 각 단계의 산출물이 만들어지고 서로 맞는지."""
    from hrattrition.hypotheses import HYPOTHESES, evaluate_hypotheses
    from hrattrition.profile import profile_dataset
    from hrattrition.question import QuestionSpec, apply_population, parse_filters
    from hrattrition.report import write_analysis_spec
    from hrattrition.validation import validate

    ds, f_all = workbook
    assert sum(f_all.attrs["excluded_after_as_of"].values()) == 0   # 합성 데이터는 이미 기준일로 잘려 있다
    q = QuestionSpec.from_args(filters=parse_filters(["직군=개발직"]) if (f_all.job_family == "개발직").any() else parse_filters(["직군=생산직"]))
    q.as_of = ds.manifest["as_of"]
    assert "90일" in q.sentence() and "자발적 퇴사" in q.sentence()
    f, pop = apply_population(f_all, q)
    assert 0 < pop["after"] < pop["before"] == 100
    prof = profile_dataset(ds, f)
    assert prof["employees"] == pop["after"] and any(t["table"] == "attendance_monthly" and t["present"] for t in prof["tables"])
    res = heuristic_scores(f)
    hyp = evaluate_hypotheses(f, res.scores, None)
    assert len(hyp["hypotheses"]) == len(HYPOTHESES) and all(h["status"].startswith("탐색") or h["status"] == "데이터 없음" for h in hyp["hypotheses"])
    val = validate(f, res, None, q.as_of, None)
    assert val["leakage"]["passed"] and val["sensitivity"]["most_influential"] and len(val["checklist"]) == 5
    assert any("정확도" in l for l in val["limitations"])
    summary = build_summary(f, res, ds.manifest, 5, q.to_dict(), prof, hyp, val, pop)
    assert summary["question"]["horizon_days"] == 90 and summary["unit_actions"]
    xlsx = write_result_workbook(f, res, summary, ds.manifest, tmp_path)
    sheets = pd.ExcelFile(xlsx).sheet_names
    assert sheets[:7] == ["1 질문 정의", "요약", "2 데이터 이해", "2 데이터 이슈", "3 가설", "4 검증", "5 팀별 확인사항"]
    spec = json.loads(write_analysis_spec(summary, res, None, tmp_path).read_text(encoding="utf-8"))
    assert spec["question"]["filters"] == q.filters and len(spec["procedure"]) == 6
    # 라벨이 있으면 가설 판정이 지지/반대/불명확으로 바뀐다
    X = numeric_matrix(f)
    y = pd.Series((X["survey_engagement"].fillna(3) < X["survey_engagement"].median()).astype(int), index=X.index)
    hyp2 = evaluate_hypotheses(f, res.scores, y)
    h6 = next(h for h in hyp2["hypotheses"] if h["id"] == "H6")
    assert h6["status"] in {"지지", "반대", "불명확"} and h6["signals"][0]["auc"] is not None


def test_leakage_cutoff_excludes_future_rows(workbook):
    """기준일 이후 기록을 끼워 넣으면 피처 계산에서 제외되고 건수가 기록된다."""
    import copy
    ds, _ = workbook
    ds2 = copy.copy(ds)
    ds2.tables = dict(ds.tables)
    rv = ds.tables["performance_reviews"].copy()
    fut = rv.head(3).copy()
    fut["finalized_at"] = pd.Timestamp(ds.as_of) + pd.Timedelta(days=30)
    fut["final_rating"] = "D"
    ds2.tables["performance_reviews"] = pd.concat([rv, fut])
    f2 = build_features(ds2)
    assert f2.attrs["excluded_after_as_of"]["performance_reviews"] == 3


def test_entry_scripts_run_end_to_end(workbook, tmp_path: Path):
    """두 스킬의 진입 스크립트가 저장소 안에서 설치 없이 동작하는지."""
    ds, _ = workbook
    env = {**os.environ, "PYTHONUTF8": "1"}
    r = subprocess.run([sys.executable, str(ROOT / "skill/predict_attrition/scripts/predict_attrition.py"), "--input", ds.source, "--out", str(tmp_path),
                        "--horizon-days", "180", "--prompt", "누가 그만둘 것 같은지 봐줘"], capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    assert (tmp_path / C.RESULT_FILENAME).exists() and (tmp_path / "summary.json").exists() and (tmp_path / "analysis_spec.json").exists()
    assert all(tag in r.stdout for tag in ("[1 질문]", "[2 데이터]", "[3 가설]", "[4 검증]", "[5 행동]", "[6 재사용]"))
    s = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert s["question"]["horizon_days"] == 180 and s["question"]["raw_prompt"].startswith("누가")
    # 재사용: 스펙만 넘겨도 같은 질문 정의로 돈다
    r = subprocess.run([sys.executable, str(ROOT / "skill/predict_attrition/scripts/predict_attrition.py"), "--input", ds.source, "--out", str(tmp_path / "rerun"),
                        "--spec", str(tmp_path / "analysis_spec.json")], capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    s2 = json.loads((tmp_path / "rerun" / "summary.json").read_text(encoding="utf-8"))
    assert s2["question"]["horizon_days"] == 180
    r = subprocess.run([sys.executable, str(ROOT / "skill/make_dashboard/scripts/make_dashboard.py"), "--result", str(tmp_path / C.RESULT_FILENAME),
                        "--data", ds.source, "--out", str(tmp_path)], capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    assert (tmp_path / "dashboard.html").exists() and "원본 포함" in r.stdout
