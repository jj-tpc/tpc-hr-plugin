"""HR 리스크 터미널: 단일 HTML, 외부 리소스 없음(인라인 SVG). 밀도·연동·상태색·키보드가 핵심.

레이아웃
  상단 상태줄  회사 · 기준일 · 분석 모드 · 입력 파일 · 방법론 6단계 상태(Q D H V A R) · 검색(/) · 공유용 토글
  좌측 레일    조직 트리(본부>팀: 인원·높음·평균 위험 히트셀) — 클릭하면 모든 패널이 그 조직으로 필터(표시 필터, 재계산 없음)
  패널         신호 보드 | 가설 H1~H9 | 팀×신호 히트맵 | 워치리스트(스파크라인) | 검증 V1~V9·HR 확인사항 | 구성 | 월별 추세
  드로어       선택 직원 상세: 신호별 회사 평균 대비 불릿, 모델/규칙 기여, 값의 출처

색: 상태색만 의미를 가진다(critical/warning/good). 히트맵은 위험 방향으로 부호를 맞춘 z의 발산 스케일(파랑=안전쪽, 빨강=위험쪽, 회색=평균).
    범주색은 파랑 하나(선택·강조)와 회색 단계만 쓴다. 숫자는 tabular-nums.
"""
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from . import config as C
from .features import ALLOWED_FEATURES, FEATURE_DOCS, PLAIN

SOURCE_TABLE = {   # 신호 → 값의 출처(드로어 표시용)
    "tenure_years": "v_employees_current", "grade_level": "v_employees_current", "is_leader": "v_employees_current", "is_fixed_term": "v_employees_current",
    "contract_ending_90d": "v_employees_current", "on_leave": "v_employees_current", "base_annual_krw10k": "v_employees_current",
    "band_position": "hr_compensation_history", "months_since_raise": "hr_compensation_history", "last_raise_pct": "hr_compensation_history",
    "promotion_holds_2y": "hr_promotion_reviews", "months_since_promotion": "hr_personnel_actions", "transfers_count": "hr_personnel_actions",
    "last_rating_score": "hr_performance_reviews", "rating_trend": "hr_performance_reviews", "self_manager_gap": "hr_performance_reviews",
    "ot_hours_m6": "v_attendance_monthly", "ot_trend": "v_attendance_monthly", "late_count_m6": "v_attendance_monthly", "absent_days_m6": "v_attendance_monthly",
    "leave_usage_rate": "v_employees_current", "leave_rejected_12m": "hr_leave_requests", "training_hours_12m": "hr_training_enrollments",
    "oncall_weeks_12m": "hr_oncall_shifts", "survey_engagement": "hr_survey_answers", "survey_pay_perception": "hr_survey_answers",
    "survey_workload": "hr_survey_answers", "survey_enps": "hr_survey_answers",
}

SHORT = {   # 히트맵 열 머리글(≤5자)
    "tenure_years": "근속", "age": "나이", "grade_level": "직급", "is_leader": "보직", "is_fixed_term": "기간제", "contract_ending_90d": "만료임박",
    "on_leave": "휴직", "base_annual_krw10k": "연봉", "band_position": "밴드위치", "months_since_raise": "미인상月", "last_raise_pct": "인상률",
    "promotion_holds_2y": "승진보류", "months_since_promotion": "미승진月", "transfers_count": "전보", "last_rating_score": "평가", "rating_trend": "평가추세",
    "self_manager_gap": "자기-확정", "ot_hours_m6": "연장", "ot_trend": "연장추세", "late_count_m6": "지각", "absent_days_m6": "결근", "sick_days_m6": "병가",
    "leave_usage_rate": "연차율", "leave_rejected_12m": "휴가반려", "training_hours_12m": "교육", "oncall_weeks_12m": "온콜",
    "survey_engagement": "몰입", "survey_pay_perception": "보상인식", "survey_workload": "워라밸", "survey_enps": "eNPS", "survey_nonresponse": "미응답",
}

TEMPLATE = r"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root{
  --page:#0d0d0d;--panel:#1a1a19;--panel-2:#202020;--line:#2c2c2a;--axis:#383835;
  --ink:#f0efec;--ink-2:#c3c2b7;--muted:#898781;
  --accent:#3987e5;--accent-dim:#1c5cab;
  --good:#0ca30c;--warn:#fab219;--serious:#ec835a;--crit:#d03b3b;
  --font:system-ui,-apple-system,"Segoe UI","Malgun Gothic",sans-serif;
}
*{box-sizing:border-box}
html,body{margin:0;background:var(--page);color:var(--ink);font:12px/1.45 var(--font)}
.num{font-variant-numeric:tabular-nums}
button,input,select{font:inherit;color:inherit}
a{color:var(--accent)}

/* 상태줄 */
.bar{display:flex;align-items:center;gap:14px;padding:6px 12px;border-bottom:1px solid var(--line);background:var(--panel);position:sticky;top:0;z-index:5;white-space:nowrap;overflow:hidden}
.bar .co{font-weight:700;font-size:13px}
.bar .meta{color:var(--ink-2)}
.chip{display:inline-flex;align-items:center;gap:5px;padding:1px 7px;border:1px solid var(--line);border-radius:3px;font-size:11px;color:var(--ink-2)}
.chip.mode-pred{border-color:var(--good);color:var(--good)}.chip.mode-diag{border-color:var(--warn);color:var(--warn)}
.steps{display:flex;gap:4px;margin-left:auto}
.step{display:inline-flex;align-items:center;gap:4px;padding:1px 6px;border-radius:3px;background:var(--panel-2);font-size:11px;color:var(--ink-2)}
.step i{width:7px;height:7px;border-radius:50%;background:var(--muted);display:inline-block}
.step.pass i{background:var(--good)}.step.warn i{background:var(--warn)}.step.fail i{background:var(--crit)}
.bar input{background:var(--page);border:1px solid var(--line);border-radius:3px;padding:3px 8px;width:220px;color:var(--ink)}
.bar input:focus{outline:1px solid var(--accent)}
.tog{background:var(--panel-2);border:1px solid var(--line);border-radius:3px;padding:3px 8px;cursor:pointer;color:var(--ink-2)}
.tog.on{border-color:var(--accent);color:var(--accent)}
.kbd{color:var(--muted);font-size:11px}
.kbd b{display:inline-block;border:1px solid var(--axis);border-radius:3px;padding:0 4px;font-weight:600;color:var(--ink-2);margin:0 1px}

/* 본문 */
.app{display:grid;grid-template-columns:236px 1fr;min-height:calc(100vh - 34px)}
.rail{border-right:1px solid var(--line);background:var(--panel);padding:10px 0;overflow:auto;position:sticky;top:34px;height:calc(100vh - 34px)}
.rail h3{margin:0 10px 6px;font-size:11px;color:var(--muted);font-weight:600;letter-spacing:.4px;text-transform:uppercase}
.hero{padding:6px 12px 10px;border-bottom:1px solid var(--line);margin-bottom:8px}
.hero .v{font-size:30px;font-weight:700;line-height:1;color:var(--crit)}
.hero .l{color:var(--ink-2);margin-top:4px}
.hero .sub{color:var(--muted);font-size:11px;margin-top:2px}
.tree{list-style:none;margin:0;padding:0}
.tree li{display:grid;grid-template-columns:1fr 34px 30px 14px;gap:6px;align-items:center;padding:3px 12px;cursor:pointer;color:var(--ink-2)}
.tree li.div{color:var(--ink);font-weight:600;margin-top:4px}
.tree li.unit{padding-left:22px}
.tree li:hover{background:var(--panel-2)}
.tree li.sel{background:#15233a;color:var(--ink);box-shadow:inset 2px 0 0 var(--accent)}
.tree .n{text-align:right;color:var(--muted)}.tree .hi{text-align:right;color:var(--crit)}
.cell{width:14px;height:10px;border-radius:2px;display:inline-block}
.rail .all{padding:3px 12px;cursor:pointer;color:var(--ink-2)}.rail .all.sel{background:#15233a;color:var(--ink);box-shadow:inset 2px 0 0 var(--accent)}
.legend{padding:8px 12px;color:var(--muted);font-size:11px;border-top:1px solid var(--line);margin-top:8px}
.legend .cell{vertical-align:middle}

.grid{display:grid;grid-template-columns:repeat(12,1fr);gap:8px;padding:8px}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:4px;padding:8px 10px;min-width:0}
.panel h2{margin:0 0 6px;font-size:11px;color:var(--muted);font-weight:600;letter-spacing:.4px;text-transform:uppercase;display:flex;gap:8px;align-items:baseline}
.panel h2 .r{margin-left:auto;font-weight:400;text-transform:none;letter-spacing:0}
.c3{grid-column:span 3}.c4{grid-column:span 4}.c5{grid-column:span 5}.c6{grid-column:span 6}.c7{grid-column:span 7}.c8{grid-column:span 8}.c12{grid-column:span 12}
@media(max-width:1200px){.c3,.c4,.c5,.c6,.c7,.c8{grid-column:span 12}.app{grid-template-columns:1fr}.rail{position:static;height:auto;border-right:0;border-bottom:1px solid var(--line)}}

table{width:100%;border-collapse:collapse}
th{color:var(--muted);font-weight:600;text-align:left;padding:3px 6px;border-bottom:1px solid var(--line);font-size:11px;white-space:nowrap;cursor:pointer;user-select:none}
td{padding:3px 6px;border-bottom:1px solid #222;white-space:nowrap;vertical-align:middle}
tr:hover td{background:var(--panel-2)}
tr.sel td{background:#15233a}
td.r,th.r{text-align:right}
.band{display:inline-block;padding:0 6px;border-radius:3px;font-size:11px;font-weight:600;border:1px solid}
.band.높음{color:var(--crit);border-color:var(--crit)}.band.주의{color:var(--warn);border-color:var(--warn)}.band.낮음{color:var(--good);border-color:var(--good)}
.status{display:inline-flex;align-items:center;gap:5px}
.status i{width:8px;height:8px;border-radius:50%;display:inline-block;background:var(--muted)}
.status.통과 i{background:var(--good)}.status.경고 i{background:var(--warn)}.status.실패 i{background:var(--crit)}
.hyp{display:inline-block;padding:0 6px;border-radius:3px;font-size:11px;border:1px solid var(--axis);color:var(--ink-2)}
.hyp.sup{border-color:var(--good);color:var(--good)}.hyp.opp{border-color:var(--crit);color:var(--crit)}.hyp.exp{border-color:var(--axis);color:var(--muted)}
.muted{color:var(--muted)}.dim{color:var(--ink-2)}
.wrap{white-space:normal}
.scroll{overflow:auto;max-height:420px}
.heat{display:grid;gap:2px;align-items:center;min-width:max-content}
.heat .hd{color:var(--muted);font-size:10px;text-align:center;line-height:1.1;padding:0 1px 4px;word-break:keep-all;overflow:hidden}
.heat .rn{color:var(--ink-2);padding-right:6px;text-align:right;cursor:pointer}
.heat .rn:hover{color:var(--ink)}
.heat .hc{height:18px;border-radius:2px;position:relative;cursor:default}
.heat .hc span{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:10px;color:rgba(240,239,236,.0)}
.heat .hc:hover span{color:var(--ink)}
.heat .tot{color:var(--ink-2);text-align:right;padding-left:6px}
.sig{display:grid;grid-template-columns:1fr 56px 56px 70px 56px;gap:8px;align-items:center;padding:2px 0;border-bottom:1px solid #222}
.sig.head{color:var(--muted);font-size:11px}
.sig .r{text-align:right}
.spark svg{display:block}
.bullet{display:grid;grid-template-columns:150px 1fr 60px 48px;gap:8px;align-items:center;padding:2px 0;border-bottom:1px solid #222;font-size:11px}
.bullet .lbl{color:var(--ink-2)}
.drawer{position:fixed;left:236px;right:0;bottom:0;max-height:46vh;background:var(--panel);border-top:1px solid var(--accent-dim);box-shadow:0 -8px 24px rgba(0,0,0,.5);transform:translateY(100%);transition:transform .18s ease;z-index:6;overflow:auto;padding:10px 14px}
.drawer.on{transform:translateY(0)}
.drawer .head{display:flex;gap:14px;align-items:baseline;flex-wrap:wrap;margin-bottom:8px}
.drawer .head b{font-size:14px}
.drawer .cols{display:grid;grid-template-columns:1.4fr 1fr;gap:16px}
@media(max-width:1200px){.drawer{left:0}}
.close{margin-left:auto;background:none;border:1px solid var(--line);border-radius:3px;padding:2px 8px;cursor:pointer;color:var(--ink-2)}
.empty{color:var(--muted);padding:12px 0;text-align:center}
.mini{display:grid;grid-template-columns:70px 1fr 30px;gap:6px;align-items:center;padding:1px 0}
.mini .l{color:var(--ink-2);font-size:11px}.mini .n{text-align:right;color:var(--muted);font-size:11px}
.mini .b{height:9px;border-radius:2px;background:var(--accent-dim)}
.tip{position:fixed;pointer-events:none;background:#0b0b0b;border:1px solid var(--axis);border-radius:3px;padding:5px 8px;font-size:11px;color:var(--ink);z-index:9;display:none;max-width:320px;white-space:normal}
.share .pii{filter:blur(5px);user-select:none}
.foot{padding:6px 12px;color:var(--muted);font-size:11px;border-top:1px solid var(--line)}
</style>
</head>
<body>
<div class="bar">
  <span class="co">__COMPANY__</span>
  <span class="meta num">기준일 __AS_OF__</span>
  <span class="chip __MODECLS__">__MODE_LABEL__</span>
  <span class="meta">입력 <span class="num">__SOURCE__</span></span>
  <span class="meta num">엔진 v__ENGINE__</span>
  <div class="steps" id="steps"></div>
  <input id="q" placeholder="이름·사번·팀 검색  ( / )">
  <button class="tog" id="share" title="이름·사번을 가립니다 (s)">공유용</button>
  <span class="kbd" title="↑↓ 워치리스트 이동 · Enter 상세 · Esc 필터/드로어 해제 · / 검색 · 1/2/3 밴드 · s 공유용"><b>↑↓</b><b>⏎</b><b>Esc</b><b>1-3</b></span>
</div>

<div class="app">
  <aside class="rail">
    <div class="hero"><div class="v num" id="heroV">–</div><div class="l">위험 ‘높음’ 인원 <span class="muted" id="heroN"></span></div><div class="sub" id="heroSub"></div></div>
    <h3>조직</h3>
    <div class="all sel" id="allOrg">전체 <span class="num muted" id="allN"></span></div>
    <ul class="tree" id="tree"></ul>
    <div class="legend">히트셀 = 평균 위험 지수 · <span class="cell" style="background:#3987e5"></span> 낮음 → <span class="cell" style="background:#d03b3b"></span> 높음<br>클릭 = 표시 필터(재계산 없음)</div>
  </aside>

  <main>
    <div class="grid">
      <section class="panel c7"><h2>신호 보드 <span class="r" id="sigScope"></span></h2><div id="sigBoard"></div></section>
      <section class="panel c5"><h2>가설 H1~H9 <span class="r" id="hypKind"></span></h2><div id="hyp"></div></section>
      <section class="panel c12"><h2>팀 × 신호 히트맵 <span class="r">셀 = 팀 평균 z(위험 방향으로 부호 정렬) · 빨강 = 위험 쪽 · 파랑 = 안전 쪽 · ≠ = 모델 계수 방향이 가설과 다름 · 호버 = 값 · 가로 스크롤 →</span></h2><div class="scroll" id="heat"></div></section>
      <section class="panel c7"><h2>워치리스트 <span class="r" id="wlMeta"></span></h2><div class="scroll" id="wl"></div></section>
      <section class="panel c5">
        <h2>검증 V1~V9 <span class="r" id="valOverall"></span></h2><div id="val"></div>
        <h2 style="margin-top:10px">회사 전체 신호 → 조치</h2><div id="acts"></div>
        <h2 style="margin-top:10px">팀별 확인사항</h2><div id="units"></div>
      </section>
      <section class="panel c6"><h2>구성 <span class="r" id="compScope"></span></h2><div id="comp" style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px"></div></section>
      <section class="panel c6"><h2>월별 추세 <span class="r" id="monMeta"></span></h2><div id="mon"></div></section>
    </div>
    <div class="foot">__ABOUT__</div>
  </main>
</div>

<div class="drawer" id="drawer"></div>
<div class="tip" id="tip"></div>

<script>
const DATA=__DATA__, DOCS=__DOCS__, OV=__OVERVIEW__, EX=__EXTRAS__, META=__META__;
const R=DATA.rows, FEATS=DATA.feats, DIR=DATA.dir, COEF=DATA.coef||{}, Z=DATA.z, STATS=DATA.stats, SRC=DATA.src, SHORT=DATA.short;
const $=s=>document.querySelector(s), esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const fmt=(v,d=2)=>v===null||v===undefined||Number.isNaN(v)?'–':(+v).toFixed(d);
const state={div:null,unit:null,band:'',q:'',sel:null,share:false,sortK:'risk_score',sortDir:-1};
const BANDC={'높음':'var(--crit)','주의':'var(--warn)','낮음':'var(--good)'};

/* 발산 색: adjusted z ∈ [-2,2] → 파랑(-) ↔ 회색(0) ↔ 빨강(+) */
function lerp(a,b,t){return a+(b-a)*t}
function hex2(h){return [1,3,5].map(i=>parseInt(h.slice(i,i+2),16))}
function mix(h1,h2,t){const a=hex2(h1),b=hex2(h2);return `rgb(${a.map((v,i)=>Math.round(lerp(v,b[i],t))).join(',')})`}
function divColor(z){const t=Math.max(-1,Math.min(1,z/2));return t<0?mix('#383835','#3987e5',-t):mix('#383835','#d03b3b',t)}
function riskColor(p){return p>=.7?'#d03b3b':p>=.4?'#fab219':'#3987e5'}
function adj(k,z){return (DIR[k]||0)*z}

/* 필터 */
function visible(){const q=state.q.trim();return R.filter(r=>(!state.div||r.division_name===state.div)&&(!state.unit||r.org_unit_name===state.unit)&&(!state.band||r.risk_band===state.band)&&(!q||[r.name,r.employee_id,r.org_unit_name,r.division_name].join(' ').includes(q)))}
function scopeLabel(){return state.unit||state.div||'전체'}

/* 상태줄: 방법론 6단계 */
(function steps(){
  const cl=EX.checklist||[], over=EX.overall_ko||'';
  const st=k=>k==='통과'?'pass':k==='경고'?'warn':k==='실패'?'fail':'';
  const items=[['Q','질문 정의',EX.question&&Object.keys(EX.question).length?'pass':''],['D','데이터 이해',cl.length?'pass':''],['H','가설',(EX.hypotheses||[]).length?'pass':''],
    ['V','검증',st(over)],['A','행동 연결',(EX.unit_actions||[]).length?'pass':''],['R','재사용','pass']];
  $('#steps').innerHTML=items.map(([k,t,s])=>`<span class="step ${s}" title="${t}"><i></i>${k}</span>`).join('');
})();

/* 레일 */
function renderRail(){
  const by={};R.forEach(r=>{(by[r.division_name]=by[r.division_name]||{}); (by[r.division_name][r.org_unit_name]=by[r.division_name][r.org_unit_name]||[]).push(r)});
  const hi=R.filter(r=>r.risk_band==='높음').length;
  $('#heroV').textContent=hi; $('#heroN').textContent=`/ ${R.length}`; $('#heroSub').textContent=`주의 ${R.filter(r=>r.risk_band==='주의').length} · 낮음 ${R.filter(r=>r.risk_band==='낮음').length} · 평균 ${fmt(R.reduce((a,r)=>a+r.risk_score,0)/R.length)}`;
  $('#allN').textContent=R.length;
  const divs=Object.entries(by).map(([d,units])=>{const rows=Object.values(units).flat();return [d,units,rows]}).sort((a,b)=>avg(b[2])-avg(a[2]));
  const single=divs.length===1;   // 본부 구분이 없는 명부: 본부 행을 생략하고 팀만
  $('#tree').innerHTML=divs.map(([d,units,rows])=>(single?'':`<li class="div ${state.div===d&&!state.unit?'sel':''}" data-div="${esc(d)}"><span>${esc(d)}</span><span class="n num">${rows.length}</span><span class="hi num">${rows.filter(r=>r.risk_band==='높음').length||''}</span><span class="cell" style="background:${riskColor(avg(rows))}" title="평균 ${fmt(avg(rows))}"></span></li>`)+
    Object.entries(units).sort((a,b)=>avg(b[1])-avg(a[1])).map(([u,rows])=>`<li class="unit ${state.unit===u?'sel':''}" data-div="${esc(d)}" data-unit="${esc(u)}"><span>${esc(u)}</span><span class="n num">${rows.length}</span><span class="hi num">${rows.filter(r=>r.risk_band==='높음').length||''}</span><span class="cell" style="background:${riskColor(avg(rows))}" title="평균 ${fmt(avg(rows))}"></span></li>`).join('')).join('');
  $('#allOrg').classList.toggle('sel',!state.div&&!state.unit);
  document.querySelectorAll('#tree li').forEach(li=>li.onclick=()=>{state.div=li.dataset.div;state.unit=li.dataset.unit||null;renderAll()});
  $('#allOrg').onclick=()=>{state.div=null;state.unit=null;renderAll()};
}
function avg(rows){return rows.length?rows.reduce((a,r)=>a+r.risk_score,0)/rows.length:0}

/* 신호 보드 */
function sparkbar(vals,k){ // 5구간 히스토그램
  const v=vals.filter(x=>x!==null&&x!==undefined);if(!v.length)return '';const mn=Math.min(...v),mx=Math.max(...v),w=(mx-mn)||1;const bins=[0,0,0,0,0];v.forEach(x=>bins[Math.min(4,Math.floor((x-mn)/w*5))]++);const m=Math.max(...bins);
  return `<svg width="56" height="14">${bins.map((b,i)=>`<rect x="${i*11}" y="${14-Math.round(b/m*13)}" width="9" height="${Math.round(b/m*13)}" rx="1" fill="#898781"/>`).join('')}</svg>`}
function renderSignals(){
  const rows=visible(); const scoped=!!(state.div||state.unit||state.band||state.q.trim());
  $('#sigScope').textContent=`${scopeLabel()} ${rows.length}명 · 평균 / ${scoped?'회사 대비 σ':'σ(전체 선택 시 생략)'} / 분포 / 높음군 z`;
  const hi=rows.filter(r=>r.risk_band==='높음');
  const items=FEATS.filter(k=>STATS[k].sd>0).map(k=>{const vals=rows.map(r=>r[k]).filter(v=>v!==null&&v!==undefined);if(!vals.length)return null;const mean=vals.reduce((a,b)=>a+b,0)/vals.length;const dz=STATS[k].sd?(mean-STATS[k].mean)/STATS[k].sd:0;
    const ref=DIR[k]===0;   // 참고 신호: 위험 방향이 없으므로 높음군 z는 부호 없이 보여주고 맨 아래로
    const hz=hi.length?hi.reduce((a,r)=>a+(ref?((Z[r.employee_id]||{})[k]||0):adj(k,(Z[r.employee_id]||{})[k]||0)),0)/hi.length:null;return {k,mean,dz:ref?dz:adj(k,dz),hz,vals,ref}}).filter(Boolean).sort((a,b)=>(a.ref-b.ref)||((b.hz??-9)-(a.hz??-9)));
  $('#sigBoard').innerHTML=`<div class="sig head"><span>신호</span><span class="r">평균</span><span class="r">σ(위험+)</span><span></span><span class="r">높음군 z</span></div>`+items.map(it=>{
    const c=it.dz>0.5?'var(--crit)':it.dz<-0.5?'var(--accent)':'var(--ink-2)';
    const dis=COEF[it.k]!==undefined&&Math.sign(COEF[it.k])!==DIR[it.k];
    const c2=it.ref?'var(--muted)':it.hz>0.3?'var(--crit)':'var(--ink-2)';
    return `<div class="sig" data-k="${it.k}"><span class="dim" title="${esc(DOCS[it.k][1])}${dis?' · 모델 계수 부호('+(COEF[it.k]>0?'+':'−')+')가 가설 방향과 다름: 표본이 작을 때 흔하며, 색은 가설 방향 기준':''}${it.ref?' · 참고 신호: 위험 방향 없음, z는 값 기준':''}">${esc(DOCS[it.k][0])}${it.ref?' <span class="muted">(참고)</span>':''}${dis?' <span class="muted" title="모델 계수 방향 ≠ 가설">≠</span>':''}</span><span class="r num">${fmt(it.mean,it.k.includes('krw')?0:2)}</span><span class="r num" style="color:${it.ref?'var(--muted)':c}">${scoped?(it.dz>=0?'+':'')+fmt(it.dz,2):'<span class="muted">·</span>'}</span><span class="spark">${sparkbar(it.vals,it.k)}</span><span class="r num" style="color:${c2}">${it.hz===null?'–':(it.hz>=0?'+':'')+fmt(it.hz,2)}</span></div>`}).join('');
}

/* 가설 */
(function renderHyp(){
  const hs=EX.hypotheses||[]; $('#hypKind').textContent=hs.length?(hs[0].status.startsWith('탐색')?'탐색적 증거 (라벨 없음)':'검증 결과 (라벨 기반, 단변량)'):'';
  if(!hs.length){$('#hyp').innerHTML='<div class="empty">가설 시트 없음</div>';return}
  const cls=s=>s.startsWith('지지')?'sup':s.startsWith('반대')?'opp':s.startsWith('탐색')?'exp':'';
  $('#hyp').innerHTML=`<table><tbody>${hs.map(h=>{const top=h.signals.slice().sort((a,b)=>(parseFloat(b.auc)||parseFloat(b.strong_pct)||0)-(parseFloat(a.auc)||parseFloat(a.strong_pct)||0))[0]||{};
    const aucBar=top.auc?`<svg width="60" height="8"><rect x="0" y="0" width="60" height="8" rx="2" fill="#2c2c2a"/><rect x="30" y="0" width="${Math.max(0,(parseFloat(top.auc)-.5))*120}" height="8" rx="2" fill="${parseFloat(top.auc)>=.6?'var(--good)':'var(--ink-2)'}"/></svg>`:'';
    return `<tr><td class="muted">${h.id}</td><td class="wrap dim" style="max-width:260px">${esc(h.hypothesis)}</td><td><span class="hyp ${cls(h.status)}">${esc(h.status)}</span></td><td class="num muted">${top.auc?'AUC '+fmt(top.auc,2):top.strong_pct?'두드러짐 '+top.strong_pct+'%':''}</td><td>${aucBar}</td></tr>`}).join('')}</tbody></table>`;
})();

/* 히트맵 */
function renderHeat(){
  const feats=FEATS.filter(k=>DIR[k]!==0&&STATS[k].sd>0);   // 방향 있는 신호 중 값이 변하는 것만
  const units={};R.forEach(r=>(units[r.org_unit_name]=units[r.org_unit_name]||[]).push(r));
  const rows=Object.entries(units).map(([u,rs])=>({u,div:rs[0].division_name,n:rs.length,hi:rs.filter(r=>r.risk_band==='높음').length,avg:avg(rs),
    z:feats.map(k=>{const v=rs.map(r=>(Z[r.employee_id]||{})[k]).filter(x=>x!==undefined&&x!==null);return v.length?adj(k,v.reduce((a,b)=>a+b,0)/v.length):null})})).sort((a,b)=>b.avg-a.avg);
  const cols=`120px repeat(${feats.length},46px) 40px 48px`;
  let h=`<div class="heat" style="grid-template-columns:${cols}"><div></div>${feats.map(k=>`<div class="hd" title="${esc(DOCS[k][0])} — ${esc(DOCS[k][1])}${COEF[k]!==undefined&&Math.sign(COEF[k])!==DIR[k]?' · 모델 계수 방향이 가설과 다름':''}">${esc(SHORT[k]||DOCS[k][0])}${COEF[k]!==undefined&&Math.sign(COEF[k])!==DIR[k]?'<span class="muted">≠</span>':''}</div>`).join('')}<div class="hd">인원</div><div class="hd">높음%</div>`;
  rows.forEach(r=>{const sel=state.unit===r.u;h+=`<div class="rn" data-unit="${esc(r.u)}" data-div="${esc(r.div)}" style="${sel?'color:var(--accent)':''}">${esc(r.u)}</div>`+r.z.map((z,i)=>z===null?`<div class="hc" style="background:#141414"></div>`:`<div class="hc" style="background:${divColor(z)};${sel?'outline:1px solid var(--accent)':''}" data-tip="${esc(r.u)} · ${esc(DOCS[feats[i]][0])}<br>팀 평균 z ${z>=0?'+':''}${fmt(z,2)} (${z>0.3?'위험 쪽':z<-0.3?'안전 쪽':'평균 근처'})"><span>${z>=0?'+':''}${fmt(z,1)}</span></div>`).join('')+`<div class="tot num">${r.n}</div><div class="tot num" style="color:${r.hi/r.n>=.3?'var(--crit)':'var(--ink-2)'}">${Math.round(100*r.hi/r.n)}</div>`});
  $('#heat').innerHTML=h+'</div>';
  document.querySelectorAll('#heat .rn').forEach(el=>el.onclick=()=>{state.unit=el.dataset.unit;state.div=el.dataset.div;renderAll()});
}

/* 워치리스트 */
function sparkline(vals){const v=(vals||[]).map(x=>x===null?null:+x);if(!v.some(x=>x!==null))return '';const xs=v.filter(x=>x!==null),mn=Math.min(...xs),mx=Math.max(...xs),w=(mx-mn)||1;const pts=v.map((x,i)=>x===null?null:[i*12+2,16-Math.round((x-mn)/w*12)]).filter(Boolean);
  return `<svg width="62" height="18"><polyline fill="none" stroke="#898781" stroke-width="1.5" points="${pts.map(p=>p.join(',')).join(' ')}"/><circle cx="${pts[pts.length-1][0]}" cy="${pts[pts.length-1][1]}" r="2.2" fill="#3987e5"/></svg>`}
function renderWatch(){
  let rows=visible().slice().sort((a,b)=>{const x=a[state.sortK],y=b[state.sortK];return (x>y?1:x<y?-1:0)*state.sortDir});
  $('#wlMeta').textContent=`${scopeLabel()} · ${rows.length}명 · 밴드 ${state.band||'전체'} · 클릭/Enter = 상세`;
  const checked=JSON.parse(localStorage.getItem('hr-checked')||'{}');
  const th=(k,t,r)=>`<th class="${r?'r':''}" data-k="${k}">${t}${state.sortK===k?(state.sortDir<0?' ▾':' ▴'):''}</th>`;
  $('#wl').innerHTML=`<table><thead><tr>${th('risk_score','위험',true)}${th('risk_band','밴드')}${th('employee_id','사번')}${th('name','이름')}${th('org_unit_name','팀')}${th('grade_title','직급')}${th('tenure_years','근속',true)}<th>연장 6M</th><th>주요 신호</th><th>확인</th></tr></thead><tbody>${
    rows.map(r=>`<tr data-id="${r.employee_id}" class="${state.sel===r.employee_id?'sel':''}"><td class="r num" style="color:${BANDC[r.risk_band]}">${fmt(r.risk_score)}</td><td><span class="band ${r.risk_band}">${r.risk_band}</span></td><td class="num pii">${esc(r.employee_id)}</td><td class="pii">${esc(r.name)}</td><td class="dim">${esc(r.org_unit_name)}</td><td class="dim">${esc(r.grade_title)}</td><td class="r num">${fmt(r.tenure_years,1)}</td><td class="spark">${sparkline((OV.spark||{})[r.employee_id])}</td><td class="muted" style="max-width:380px;overflow:hidden;text-overflow:ellipsis" title="${esc(r.top_drivers)}">${esc(r.top_drivers)}</td><td><input type="checkbox" ${checked[r.employee_id]?'checked':''} data-chk="${r.employee_id}" title="확인함 (이 브라우저에만 저장)"></td></tr>`).join('')}</tbody></table>`;
  document.querySelectorAll('#wl th[data-k]').forEach(t=>t.onclick=()=>{const k=t.dataset.k;state.sortDir=(state.sortK===k)?-state.sortDir:(['risk_score','tenure_years'].includes(k)?-1:1);state.sortK=k;renderWatch()});
  document.querySelectorAll('#wl tr[data-id]').forEach(tr=>tr.onclick=e=>{if(e.target.type==='checkbox')return;select(tr.dataset.id)});
  document.querySelectorAll('#wl [data-chk]').forEach(c=>c.onchange=()=>{const m=JSON.parse(localStorage.getItem('hr-checked')||'{}');if(c.checked)m[c.dataset.chk]=Date.now();else delete m[c.dataset.chk];try{localStorage.setItem('hr-checked',JSON.stringify(m))}catch{}});
}

/* 검증·조치·팀별 */
(function renderVal(){
  const cl=EX.checklist||[]; $('#valOverall').textContent=EX.overall_ko?`종합 ${EX.overall_ko}`:'';
  const short=d=>d.replace(/\s*\(근거:.*$/,'');
  $('#val').innerHTML=cl.length?`<table style="table-layout:fixed"><colgroup><col style="width:28px"><col style="width:120px"><col style="width:72px"><col></colgroup><tbody>${cl.map(c=>`<tr title="${esc(c.detail)}"><td class="muted">${c.id}</td><td class="dim wrap">${esc(c.item)}</td><td><span class="status ${c.status_ko}"><i></i>${c.status_ko}</span></td><td class="muted wrap" style="font-size:11px;line-height:1.3">${esc(short(c.detail))}</td></tr>`).join('')}</tbody></table>`:'<div class="empty">검증 시트 없음</div>';
  const acts=EX.actions||[];$('#acts').innerHTML=acts.length?`<table><tbody>${acts.map(a=>`<tr><td class="muted">${esc(a.category)}</td><td class="dim">${esc(a.signal)}</td><td class="wrap">${esc(a.action)}</td></tr>`).join('')}</tbody></table>`:'<div class="empty">없음</div>';
  const u=EX.unit_actions||[];$('#units').innerHTML=u.length?`<table><tbody>${u.map(x=>`<tr style="cursor:pointer" data-unit="${esc(x.unit)}" data-div="${esc(x.division)}"><td class="dim">${esc(x.unit)}</td><td class="r num muted">${x.n}</td><td class="r num" style="color:${riskColor(parseFloat(x.avg_risk))}">${fmt(x.avg_risk)}</td><td class="wrap muted">${esc(x.signals)}</td><td class="wrap">${esc(x.checks)}</td></tr>`).join('')}</tbody></table>`:'<div class="empty">없음</div>';
  document.querySelectorAll('#units tr[data-unit]').forEach(tr=>tr.onclick=()=>{state.unit=tr.dataset.unit;state.div=tr.dataset.div;renderAll()});
})();

/* 구성(선택 범위) */
function miniBars(title,items){const m=Math.max(1,...items.map(i=>i.n));return `<div><div class="muted" style="font-size:11px;margin-bottom:4px">${title}</div>${items.map(i=>`<div class="mini"><span class="l">${esc(i.name)}</span><span class="b" style="width:${Math.round(100*i.n/m)}%"></span><span class="n num">${i.n}</span></div>`).join('')}</div>`}
function bins(vals,edges,labels){const c=labels.map(()=>0);vals.forEach(v=>{if(v===null||v===undefined)return;for(let i=0;i<edges.length-1;i++)if(v>=edges[i]&&v<edges[i+1]){c[i]++;break}});return labels.map((l,i)=>({name:l,n:c[i]}))}
function renderComp(){const rows=visible();$('#compScope').textContent=`${scopeLabel()} ${rows.length}명`;
  const grade=Object.entries(rows.reduce((m,r)=>(m[r.grade_title]=(m[r.grade_title]||0)+1,m),{})).sort((a,b)=>(rows.find(r=>r.grade_title===a[0])?.grade_level||0)-(rows.find(r=>r.grade_title===b[0])?.grade_level||0)).map(([k,v])=>({name:k,n:v}));
  const emp=Object.entries(rows.reduce((m,r)=>(m[r.employment_type]=(m[r.employment_type]||0)+1,m),{})).map(([k,v])=>({name:k,n:v}));
  $('#comp').innerHTML=miniBars('근속',bins(rows.map(r=>r.tenure_years),[0,1,3,6,10,15,99],['<1년','1~3','3~6','6~10','10~15','15+']))+miniBars('직급',grade)+miniBars('고용형태 · 재직',emp.concat([{name:'휴직',n:rows.filter(r=>r.employment_status==='휴직').length},{name:'보직자',n:rows.filter(r=>r.is_leader).length}]));
}

/* 월별 추세: 소규모 다중(한 축씩) */
function lineChart(labels,vals,color,unit){const W=560,H=70,P=28;const mx=Math.max(1,...vals);const x=i=>P+i*(W-P-6)/Math.max(1,labels.length-1),y=v=>H-14-(v/mx)*(H-24);
  return `<svg width="100%" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" style="display:block"><line x1="${P}" y1="${H-14}" x2="${W-6}" y2="${H-14}" stroke="#383835"/><text x="0" y="${y(mx)+4}" fill="#898781" font-size="9">${fmt(mx,0)}${unit}</text><text x="0" y="${H-12}" fill="#898781" font-size="9">0</text>
   <polyline fill="none" stroke="${color}" stroke-width="2" points="${vals.map((v,i)=>`${x(i)},${y(v)}`).join(' ')}"/>${vals.map((v,i)=>`<circle cx="${x(i)}" cy="${y(v)}" r="2.5" fill="${color}"><title>${labels[i]} · ${fmt(v,1)}${unit}</title></circle>`).join('')}
   ${labels.map((l,i)=>i%2===0||i===labels.length-1?`<text x="${x(i)}" y="${H-3}" fill="#898781" font-size="9" text-anchor="middle">${l.slice(2)}</text>`:'').join('')}</svg>`}
function barChart(labels,vals,color,unit){const W=560,H=70,P=28;const mx=Math.max(1,...vals);const bw=(W-P-6)/labels.length;const y=v=>H-14-(v/mx)*(H-24);
  return `<svg width="100%" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" style="display:block"><line x1="${P}" y1="${H-14}" x2="${W-6}" y2="${H-14}" stroke="#383835"/><text x="0" y="${y(mx)+4}" fill="#898781" font-size="9">${fmt(mx,0)}${unit}</text><text x="0" y="${H-12}" fill="#898781" font-size="9">0</text>
   ${vals.map((v,i)=>`<rect x="${P+i*bw+2}" y="${y(v)}" width="${Math.max(2,bw-4)}" height="${H-14-y(v)}" rx="2" fill="${color}"><title>${labels[i]} · ${v}${unit}</title></rect>`).join('')}
   ${labels.map((l,i)=>i%2===0||i===labels.length-1?`<text x="${P+i*bw+bw/2}" y="${H-3}" fill="#898781" font-size="9" text-anchor="middle">${l.slice(2)}</text>`:'').join('')}</svg>`}
(function renderMonthly(){const m=OV.monthly;if(!m){$('#mon').innerHTML='<div class="empty">원본 HR 파일을 함께 주면 월별 연장근로·지각 추세와 설문 비교가 표시됩니다</div>';$('#monMeta').textContent='';return}
  $('#monMeta').textContent=`회사 전체 · ${m.labels[0]} ~ ${m.labels[m.labels.length-1]} (기준일 이후 월 제외)`;
  let h=`<div class="muted" style="font-size:11px">월평균 연장근로 (시간/인)</div>${lineChart(m.labels,m.overtime,'#3987e5','h')}<div class="muted" style="font-size:11px;margin-top:6px">지각 합계 (건)</div>${barChart(m.labels,m.late,'#898781','')}`;
  if(OV.survey&&OV.survey.length){const dims=Object.keys(OV.survey[OV.survey.length-1].dims).filter(d=>d!=='추천의향');const cur=OV.survey[OV.survey.length-1],prev=OV.survey.length>1?OV.survey[0]:null;
    h+=`<div class="muted" style="font-size:11px;margin-top:8px">설문 차원 평균 (1~5) · <span style="color:#3987e5">■</span> ${esc(cur.survey)}${prev?` <span style="color:#898781">■</span> ${esc(prev.survey)}`:''}${cur.dims['추천의향']!==undefined?` · eNPS 추천의향 <b class="num" style="color:var(--ink)">${fmt(cur.dims['추천의향'],1)}</b>/10`:''}</div><div style="display:grid;grid-template-columns:repeat(${dims.length},1fr);gap:4px;margin-top:4px">${dims.map(d=>`<div style="text-align:center"><div class="muted" style="font-size:10px">${esc(d)}</div><svg width="100%" height="46" viewBox="0 0 40 46"><rect x="4" y="${46-cur.dims[d]/5*40}" width="14" height="${cur.dims[d]/5*40}" rx="2" fill="#3987e5"><title>${esc(cur.survey)} ${fmt(cur.dims[d],2)}</title></rect>${prev?`<rect x="22" y="${46-(prev.dims[d]||0)/5*40}" width="14" height="${(prev.dims[d]||0)/5*40}" rx="2" fill="#898781"><title>${esc(prev.survey)} ${fmt(prev.dims[d],2)}</title></rect>`:''}</svg><div class="num" style="font-size:11px">${fmt(cur.dims[d],2)}</div></div>`).join('')}</div>`}
  $('#mon').innerHTML=h;
})();

/* 드로어 */
function select(id){state.sel=id;renderWatch();const r=R.find(x=>x.employee_id===id);if(!r)return;const z=Z[id]||{};
  const rows=FEATS.map(k=>({k,v:r[k],z:z[k]})).filter(x=>x.v!==null&&x.v!==undefined).sort((a,b)=>Math.abs(adj(b.k,b.z||0))-Math.abs(adj(a.k,a.z||0)));
  const bul=rows.map(x=>{const az=adj(x.k,x.z||0);const w=Math.min(100,Math.abs(az)/2*50);const left=az<0?50-w:50;const c=DIR[x.k]===0?'#898781':az>0?'#d03b3b':'#3987e5';
    return `<div class="bullet"><span class="lbl" title="${esc(DOCS[x.k][1])} · 출처 ${esc(SRC[x.k]||'')}">${esc(DOCS[x.k][0])}</span><svg width="100%" height="10" viewBox="0 0 100 10" preserveAspectRatio="none"><rect x="0" y="4" width="100" height="2" fill="#2c2c2a"/><rect x="${left}" y="2" width="${w}" height="6" rx="1" fill="${c}"/><rect x="49.5" y="0" width="1" height="10" fill="#898781"/></svg><span class="num r dim">${fmt(x.v,x.k.includes('krw')?0:2)}</span><span class="num r muted">${(x.z||0)>=0?'+':''}${fmt(x.z,1)}σ</span></div>`}).join('');
  $('#drawer').innerHTML=`<div class="head"><b class="pii">${esc(r.name)}</b><span class="num pii muted">${esc(r.employee_id)}</span><span class="dim">${esc(r.division_name)} / ${esc(r.org_unit_name)} · ${esc(r.grade_title)} · ${esc(r.role_title)} · ${esc(r.employment_type)} · ${esc(r.employment_status)} · 근속 <span class="num">${fmt(r.tenure_years,1)}</span>년</span><span class="band ${r.risk_band}">${r.risk_band} ${fmt(r.risk_score)}</span><button class="close" id="closeD">닫기 Esc</button></div>
   <div class="cols"><div><div class="muted" style="font-size:11px;margin-bottom:4px">신호별 회사 평균 대비 (막대 = 위험 방향 z, 가운데 선 = 회사 평균 · 회색 = 참고 신호)</div>${bul}</div>
   <div><div class="muted" style="font-size:11px">주요 신호 (${META.mode==='model'?'모델 계수 × 표준화값':'가중치 × 표준화값'} 기여 상위)</div><div class="wrap" style="margin:4px 0 10px">${esc(r.top_drivers)}</div>
   <div class="muted" style="font-size:11px">기술 표기</div><div class="wrap dim" style="margin:4px 0 10px">${esc(r.top_drivers_tech||'')}</div>
   <div class="muted" style="font-size:11px">읽을 때</div><div class="wrap muted" style="margin-top:4px">신호는 확인해 볼 지점이며 개인의 성향이 아니다. ${META.mode==='model'?'예측 확률은 제공된 라벨 패턴에 기반하며 무작위 교차검증 AUC '+fmt(META.cv_auc,3)+'은 시간 분리 평가가 아니다.':'진단 지수는 예측 확률이 아니라 회사 내 상대 순위다.'} 성별·국적·혼인 등 민감 속성은 쓰지 않았다.</div></div></div>`;
  $('#drawer').classList.add('on');$('#closeD').onclick=closeDrawer;
}
function closeDrawer(){$('#drawer').classList.remove('on');state.sel=null;renderWatch()}

/* 툴팁 */
const tip=$('#tip');document.addEventListener('mousemove',e=>{const t=e.target.closest('[data-tip]');if(!t){tip.style.display='none';return}tip.innerHTML=t.dataset.tip;tip.style.display='block';tip.style.left=Math.min(window.innerWidth-330,e.clientX+12)+'px';tip.style.top=(e.clientY+14)+'px'});

/* 키보드·검색·공유 */
$('#q').oninput=e=>{state.q=e.target.value;renderAll()};
$('#share').onclick=()=>{state.share=!state.share;document.body.classList.toggle('share',state.share);$('#share').classList.toggle('on',state.share)};
document.addEventListener('keydown',e=>{if(e.target.tagName==='INPUT'){if(e.key==='Escape'){e.target.blur();state.q='';e.target.value='';renderAll()}return}
  if(e.key==='/'){e.preventDefault();$('#q').focus();return}
  if(e.key==='s'){$('#share').click();return}
  if(e.key==='Escape'){if($('#drawer').classList.contains('on'))closeDrawer();else{state.div=null;state.unit=null;state.band='';renderAll()}return}
  if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();const ids=[...document.querySelectorAll('#wl tr[data-id]')].map(t=>t.dataset.id);if(!ids.length)return;let i=ids.indexOf(state.sel);i=e.key==='ArrowDown'?Math.min(ids.length-1,i+1):Math.max(0,i-1);state.sel=ids[i];renderWatch();document.querySelector(`#wl tr[data-id="${state.sel}"]`)?.scrollIntoView({block:'nearest'});if($('#drawer').classList.contains('on'))select(state.sel);return}
  if(e.key==='Enter'&&state.sel){select(state.sel)}
  if(['1','2','3'].includes(e.key)){state.band={'1':'높음','2':'주의','3':'낮음'}[e.key]===state.band?'':{'1':'높음','2':'주의','3':'낮음'}[e.key];renderAll()}
});

function renderAll(){renderRail();renderSignals();renderHeat();renderWatch();renderComp()}
renderAll();
</script>
</body>
</html>
"""


def _clean(v):
    if isinstance(v, (np.floating, float)):
        return None if np.isnan(v) else round(float(v), 3)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if isinstance(v, pd.Timestamp):
        return v.date().isoformat()
    return v


def build_dashboard(features: pd.DataFrame, scores: pd.DataFrame, metrics: dict, manifest: dict, overview: dict,
                    out_path: Path, unavailable: list | None = None, extras: dict | None = None, share: bool = False) -> Path:
    """share=True: 공유용. 이름·사번을 실제로 제거(가명 P-001…)하고 스파크라인 키도 같이 바꾼다. 블러가 아니라 데이터 자체가 없다."""
    from . import __version__
    extras = extras or {}
    df = features.merge(scores, on="employee_id", how="left")
    if share:
        order = df.sort_values("risk_score", ascending=False).employee_id.tolist()
        alias = {eid: f"P-{i + 1:03d}" for i, eid in enumerate(order)}
        overview = dict(overview)
        if overview.get("spark"):
            overview["spark"] = {alias[k]: v for k, v in overview["spark"].items() if k in alias}
        df["employee_id"] = df["employee_id"].map(alias)
        df["name"] = "비식별"
        for c in ("top_drivers_tech",):
            if c in df:
                df[c] = ""
        extras = {k: v for k, v in extras.items() if k != "question"} | {"question": extras.get("question", {})}
    if "drivers_plain" in df:
        df["top_drivers_tech"] = df["top_drivers"]
        df["top_drivers"] = df["drivers_plain"]
    for c in ("division_name", "org_unit_name", "grade_title", "role_title", "employment_type", "employment_status", "job_family"):
        df[c] = df[c].fillna("미지정") if c in df else "미지정"
    for c in ("tenure_years", "risk_score", "grade_level"):
        df[c] = pd.to_numeric(df.get(c), errors="coerce")
    df["risk_score"] = df["risk_score"].fillna(0.0)
    df["is_leader"] = pd.to_numeric(df.get("is_leader"), errors="coerce").fillna(0).astype(int)

    feats = [c for c in ALLOWED_FEATURES if c in df and df[c].notna().any()]
    mode = metrics.get("mode", "heuristic")
    coefs = metrics.get("coefficients") or {}
    # 색의 '위험 방향'은 가설(FEATURE_DOCS) 기준으로 고정한다. 작은 표본의 모델 계수 부호는 흔들리므로 색을 바꾸지 않고,
    # 계수 부호가 가설과 다르면 신호 보드·히트맵 머리글에 ≠ 표시만 한다. 방향 0(참고) 신호는 모델 모드에서 계수 부호를 쓴다.
    direction, coef_sign = {}, {}
    for k in feats:
        d = int(FEATURE_DOCS[k][2])
        if mode == "model" and k in coefs and abs(coefs[k]) > 1e-9:
            coef_sign[k] = 1 if coefs[k] > 0 else -1
            if d == 0:
                d = coef_sign[k]
        direction[k] = d
    stats = {}
    for k in feats:
        s = pd.to_numeric(df[k], errors="coerce")
        stats[k] = dict(mean=_clean(s.mean()), sd=_clean(s.std(ddof=0)) or 0, coverage=round(100 * float(s.notna().mean()), 1))
    Z = pd.DataFrame(index=df.employee_id)
    for k in feats:
        s = pd.to_numeric(df[k], errors="coerce")
        sd = s.std(ddof=0)
        Z[k] = (((s - s.mean()) / sd) if sd and not np.isnan(sd) else s * 0).clip(-3, 3).to_numpy()
    z_by_emp = {eid: {k: _clean(v) for k, v in row.items() if v is not None and not (isinstance(v, float) and np.isnan(v))} for eid, row in zip(Z.index, Z.to_dict("records"))}
    rows = [{k: _clean(v) for k, v in r.items()} for r in df.to_dict("records")]

    if mode == "model":
        mode_label = f"예측 모드 · 양성 {metrics.get('positives')}명 학습 · CV AUC {metrics.get('cv_auc')}"
        mode_cls = "mode-pred"
        about = (f"퇴사 위험 지수는 제공된 라벨로 학습한 로지스틱 회귀의 예측 확률이다({metrics.get('algorithm')}). 무작위 층화 교차검증 AUC {metrics.get('cv_auc')}는 시간 분리 평가가 아니므로 출시 성능 근거가 아니다. "
                 "히트맵·신호 보드·드로어의 색은 가설의 위험 방향 기준이며, 모델 계수 부호가 가설과 다른 신호는 ≠로 표시했다.")
    else:
        mode_label = "진단 모드 · 규칙 기반 신호 지수 · 예측 아님"
        mode_cls = "mode-diag"
        about = ("퇴사 위험 지수는 공개 가중치로 신호를 합친 회사 내 상대 지수(0~1)이며 예측 확률이 아니다. 개인 평가나 인사 조치의 단독 근거로 쓰면 안 된다. "
                 "히트맵·신호 보드의 위험 방향은 가설(FEATURE_DOCS)의 방향을 따른다.")
    about += " 성별·국적·체류자격·혼인·가족·주거·거주지·병역·나이·병가·설문 미응답은 개인 점수에 쓰지 않았다. 모든 필터는 표시 필터(재계산 없음)다. 외부 리소스를 쓰지 않아 오프라인에서도 열린다."
    if share:
        about = "공유용 버전: 이름과 사번을 제거하고 위험 순 가명(P-001…)으로 바꿨다. 원본 식별 정보는 이 파일에 들어 있지 않다. " + about
    if unavailable:
        about += " 입력에 없어 계산하지 못한 신호: " + ", ".join(FEATURE_DOCS[c][0] for c in unavailable if c in FEATURE_DOCS) + "."

    data = dict(rows=rows, feats=feats, dir=direction, coef=coef_sign, z=z_by_emp, stats=stats, src=SOURCE_TABLE, short=SHORT)
    meta = dict(mode=mode, cv_auc=metrics.get("cv_auc"), positives=metrics.get("positives"), as_of=str(manifest.get("as_of")), company=str(manifest["company"]["name"]))
    html = (TEMPLATE.replace("__TITLE__", f"{manifest['company']['name']} HR 리스크 터미널" + (" (공유용)" if share else ""))
            .replace("__COMPANY__", str(manifest["company"]["name"])).replace("__AS_OF__", str(manifest.get("as_of")))
            .replace("__MODECLS__", mode_cls).replace("__MODE_LABEL__", mode_label)
            .replace("__SOURCE__", str(manifest.get("source_file") or "")).replace("__ENGINE__", __version__)
            .replace("__ABOUT__", about + f" 생성 {datetime.now().strftime('%Y-%m-%d %H:%M')}.")
            .replace("__DOCS__", json.dumps({k: list(v) for k, v in FEATURE_DOCS.items()}, ensure_ascii=False))
            .replace("__OVERVIEW__", json.dumps(overview, ensure_ascii=False, default=_clean))
            .replace("__EXTRAS__", json.dumps(extras, ensure_ascii=False, default=_clean))
            .replace("__META__", json.dumps(meta, ensure_ascii=False, default=_clean))
            .replace("__DATA__", json.dumps(data, ensure_ascii=False, default=_clean)))
    out_path.write_text(html, encoding="utf-8")
    return out_path
