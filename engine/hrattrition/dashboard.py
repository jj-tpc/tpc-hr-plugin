"""단일 HTML 대시보드: '인력 현황' 탭 + '퇴사 위험' 탭. 데이터는 JSON으로 임베드, 차트는 Chart.js(cdnjs)."""
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from .features import FEATURE_DOCS

CHART_JS = "https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"

TEMPLATE = r"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<script src="__CHART_JS__"></script>
<style>
:root{--bg:#0b0f17;--card:#121a26;--line:#1f2a3a;--fg:#e6edf7;--muted:#8fa0b8;--accent:#5ee1ff;--hi:#ff5c7a;--mid:#ffb547;--lo:#5ad48a;--violet:#a78bfa;}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.5 "Pretendard","Segoe UI","Malgun Gothic",sans-serif}
header{padding:18px 28px 0;border-bottom:1px solid var(--line)}
.hrow{display:flex;gap:18px;align-items:baseline;flex-wrap:wrap}
h1{margin:0;font-size:20px;letter-spacing:.3px}.sub{color:var(--muted)}
.badge{padding:3px 10px;border-radius:999px;font-size:12px;border:1px solid var(--line);background:#0f1622}
.badge.heur{border-color:var(--mid);color:var(--mid)}.badge.model{border-color:var(--lo);color:var(--lo)}
nav{display:flex;gap:4px;margin-top:12px}
nav button{background:transparent;border:0;border-bottom:2px solid transparent;color:var(--muted);padding:10px 16px;font:inherit;font-weight:600;cursor:pointer}
nav button.on{color:var(--fg);border-bottom-color:var(--accent)}
main{padding:20px 28px;display:none;grid-template-columns:repeat(12,1fr);gap:18px}main.on{display:grid}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px}
.kpis{grid-column:span 12;display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(160px,1fr))}
.kpi .v{font-size:26px;font-weight:700}.kpi .l{color:var(--muted);font-size:12px}
.c3{grid-column:span 3}.c4{grid-column:span 4}.c6{grid-column:span 6}.c8{grid-column:span 8}.c12{grid-column:span 12}
@media(max-width:1000px){.c3,.c4,.c6,.c8{grid-column:span 12}}
h2{margin:0 0 10px;font-size:14px;color:var(--muted);font-weight:600;text-transform:uppercase;letter-spacing:.6px}
table{width:100%;border-collapse:collapse;font-size:13px}th,td{padding:7px 8px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}
th{color:var(--muted);font-weight:600;cursor:pointer;user-select:none}tr:hover td{background:#17202e}
.band{padding:2px 8px;border-radius:6px;font-size:12px;font-weight:600}
.band.높음{background:rgba(255,92,122,.18);color:var(--hi)}.band.주의{background:rgba(255,181,71,.18);color:var(--mid)}.band.낮음{background:rgba(90,212,138,.16);color:var(--lo)}
.bar{height:6px;border-radius:3px;background:#1d2838;position:relative;display:inline-block;width:80px;vertical-align:middle}.bar i{position:absolute;left:0;top:0;bottom:0;border-radius:3px;background:linear-gradient(90deg,var(--lo),var(--mid),var(--hi))}
select,input{background:#0f1622;color:var(--fg);border:1px solid var(--line);border-radius:8px;padding:6px 10px;font:inherit}
.toolbar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:10px}
.drivers{color:var(--muted);font-size:12px;white-space:normal;max-width:460px}
#detail .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:8px 16px;font-size:13px}
#detail .k{color:var(--muted)}#detail .warn{color:var(--hi)}#detail .good{color:var(--lo)}
.note{color:var(--muted);font-size:12px;margin-top:8px}
canvas{max-height:280px}
.empty{color:var(--muted);font-size:13px;padding:20px 0;text-align:center}
</style>
</head>
<body>
<header>
  <div class="hrow"><h1>__COMPANY__ · HR 대시보드</h1><span class="sub">기준일 __AS_OF__ · 생성 __GENERATED__</span><span class="badge __MODE__">__MODE_LABEL__</span></div>
  <nav><button class="on" data-tab="ov">인력 현황</button><button data-tab="risk">퇴사 위험</button></nav>
</header>

<main id="tab-ov" class="on">
  <section class="kpis" id="ovKpis"></section>
  <section class="card c4"><h2>본부별 인원</h2><canvas id="ovDiv"></canvas></section>
  <section class="card c4"><h2>직군 구성</h2><canvas id="ovFam"></canvas></section>
  <section class="card c4"><h2>직급 분포</h2><canvas id="ovGrade"></canvas></section>
  <section class="card c4"><h2>근속 분포</h2><canvas id="ovTenure"></canvas></section>
  <section class="card c4"><h2>연령대</h2><canvas id="ovAge"></canvas></section>
  <section class="card c4"><h2>고용형태</h2><canvas id="ovType"></canvas></section>
  <section class="card c8" id="ovMonthlyCard"><h2>월별 근태 추세 (월평균 연장근로 · 지각 합계)</h2><canvas id="ovMonthly"></canvas></section>
  <section class="card c4" id="ovSurveyCard"><h2>설문 차원별 평균 (최근 설문)</h2><canvas id="ovSurvey"></canvas></section>
</main>

<main id="tab-risk">
  <section class="kpis" id="kpis"></section>
  <section class="card c4"><h2>위험 지수 분포</h2><canvas id="hist"></canvas></section>
  <section class="card c4"><h2>본부별 평균 위험</h2><canvas id="byDiv"></canvas></section>
  <section class="card c4"><h2>직군별 평균 위험</h2><canvas id="byFam"></canvas></section>
  <section class="card c6"><h2>근속 대비 위험</h2><canvas id="scatter"></canvas><div class="note">점을 누르면 아래 상세가 바뀝니다.</div></section>
  <section class="card c6"><h2>'높음' 그룹의 주요 신호 (회사 평균 대비)</h2><canvas id="drivers"></canvas><div class="note">위험 밴드 '높음' 직원들의 신호 표준화 값(z) 평균. 붉은색은 위험 방향.</div></section>
  <section class="card c12">
    <h2>직원별 위험 지수</h2>
    <div class="toolbar">
      <select id="fDiv"><option value="">모든 본부</option></select>
      <select id="fBand"><option value="">모든 밴드</option><option>높음</option><option>주의</option><option>낮음</option></select>
      <input id="fQ" placeholder="이름·팀·사번 검색">
      <span class="sub" id="count"></span>
    </div>
    <div style="overflow:auto;max-height:520px"><table id="tbl"><thead><tr>
      <th data-k="risk_score">위험</th><th data-k="risk_band">밴드</th><th data-k="employee_id">사번</th><th data-k="name">이름</th>
      <th data-k="division_name">본부</th><th data-k="org_unit_name">팀</th><th data-k="grade_title">직급</th><th data-k="tenure_years">근속</th>
      <th>주요 신호</th></tr></thead><tbody></tbody></table></div>
  </section>
  <section class="card c12" id="detail"><h2>직원 상세</h2><div class="sub">표의 행이나 산점도의 점을 누르세요.</div></section>
  <section class="card c12"><h2>이 대시보드에 대해</h2><div class="note">__ABOUT__</div></section>
</main>

<script>
const DATA = __DATA__;
const DOCS = __DOCS__;
const OV = __OVERVIEW__;
const R = DATA.rows;
const css = getComputedStyle(document.documentElement);
const col = n => css.getPropertyValue(n).trim();
const PAL = ['#5ee1ff','#a78bfa','#5ad48a','#ffb547','#ff5c7a','#4f9cf9','#f472b6','#34d399','#fbbf24','#94a3b8','#c084fc','#22d3ee'];
const bandColor = b => b==='높음'?col('--hi'):b==='주의'?col('--mid'):col('--lo');
Chart.defaults.color = col('--muted'); Chart.defaults.borderColor = col('--line'); Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;

document.querySelectorAll('nav button').forEach(b=>b.onclick=()=>{document.querySelectorAll('nav button').forEach(x=>x.classList.toggle('on',x===b));document.querySelectorAll('main').forEach(m=>m.classList.toggle('on',m.id==='tab-'+b.dataset.tab));});

function kpi(el,items){items.forEach(([l,v,c])=>{if(v===null||v===undefined)return;el.insertAdjacentHTML('beforeend',`<div class="card kpi"><div class="v" style="color:${c||'inherit'}">${v}</div><div class="l">${l}</div></div>`)})}
function emptyCard(el){el.parentElement.insertAdjacentHTML('beforeend','<div class="empty">데이터 없음</div>');el.remove();}
function bar(id,rows,horizontal,color){const el=document.getElementById(id);if(!rows||!rows.length){emptyCard(el);return;}
 new Chart(el,{type:'bar',data:{labels:rows.map(r=>r.name),datasets:[{data:rows.map(r=>r.n),backgroundColor:color||rows.map((_,i)=>PAL[i%PAL.length])}]},options:{indexAxis:horizontal?'y':'x',plugins:{legend:{display:false}},scales:{[horizontal?'x':'y']:{ticks:{precision:0}}}}});}
function doughnut(id,rows){const el=document.getElementById(id);if(!rows||!rows.length){emptyCard(el);return;}
 new Chart(el,{type:'doughnut',data:{labels:rows.map(r=>`${r.name} (${r.n})`),datasets:[{data:rows.map(r=>r.n),backgroundColor:rows.map((_,i)=>PAL[i%PAL.length]),borderWidth:0}]},options:{plugins:{legend:{position:'right'}},cutout:'60%'}});}

// ── 현황 탭 ──
kpi(document.getElementById('ovKpis'),[["재직 인원",OV.headcount+"명"],["휴직 중",OV.on_leave+"명"],["기간제",OV.fixed_term+"명"],["보직자",OV.leaders+"명"],
 ["평균 근속",OV.avg_tenure!==null?OV.avg_tenure+"년":null],["평균 나이",OV.avg_age!==null?OV.avg_age+"세":null],["입사 1년 미만",OV.new_hires_12m!==null?OV.new_hires_12m+"명":null],
 ["연차 사용률",OV.leave&&OV.leave.rate!==null?OV.leave.rate+"%":null]]);
bar('ovDiv',OV.by_division,true); doughnut('ovFam',OV.by_family); bar('ovGrade',OV.by_grade,false,col('--violet'));
bar('ovTenure',OV.tenure_bins,false,col('--accent')); bar('ovAge',OV.age_bins,false,col('--lo')); doughnut('ovType',OV.by_employment_type);
if(OV.monthly){new Chart(ovMonthly,{data:{labels:OV.monthly.labels,datasets:[{type:'line',label:'월평균 연장근로(h)',data:OV.monthly.overtime,borderColor:col('--mid'),backgroundColor:col('--mid'),tension:.3,yAxisID:'y'},{type:'bar',label:'지각 합계(건)',data:OV.monthly.late,backgroundColor:'rgba(94,225,255,.35)',yAxisID:'y2'}]},
 options:{scales:{y:{position:'left',title:{display:true,text:'시간'}},y2:{position:'right',grid:{drawOnChartArea:false},ticks:{precision:0}}}}});}else{document.getElementById('ovMonthlyCard').innerHTML='<h2>월별 근태 추세</h2><div class="empty">원본 데이터 파일을 함께 주면 표시됩니다</div>';}
if(OV.survey&&OV.survey.length){const dims=Object.keys(OV.survey[OV.survey.length-1].dims);new Chart(ovSurvey,{type:'bar',data:{labels:dims,datasets:OV.survey.map((s,i)=>({label:s.survey,data:dims.map(d=>s.dims[d]),backgroundColor:i===OV.survey.length-1?col('--accent'):'rgba(143,160,184,.5)'}))},options:{indexAxis:'y',scales:{x:{min:0,max:10}}}});}else{document.getElementById('ovSurveyCard').innerHTML='<h2>설문 차원별 평균</h2><div class="empty">원본 데이터 파일을 함께 주면 표시됩니다</div>';}

// ── 위험 탭 ──
const hi = R.filter(r=>r.risk_band==='높음').length, mid = R.filter(r=>r.risk_band==='주의').length;
const avg = R.reduce((a,r)=>a+r.risk_score,0)/Math.max(R.length,1);
kpi(document.getElementById('kpis'),[["분석 인원",R.length+"명"],["위험 높음",hi+"명",col('--hi')],["주의",mid+"명",col('--mid')],["평균 위험 지수",avg.toFixed(2)],
 ["계약 만료 90일 내",R.filter(r=>r.contract_ending_90d).length+"명"],[DATA.metric_label,DATA.metric_value]]);
const bins = Array.from({length:10},(_,i)=>R.filter(r=>r.risk_score>=i/10 && r.risk_score<(i+1)/10 || (i===9&&r.risk_score===1)).length);
new Chart(hist,{type:'bar',data:{labels:bins.map((_,i)=>`${i/10}`),datasets:[{data:bins,backgroundColor:bins.map((_,i)=>i>=7?col('--hi'):i>=4?col('--mid'):col('--lo'))}]},options:{plugins:{legend:{display:false}},scales:{y:{ticks:{precision:0}}}}});
function groupAvg(key){const m={};R.forEach(r=>{(m[r[key]]=m[r[key]]||[]).push(r.risk_score)});return Object.entries(m).map(([k,v])=>[k,v.reduce((a,b)=>a+b,0)/v.length,v.length]).sort((a,b)=>b[1]-a[1]);}
function hbar(id,rows){new Chart(document.getElementById(id),{type:'bar',data:{labels:rows.map(r=>`${r[0]} (${r[2]})`),datasets:[{data:rows.map(r=>r[1]),backgroundColor:rows.map(r=>r[1]>=.6?col('--hi'):r[1]>=.45?col('--mid'):col('--accent'))}]},options:{indexAxis:'y',plugins:{legend:{display:false}},scales:{x:{min:0,max:1}}}});}
hbar('byDiv',groupAvg('division_name')); hbar('byFam',groupAvg('job_family'));
const sc = new Chart(scatter,{type:'scatter',data:{datasets:['높음','주의','낮음'].map(b=>({label:b,data:R.filter(r=>r.risk_band===b).map(r=>({x:r.tenure_years,y:r.risk_score,id:r.employee_id})),backgroundColor:bandColor(b),pointRadius:5,pointHoverRadius:7}))},
  options:{scales:{x:{title:{display:true,text:'근속(년)'}},y:{min:0,max:1,title:{display:true,text:'위험 지수'}}},plugins:{tooltip:{callbacks:{label:c=>{const r=R.find(x=>x.employee_id===c.raw.id);return `${r.name} · ${r.org_unit_name} · ${r.risk_score}`}}}},
  onClick:(e,els)=>{if(els.length){const d=sc.data.datasets[els[0].datasetIndex].data[els[0].index];showDetail(d.id)}}}});
const Z = DATA.z_high;
const zk = Object.entries(Z).filter(([k])=>DOCS[k]&&DOCS[k][2]!==0).sort((a,b)=>Math.abs(b[1]*DOCS[b[0]][2])-Math.abs(a[1]*DOCS[a[0]][2])).slice(0,12);
new Chart(drivers,{type:'bar',data:{labels:zk.map(([k])=>DOCS[k][0]),datasets:[{data:zk.map(([k,v])=>v),backgroundColor:zk.map(([k,v])=>(v*DOCS[k][2])>0?col('--hi'):col('--lo'))}]},options:{indexAxis:'y',plugins:{legend:{display:false}},scales:{x:{title:{display:true,text:'z (0 = 회사 평균)'}}}}});
const fDiv=document.getElementById('fDiv'),fBand=document.getElementById('fBand'),fQ=document.getElementById('fQ'),tb=document.querySelector('#tbl tbody');
[...new Set(R.map(r=>r.division_name))].sort().forEach(d=>fDiv.insertAdjacentHTML('beforeend',`<option>${d}</option>`));
let sortK='risk_score',sortDir=-1;
function render(){const q=fQ.value.trim();let rows=R.filter(r=>(!fDiv.value||r.division_name===fDiv.value)&&(!fBand.value||r.risk_band===fBand.value)&&(!q||[r.name,r.org_unit_name,r.employee_id].join(' ').includes(q)));
 rows.sort((a,b)=>{const x=a[sortK],y=b[sortK];return (x>y?1:x<y?-1:0)*sortDir});
 tb.innerHTML=rows.map(r=>`<tr data-id="${r.employee_id}"><td><span class="bar"><i style="width:${Math.round(r.risk_score*100)}%"></i></span> ${r.risk_score.toFixed(2)}</td><td><span class="band ${r.risk_band}">${r.risk_band}</span></td><td>${r.employee_id}</td><td>${r.name}</td><td>${r.division_name}</td><td>${r.org_unit_name}</td><td>${r.grade_title}</td><td>${(r.tenure_years||0).toFixed(1)}</td><td class="drivers">${r.top_drivers}</td></tr>`).join('');
 document.getElementById('count').textContent=`${rows.length}명`;}
[fDiv,fBand].forEach(e=>e.onchange=render); fQ.oninput=render;
document.querySelectorAll('#tbl th[data-k]').forEach(th=>th.onclick=()=>{const k=th.dataset.k;sortDir=(sortK===k)?-sortDir:(k==='risk_score'||k==='tenure_years'?-1:1);sortK=k;render()});
tb.onclick=e=>{const tr=e.target.closest('tr');if(tr)showDetail(tr.dataset.id)};
render();
function showDetail(id){const r=R.find(x=>x.employee_id===id);if(!r)return;const z=DATA.z[id]||{};
 const items=Object.keys(DOCS).filter(k=>r[k]!==null&&r[k]!==undefined).map(k=>{const v=r[k],zz=z[k]||0,dir=DOCS[k][2];const risky=dir*zz;const cls=risky>0.8?'warn':risky<-0.8?'good':'';return `<div><div class="k">${DOCS[k][0]}</div><div class="${cls}">${typeof v==='number'?(Number.isInteger(v)?v:v.toFixed(2)):v} <span class="k">z ${zz>=0?'+':''}${zz.toFixed(1)}</span></div></div>`}).join('');
 document.getElementById('detail').innerHTML=`<h2>직원 상세</h2><div style="display:flex;gap:14px;align-items:baseline;flex-wrap:wrap;margin-bottom:10px"><strong style="font-size:16px">${r.name}</strong><span class="sub">${r.employee_id} · ${r.division_name} / ${r.org_unit_name} · ${r.grade_title} · ${r.role_title} · ${r.employment_type} · ${r.employment_status}</span><span class="band ${r.risk_band}">${r.risk_band} ${r.risk_score.toFixed(2)}</span></div><div class="note" style="margin-bottom:10px">주요 신호: ${r.top_drivers}</div><div class="grid">${items}</div>`;
 document.getElementById('detail').scrollIntoView({behavior:'smooth',block:'start'});}
</script>
</body>
</html>
"""


def _clean(v):
    if isinstance(v, (np.floating, float)):
        return None if np.isnan(v) else round(float(v), 3)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, pd.Timestamp):
        return v.date().isoformat()
    return v


def build_dashboard(features: pd.DataFrame, scores: pd.DataFrame, metrics: dict, manifest: dict, overview: dict,
                    out_path: Path, unavailable: list | None = None) -> Path:
    df = features.merge(scores, on="employee_id", how="left")
    if "drivers_plain" in df:
        df["top_drivers"] = df["drivers_plain"]   # HR 담당자용: 평이한 표현
    for c in ("division_name", "org_unit_name", "grade_title", "role_title", "employment_type", "employment_status", "job_family"):
        df[c] = df[c].fillna("미지정") if c in df else "미지정"
    df["tenure_years"] = pd.to_numeric(df.get("tenure_years"), errors="coerce").fillna(0.0)
    df["risk_score"] = pd.to_numeric(df.get("risk_score"), errors="coerce").fillna(0.0)
    num_cols = [c for c in FEATURE_DOCS if c in df]
    Z = ((df[num_cols] - df[num_cols].mean()) / df[num_cols].std(ddof=0).replace(0, np.nan)).fillna(0).clip(-3, 3)
    z_by_emp = {eid: {k: round(float(v), 2) for k, v in row.items()} for eid, row in zip(df.employee_id, Z.to_dict("records"))}
    high = df.risk_band == "높음"
    z_high = {k: round(float(v), 2) for k, v in Z[high].mean().items()} if high.any() else {k: 0.0 for k in num_cols}
    rows = [{k: _clean(v) for k, v in r.items()} for r in df.to_dict("records")]
    mode = metrics.get("mode", "heuristic")
    if mode == "model":
        metric_label, metric_value = "교차검증 AUC", f"{metrics.get('cv_auc', '-')}"
        mode_label = f"예측 모델 · 양성 {metrics.get('positives')}명 학습"
        about = ("퇴사 위험 탭의 지수는 라벨(퇴사 여부)로 학습한 로지스틱 회귀의 예측 확률이다. 성별·국적·혼인 등 민감 속성은 쓰지 않았다. "
                 f"알고리즘: {metrics.get('algorithm')}.")
    else:
        metric_label, metric_value = "분석 모드", "진단(규칙 기반 신호 지수)"
        mode_label = "진단 모드 · 규칙 기반 신호 지수 · 예측 아님"
        about = ("퇴사 위험 탭의 지수는 보상 밴드 위치·승진 보류·평가·연장근로 추세·설문 몰입도 등에 공개 가중치를 곱한 회사 내 상대 지수(0~1)다. "
                 "예측 확률이 아니며 개인 평가나 인사 조치의 단독 근거로 쓰면 안 된다. 성별·국적·혼인 등 민감 속성은 쓰지 않는다.")
    if unavailable:
        about += " 입력 파일에 없어 계산하지 못한 신호: " + ", ".join(FEATURE_DOCS[c][0] for c in unavailable if c in FEATURE_DOCS) + "."
    data = dict(rows=rows, z=z_by_emp, z_high=z_high, metric_label=metric_label, metric_value=metric_value)
    html = (TEMPLATE.replace("__TITLE__", f"{manifest['company']['name']} HR 대시보드")
            .replace("__CHART_JS__", CHART_JS).replace("__COMPANY__", str(manifest["company"]["name"]))
            .replace("__AS_OF__", str(manifest["as_of"])).replace("__GENERATED__", datetime.now().strftime("%Y-%m-%d %H:%M"))
            .replace("__MODE__", "model" if mode == "model" else "heur").replace("__MODE_LABEL__", mode_label)
            .replace("__ABOUT__", about)
            .replace("__DOCS__", json.dumps({k: list(v) for k, v in FEATURE_DOCS.items()}, ensure_ascii=False))
            .replace("__OVERVIEW__", json.dumps(overview, ensure_ascii=False, default=_clean))
            .replace("__DATA__", json.dumps(data, ensure_ascii=False)))
    out_path.write_text(html, encoding="utf-8")
    return out_path
