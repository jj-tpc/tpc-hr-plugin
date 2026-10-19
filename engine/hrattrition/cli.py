"""명령줄.

    predict   --input <HR.xlsx|폴더|프리셋> --out DIR [--labels csv] [--mode auto|model|heuristic] [--weights w.json] [--top 10]
              → features.csv, scores.csv, metrics.json, summary.json, 퇴사위험_결과.xlsx
    dashboard --result <퇴사위험_결과.xlsx> [--data <HR.xlsx>] --out DIR [--open]
              → dashboard.html   (--result가 없고 --data만 있으면 예측을 먼저 수행한다)
    run       predict + dashboard
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from . import config as C
from .dashboard import build_dashboard
from .data import load_any
from .features import build_features
from .labels import describe_labels, load_labels
from .hypotheses import evaluate_hypotheses
from .model import save_result, score
from .overview import build_overview
from .profile import profile_dataset
from .question import QuestionSpec, apply_population, parse_filters
from .report import build_summary, read_result_workbook, write_analysis_spec, write_result_workbook, write_summary
from .validation import validate

DATASET_ROOT = Path(os.environ.get("HR_DATASET_ROOT", "~/project_tpc/offpiste_synthetic_HR_data/output")).expanduser()


def _add_predict_args(ap):
    ap.add_argument("--input", "--data", "--preset", dest="input", help="HR xlsx 파일, output/<preset> 폴더, 또는 프리셋 이름")
    ap.add_argument("--labels", type=Path, help="라벨 CSV(employee_id,left). 없으면 워크북의 라벨 시트를 찾는다")
    ap.add_argument("--mode", choices=["auto", "model", "heuristic"], default="auto")
    ap.add_argument("--weights", type=Path, help="규칙 가중치 덮어쓰기 JSON {신호: 가중치}")
    ap.add_argument("--top", type=int, default=10, help="요약에 넣을 상위 위험 직원 수")
    ap.add_argument("--include-sensitive", action="store_true", help="민감 속성(성별·국적 등)을 피처에 포함")
    # 1단계 질문 정의
    ap.add_argument("--target", help="무엇을 예측하는가 (기본: 자발적 퇴사)")
    ap.add_argument("--horizon-days", type=int, help="기준일 이후 며칠 이내인가 (기본 90)")
    ap.add_argument("--population", help="모집단 설명 (기본: 기준일 현재 재직자 전원)")
    ap.add_argument("--filter", action="append", help="모집단 제한 키=값 (예: 본부=개발본부, 직군=개발직). 반복 가능")
    ap.add_argument("--prompt", default="", help="사용자 요청 원문(기록용)")
    ap.add_argument("--spec", type=Path, help="이전 실행의 analysis_spec.json을 재사용")


def _out_dir(args, fallback_name: str) -> Path:
    out = args.out or (C.DEFAULT_OUT_ROOT / fallback_name)
    out.mkdir(parents=True, exist_ok=True)
    return out


def predict(args) -> tuple[Path, dict]:
    if not args.input:
        raise SystemExit("--input <HR.xlsx>가 필요합니다.")
    ds = load_any(args.input, DATASET_ROOT)
    out = _out_dir(args, Path(args.input).stem)
    print(f"[input] {ds.kind}: {ds.source} · {ds.manifest['company']['name']} · 기준일 {ds.manifest['as_of']} · {ds.manifest['employee_count']}명")
    # 1 질문 정의
    q = QuestionSpec.from_args(getattr(args, "target", None), getattr(args, "horizon_days", None), getattr(args, "population", None),
                               parse_filters(getattr(args, "filter", None)), getattr(args, "spec", None), getattr(args, "prompt", ""))
    q.as_of = ds.manifest["as_of"]
    print(f"[1 질문] {q.sentence()}")
    # 2 데이터 이해 (피처 계산 포함: 기준일 이후 기록은 여기서 제외된다)
    f_all = build_features(ds, args.include_sensitive)
    f, pop = apply_population(f_all, q)
    if pop["after"] == 0:
        raise SystemExit(f"모집단 제한 {pop['filters']}에 해당하는 직원이 없습니다.")
    profile = profile_dataset(ds, f, set(f_all.employee_id.astype(str)))
    f.to_csv(out / "features.csv", index=False, encoding="utf-8-sig")
    miss = f.attrs.get("unavailable", [])
    exc = sum(f.attrs.get("excluded_after_as_of", {}).values())
    print(f"[2 데이터] 테이블 {sum(t['present'] for t in profile['tables'])}개 · 모집단 {pop['after']}/{pop['before']}명 · 신호 {len(f.columns)}열"
          + (f" · 계산 못 한 신호 {len(miss)}개" if miss else "") + f" · 기준일 이후 기록 {exc}행 제외" + (f" · 이슈 {len(profile['issues'])}건" if profile["issues"] else ""))
    labels = load_labels(ds, args.labels)
    if labels is not None:
        labels = labels[labels.index.isin(f.employee_id.astype(str))]
    d = describe_labels(labels, pop["after"])
    print("[labels] " + (f"있음 (행 {d['rows']}, 양성 {d['positives']}, 커버리지 {d['coverage_pct']}%)" if d["present"] else "없음 → 규칙 기반 지수"))
    # 3 가설 → 점수 → 가설 탐색/검정
    weights = json.loads(args.weights.read_text(encoding="utf-8")) if args.weights else None
    if weights is None and getattr(args, "spec", None):
        weights = json.loads(Path(args.spec).read_text(encoding="utf-8")).get("weights_override") or None
    res = score(f, labels, args.mode, args.include_sensitive, weights)
    save_result(res, out)
    print(f"[score] 모드 {res.mode} · 밴드 {res.metrics.get('band_counts')}" + (f" · CV AUC {res.metrics['cv_auc']}" if res.mode == "model" else ""))
    hyp = evaluate_hypotheses(f, res.scores, labels)
    print("[3 가설] " + ", ".join(f"{h['id']} {h['status']}" for h in hyp["hypotheses"]))
    # 4 검증
    val = validate(f, res, labels, q.as_of, weights)
    print("[4 검증] " + " · ".join(f"{c['item']} {c['result']}" for c in val["checklist"]))
    # 5 행동 연결 + 6 재사용
    summary = build_summary(f, res, ds.manifest, args.top, q.to_dict(), profile, hyp, val, pop)
    write_summary(summary, out)
    xlsx = write_result_workbook(f, res, summary, ds.manifest, out)
    spec = write_analysis_spec(summary, res, weights, out)
    print(f"[5 행동] 회사 신호 {len(summary['company_signals'])}개 · 조치 {len(summary['actions'])}개 · 팀별 확인사항 {len(summary['unit_actions'])}팀")
    print(f"[6 재사용] {spec}")
    print(f"[result] {xlsx}")
    print(f"완료: {summary['company']} · 기준일 {summary['as_of']} · {summary['n_employees']}명 · "
          f"높음 {summary['bands']['높음']} / 주의 {summary['bands']['주의']} / 낮음 {summary['bands']['낮음']} · {summary['mode_label']}")
    return xlsx, summary


def dashboard(args) -> Path:
    result = args.result
    if result is None:
        if not args.input:
            raise SystemExit("--result <퇴사위험_결과.xlsx> 또는 --data <HR.xlsx>가 필요합니다.")
        print("[dashboard] 결과 파일이 없어 예측을 먼저 수행합니다.")
        result, _ = predict(args)
    features, scores, meta = read_result_workbook(result)
    out = _out_dir(args, Path(result).parent.name)
    raw = None
    if args.input:
        try:
            raw = load_any(args.input, DATASET_ROOT)
            print(f"[data] 원본 데이터 로드: {raw.source}")
        except Exception as e:  # noqa: BLE001 - 원본은 선택 입력
            print(f"[data] 원본 데이터를 읽지 못해 결과 파일만으로 현황을 만듭니다: {e}")
    manifest = meta["manifest"]
    ov = build_overview(features, str(manifest.get("as_of")), raw)
    p = build_dashboard(features, scores, meta["metrics"], manifest, ov, out / "dashboard.html", meta["unavailable"])
    print(f"[dashboard] {p} · 인력 현황 탭(원본 {'포함' if raw else '없음'}) + 퇴사 위험 탭")
    if args.open:
        if sys.platform == "win32":
            os.startfile(p)  # noqa: S606
        else:
            subprocess.Popen(["xdg-open" if sys.platform.startswith("linux") else "open", str(p)])
    return p


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("predict", help="퇴사 위험 예측 → 결과 엑셀")
    _add_predict_args(p1)
    p1.add_argument("--out", type=Path)
    p2 = sub.add_parser("dashboard", help="결과 엑셀(+원본) → 대시보드 HTML")
    _add_predict_args(p2)
    p2.add_argument("--result", type=Path, help="/predict_attrition이 만든 퇴사위험_결과.xlsx")
    p2.add_argument("--out", type=Path)
    p2.add_argument("--open", action="store_true")
    p3 = sub.add_parser("run", help="predict + dashboard")
    _add_predict_args(p3)
    p3.add_argument("--out", type=Path)
    p3.add_argument("--open", action="store_true")
    args = ap.parse_args(argv)

    if args.cmd == "predict":
        predict(args)
    elif args.cmd == "dashboard":
        dashboard(args)
    else:
        xlsx, _ = predict(args)
        args.result = xlsx
        dashboard(args)


if __name__ == "__main__":
    main()
