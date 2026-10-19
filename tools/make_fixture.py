"""테스트용 합성 HR 픽스처 워크북 생성 (라벨 포함).

    python tools/make_fixture.py [--n 186] [--seed 7] [--out fixtures/hr_fixture_186.xlsx]

설계
- 기준일(as_of) 2026-04-30 시점 재직자 N명. 이후 180일 관측 기간 안에 일부가 퇴사한다(퇴사일·유형 기록).
- 값은 난수이되, 퇴사자 쪽에 약한 신호 편향(몰입 낮음, 밴드 하단, 연장근로 증가, 평가 하락, 승진 보류, 근속 1~3년)을 심는다.
  → 모델이 배울 것이 있어 예측 모드 처리 경로를 검증할 수 있다. 실제 회사 데이터가 아니며 성능 근거로 쓰면 안 된다.
- 기준일 이후 기록(퇴사 발령, 이후 월 근태, 이후 확정 평가)을 일부 포함해 누수 차단(V2)이 실제로 작동하는지 볼 수 있게 한다.
- 시트는 엔진이 읽는 표준 워크북 형식(hr_*, v_*, 개요)과 '퇴사라벨' 시트.
"""
import argparse
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

AS_OF = date(2026, 4, 30)
OBS_END = AS_OF + timedelta(days=180)
DIVS = {"개발본부": ["백엔드팀", "프론트엔드팀", "플랫폼팀", "데이터팀", "QA팀"], "프로덕트본부": ["기획팀", "디자인팀"],
        "비즈니스본부": ["영업팀", "마케팅팀", "고객지원팀"], "경영지원본부": ["인사팀", "재무팀", "총무팀"]}
FAMILY = {"개발본부": "개발직", "프로덕트본부": "기획직", "비즈니스본부": "비즈니스직", "경영지원본부": "경영지원직"}
GRADES = ["L1", "L2", "L3", "L4", "L5", "L6"]
BASE = {1: 4000, 2: 4600, 3: 5400, 4: 6500, 5: 7800, 6: 9500}
SUR = "김이박최정강조윤장임한오서신권황안송류전홍"
GIV = "민서준우지호하은서윤도윤예은시우지민수아하준주원유나지우현우서아은우지안윤서민준"
DIMS = ["몰입", "성장", "보상 인식", "워라밸", "관리자", "자율성", "동료", "비전", "추천의향"]


def make(n: int, seed: int) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    ids = [f"{2026 - int(t):d}{k:03d}" for k, t in enumerate(np.zeros(n), start=1)]
    # 근속(년): 0.1~15, 1~3년 구간 두텁게
    tenure = np.clip(np.concatenate([rng.uniform(0.1, 1, n // 5), rng.uniform(1, 3, n // 3), rng.exponential(5, n - n // 5 - n // 3) + 3]), 0.1, 15)
    rng.shuffle(tenure)
    hire = [AS_OF - timedelta(days=int(t * 365.25)) for t in tenure]
    age = np.clip((24 + tenure + rng.normal(4, 4, n)).round(), 23, 59).astype(int)
    div = rng.choice(list(DIVS), n, p=[0.45, 0.15, 0.25, 0.15])
    team = [rng.choice(DIVS[d]) for d in div]
    level = np.clip((1 + tenure / 2.5 + rng.normal(0, 0.7, n)).round(), 1, 6).astype(int)
    leader = (rng.random(n) < 0.12) & (level >= 3)
    fixed_term = rng.random(n) < 0.12
    on_leave = rng.random(n) < 0.03
    # 잠재 성향(퇴사 경향)과 신호
    latent = rng.normal(0, 1, n) + np.where((tenure >= 1) & (tenure < 3), 0.5, 0)
    engagement = np.clip(3.4 - 0.45 * latent + rng.normal(0, 0.6, n), 1, 5)
    pay_perc = np.clip(3.2 - 0.35 * latent + rng.normal(0, 0.7, n), 1, 5)
    workload = np.clip(3.3 - 0.3 * latent + rng.normal(0, 0.7, n), 1, 5)
    enps = np.clip(6.5 - 0.9 * latent + rng.normal(0, 1.5, n), 0, 10).round()
    band_pos = np.clip(0.5 - 0.12 * latent + rng.normal(0, 0.2, n), 0, 1)
    rating_now = np.clip((3.2 - 0.3 * latent + rng.normal(0, 0.8, n)).round(), 1, 5).astype(int)
    rating_prev = np.clip((rating_now + 0.25 * latent + rng.normal(0, 0.7, n)).round(), 1, 5).astype(int)
    ot_base = np.clip(8 + 3 * rng.normal(0, 1, n), 0, 40)
    ot_trend = 0.6 * latent + rng.normal(0, 1.2, n)
    holds = ((latent > 0.6) & (level < 6) & (rng.random(n) < 0.5)).astype(int) + ((latent > 1.3) & (rng.random(n) < 0.4)).astype(int)
    # 퇴사 여부: 로지스틱(잠재성향) → 180일 내 퇴사. 약 25% 수준
    p_leave = 1 / (1 + np.exp(-(latent * 1.1 - 1.3)))
    leaves = rng.random(n) < p_leave
    left_days = np.where(leaves, rng.integers(10, 180, n), 0)
    left_type = np.where(leaves, rng.choice(["자발적", "비자발적", "계약만료"], n, p=[0.78, 0.1, 0.12]), "")
    left_date = [AS_OF + timedelta(days=int(d)) if l else None for d, l in zip(left_days, leaves)]
    names = [rng.choice(list(SUR)) + "".join(rng.choice(list(GIV), 2)) for _ in range(n)]
    salary = (np.array([BASE[l] for l in level]) * (0.85 + 0.3 * band_pos) * rng.normal(1, 0.03, n)).round(-1).astype(int)
    rating_map = {5: "S", 4: "A", 3: "B", 2: "C", 1: "D"}

    overview = pd.DataFrame([("회사(가상)", "(주)픽스처랩스 · 테스트용 합성 데이터 · 난수 생성"), ("프리셋", "fixture"), ("기준일", AS_OF.isoformat()),
                             ("관측 종료일", OBS_END.isoformat()), ("직원 수", f"{n}명 (기준일 재직자, 이후 퇴사 {int(leaves.sum())}명)"),
                             ("주의", "값은 난수이며 퇴사자 쪽에 약한 신호 편향을 심었다. 실제 회사 데이터가 아니다.")], columns=["항목", "내용"])
    employees = pd.DataFrame(dict(employee_id=ids, name=names, sex=rng.choice(["남", "여"], n), birth_date=[AS_OF.replace(year=AS_OF.year - int(a)) for a in age],
                                  hire_date=hire, hire_type=rng.choice(["신입", "경력"], n), recruit_channel=rng.choice(["채용플랫폼", "사내추천", "헤드헌팅"], n),
                                  education=rng.choice(["고졸", "전문대졸", "대졸", "석사"], n, p=[0.05, 0.15, 0.65, 0.15]), nationality="대한민국",
                                  marital_status=rng.choice(["미혼", "배우자있음"], n), residence_district=rng.choice(["서울 강남구", "경기 성남시", "서울 관악구"], n)))
    snap = pd.DataFrame(dict(employee_id=ids, as_of=AS_OF, name=names, division_name=div, org_unit_name=team, job_family=[FAMILY[d] for d in div],
                             grade_level=level, grade_title=[GRADES[l - 1] for l in level], role_title=np.where(leader, "팀장", "팀원"),
                             work_schedule="자율출퇴근(코어 10-16)", employment_type=np.where(fixed_term, "기간제(계약직)", "정규직"),
                             contract_end_date=[AS_OF + timedelta(days=int(rng.integers(20, 400))) if f else None for f in fixed_term],
                             employment_status=np.where(on_leave, "휴직", "재직"), base_annual_krw10k=salary, hire_date=hire, tenure_years=tenure.round(2), age=age,
                             annual_leave_granted=np.clip(15 + (tenure // 2), 11, 25), annual_leave_used=np.clip((rng.uniform(0.1, 0.6, n) * 15).round(1), 0, 15),
                             last_rating=[rating_map[r] for r in rating_now]))
    comp_rows, promo_rows, act_rows, rev_rows = [], [], [], []
    for i, eid in enumerate(ids):
        lo, hi = BASE[level[i]] * 0.85, BASE[level[i]] * 1.15
        months_since_raise = int(rng.integers(1, 20)) if latent[i] < 0.8 else int(rng.integers(8, 30))
        eff = AS_OF - timedelta(days=30 * months_since_raise)
        comp_rows.append(dict(comp_id=f"CP-{eid}-2", employee_id=eid, effective_from=eff, effective_to=None, base_annual_krw10k=salary[i], pay_band_code=f"B{level[i]}",
                              band_min_krw10k=int(lo), band_max_krw10k=int(hi), change_reason="정기인상", change_pct=round(float(np.clip(4 - 1.2 * latent[i] + rng.normal(0, 1.5), 0, 9)), 1),
                              recorded_at=eff))
        comp_rows.append(dict(comp_id=f"CP-{eid}-1", employee_id=eid, effective_from=max(hire[i], eff - timedelta(days=365)), effective_to=eff - timedelta(days=1),
                              base_annual_krw10k=int(salary[i] * 0.96), pay_band_code=f"B{level[i]}", band_min_krw10k=int(lo), band_max_krw10k=int(hi), change_reason="입사", change_pct=None,
                              recorded_at=max(hire[i], eff - timedelta(days=365))))
        for k in range(holds[i]):
            promo_rows.append(dict(promotion_review_id=f"PR-{eid}-{k}", employee_id=eid, review_year=2026 - k, from_level=level[i], to_level=level[i] + 1, eligible=True,
                                   result="보류", reason="성과 요건 미달", decided_at=date(2025 - k, 12, 15), effective_date=None))
        act_rows.append(dict(action_id=f"PA-{eid}-1", employee_id=eid, effective_date=hire[i], action_type="입사", description="입사"))
        if level[i] > 1 and tenure[i] > 2:
            act_rows.append(dict(action_id=f"PA-{eid}-2", employee_id=eid, effective_date=AS_OF - timedelta(days=int(rng.integers(60, 900))), action_type="승진", description="정기승진"))
        if leaves[i]:   # 기준일 이후 기록(누수 차단 대상)
            act_rows.append(dict(action_id=f"PA-{eid}-9", employee_id=eid, effective_date=left_date[i], action_type="퇴사", description=f"{left_type[i]} 퇴사"))
        rev_rows.append(dict(review_id=f"RV-{eid}-2025H2", cycle_id="2025-H2", employee_id=eid, reviewer_ref="EXT-1", status="확정", self_score=int(np.clip(rating_now[i] + rng.integers(0, 2), 1, 5)),
                             manager_rating=rating_map[rating_now[i]], final_rating=rating_map[rating_now[i]], finalized_at=date(2026, 1, 20)))
        if tenure[i] > 1:
            rev_rows.append(dict(review_id=f"RV-{eid}-2025H1", cycle_id="2025-H1", employee_id=eid, reviewer_ref="EXT-1", status="확정", self_score=int(rating_prev[i]),
                                 manager_rating=rating_map[rating_prev[i]], final_rating=rating_map[rating_prev[i]], finalized_at=date(2025, 7, 20)))
        if not leaves[i] or left_days[i] > 80:   # 기준일 이후 확정 평가(누수 차단 대상)
            rev_rows.append(dict(review_id=f"RV-{eid}-2026H1", cycle_id="2026-H1", employee_id=eid, reviewer_ref="EXT-1", status="확정", self_score=3,
                                 manager_rating="B", final_rating="B", finalized_at=date(2026, 7, 20)))
    att_rows = []
    months = pd.period_range("2025-05", "2026-07", freq="M")   # 기준일(2026-04) 이후 3개월 포함
    for i, eid in enumerate(ids):
        for m in months:
            if m.to_timestamp().date() < hire[i]:
                continue
            if leaves[i] and left_date[i] and m.to_timestamp().date() > left_date[i]:
                continue
            k = (m - pd.Period("2026-04", freq="M")).n   # 0 = 기준월
            trend = ot_trend[i] * max(0, 1 + k / 3) if k > -6 else 0
            att_rows.append(dict(employee_id=eid, pay_month=str(m), scheduled_days=21, attended_days=20, overtime_hours=round(float(np.clip(ot_base[i] + trend + rng.normal(0, 2), 0, 60)), 1),
                                 late_count=int(rng.poisson(0.3 + 0.4 * max(latent[i], 0))), absent_days=int(rng.random() < 0.03 + 0.03 * max(latent[i], 0)),
                                 sick_days=int(rng.random() < 0.05), recognized_hours=round(float(160 + rng.normal(0, 6)), 1)))
    leave_rows = [dict(request_id=f"LR-{eid}-{k}", employee_id=eid, leave_type="연차", start_date=AS_OF - timedelta(days=int(rng.integers(1, 300))), requested_days=1,
                       status=rng.choice(["승인", "승인", "승인", "취소", "반려"], p=[0.6, 0.15, 0.1, 0.1, 0.05]), requested_at=AS_OF - timedelta(days=int(rng.integers(5, 320))))
                  for i, eid in enumerate(ids) for k in range(int(rng.integers(2, 8)))]
    train_rows = [dict(enrollment_id=f"TE-{eid}-{k}", employee_id=eid, course_code="CRS-X", status="수료", completed_at=AS_OF - timedelta(days=int(rng.integers(1, 360))),
                       hours=int(rng.choice([1, 2, 8, 16]))) for i, eid in enumerate(ids) for k in range(int(rng.integers(0, 4) + (latent[i] < 0)))]
    oncall_rows = [dict(oncall_shift_id=f"OC-{eid}-{k}", employee_id=eid, week_start=AS_OF - timedelta(days=7 * int(rng.integers(1, 50))))
                   for i, eid in enumerate(ids) if div[i] == "개발본부" for k in range(int(rng.integers(0, 6)))]
    surveys = pd.DataFrame([dict(survey_id="SV-2025-CULTURE", closed_at=date(2025, 9, 30)), dict(survey_id="SV-2026-PULSE", closed_at=date(2026, 3, 31))])
    questions = pd.DataFrame([dict(survey_id=s, question_id=f"{s}-Q{k + 1:02d}", seq=k + 1, dimension=d, scale="nps0_10" if d == "추천의향" else "likert5")
                              for s in surveys.survey_id for k, d in enumerate(DIMS)])
    resp_rows, ans_rows = [], []
    for s in surveys.survey_id:
        for i, eid in enumerate(ids):
            if hire[i] > surveys.set_index("survey_id").closed_at[s]:
                continue
            responded = rng.random() > (0.08 + 0.1 * max(latent[i], 0))
            resp_rows.append(dict(response_id=f"SR-{s}-{eid}", survey_id=s, employee_id=eid, status="응답" if responded else "미응답"))
            if responded:
                vals = {"몰입": engagement[i], "성장": engagement[i] + rng.normal(0, .5), "보상 인식": pay_perc[i], "워라밸": workload[i], "관리자": engagement[i] + rng.normal(0, .6),
                        "자율성": 3.5 + rng.normal(0, .7), "동료": 3.8 + rng.normal(0, .6), "비전": 3.3 - 0.2 * latent[i] + rng.normal(0, .7), "추천의향": enps[i]}
                for k, d in enumerate(DIMS):
                    v = vals[d]
                    v = int(np.clip(round(v), 0, 10)) if d == "추천의향" else int(np.clip(round(v), 1, 5))
                    ans_rows.append(dict(answer_id=f"SA-{s}-{eid}-{k}", response_id=f"SR-{s}-{eid}", question_id=f"{s}-Q{k + 1:02d}", employee_id=eid, value=v))
    # left = 기본 질문 정의와 같은 "기준일 이후 90일 이내 자발적 퇴사". 다른 정의용 컬럼도 함께 둔다.
    labels = pd.DataFrame(dict(employee_id=ids, left=[int(l and d <= 90 and t == "자발적") for l, d, t in zip(leaves, left_days, left_type)],
                               left_any_90d=[int(l and d <= 90) for l, d in zip(leaves, left_days)], left_any_180d=leaves.astype(int),
                               left_date=left_date, left_type=left_type, observed_until=OBS_END,
                               label_definition="left: 기준일 이후 90일 이내 자발적 퇴사=1, 그 외 0 (관측 종료일까지 재직 또는 다른 유형)"))
    return {"개요": overview, "v_employees_current": snap, "hr_employees": employees, "hr_compensation_history": pd.DataFrame(comp_rows),
            "hr_promotion_reviews": pd.DataFrame(promo_rows), "hr_personnel_actions": pd.DataFrame(act_rows), "hr_performance_reviews": pd.DataFrame(rev_rows),
            "v_attendance_monthly": pd.DataFrame(att_rows), "hr_leave_requests": pd.DataFrame(leave_rows), "hr_training_enrollments": pd.DataFrame(train_rows),
            "hr_oncall_shifts": pd.DataFrame(oncall_rows), "hr_surveys": surveys, "hr_survey_questions": questions, "hr_survey_responses": pd.DataFrame(resp_rows),
            "hr_survey_answers": pd.DataFrame(ans_rows), "퇴사라벨": labels}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=186)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parents[1] / "fixtures" / "hr_fixture_186.xlsx")
    a = ap.parse_args()
    sheets = make(a.n, a.seed)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(a.out, engine="openpyxl") as w:
        for name, df in sheets.items():
            df.to_excel(w, sheet_name=name, index=False)
    lab = sheets["퇴사라벨"]
    print(f"{a.out} · 직원 {a.n}명 · 180일 내 퇴사 {int(lab.left_any_180d.sum())}명 · 90일 내 자발적 퇴사(left) {int(lab.left.sum())}명 · 시트 {len(sheets)}개 · {a.out.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
