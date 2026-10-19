"""입력 로드: (1) HR 워크북 xlsx (시트 접두어 hr_/v_/meta_), (2) 직원 명부 한 장 xlsx/csv, (3) output/<preset>/ 폴더.

모든 경로는 Dataset(tables, manifest)로 정규화된다. 없는 테이블은 빈 DataFrame이며 피처 단계가 알아서 건너뛴다.
"""
import json
import re
import warnings
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pandas as pd

from . import config as C

DATE_HINTS = ("_date", "_at", "_from", "_to", "_expiry", "as_of", "week_start", "week_end", "period_start", "period_end")
KEEP_STR = ("_id", "_ref", "_code", "_uuid", "_period", "_month", "employee_id", "tag_in", "tag_out")
SHEET_PREFIXES = ("hr_", "v_", "meta_")

# 직원 명부 한 장 모드: 표준 컬럼 ← 허용 별칭(소문자·공백 제거 후 비교)
ROSTER_ALIASES = {
    "employee_id": ("employee_id", "사번", "사원번호", "직원id", "직원번호", "emp_id", "id"),
    "name": ("name", "이름", "성명", "직원명"),
    "division_name": ("division_name", "본부", "사업부", "division"),
    "org_unit_name": ("org_unit_name", "팀", "부서", "조직", "department", "team"),
    "job_family": ("job_family", "직군", "직무군"),
    "grade_title": ("grade_title", "직급", "직위", "grade"),
    "grade_level": ("grade_level", "직급레벨", "레벨", "level"),
    "role_title": ("role_title", "직책", "role"),
    "employment_type": ("employment_type", "고용형태", "계약유형", "contract_type"),
    "employment_status": ("employment_status", "재직상태", "상태", "status"),
    "hire_date": ("hire_date", "입사일", "입사일자", "입사년월일"),
    "birth_date": ("birth_date", "생년월일", "생일"),
    "age": ("age", "나이", "연령", "만나이"),
    "base_annual_krw10k": ("base_annual_krw10k", "연봉", "기준연봉", "연봉(만원)", "annual_salary"),
    "last_rating": ("last_rating", "최근평가", "평가등급", "최종등급", "고과", "rating"),
    "prev_rating": ("prev_rating", "직전평가", "전년평가"),
    "last_raise_date": ("last_raise_date", "마지막인상일", "최근인상일", "연봉조정일"),
    "last_raise_pct": ("last_raise_pct", "인상률", "마지막인상률", "인상률(%)"),
    "last_promotion_date": ("last_promotion_date", "최근승진일", "마지막승진일", "승진일"),
    "promotion_holds": ("promotion_holds", "승진보류", "승진보류횟수", "승진누락"),
    "overtime_hours_monthly": ("overtime_hours_monthly", "월평균연장", "월연장근로", "연장근로(h)", "초과근무시간"),
    "late_count": ("late_count", "지각", "지각횟수"),
    "absent_days": ("absent_days", "결근", "결근일수"),
    "sick_days": ("sick_days", "병가", "병가일수"),
    "annual_leave_granted": ("annual_leave_granted", "연차발생", "연차부여", "연차총일수"),
    "annual_leave_used": ("annual_leave_used", "연차사용", "연차사용일수"),
    "training_hours": ("training_hours", "교육시간", "교육이수시간"),
    "survey_engagement": ("survey_engagement", "몰입도", "설문몰입", "engagement"),
    "survey_enps": ("survey_enps", "enps", "추천의향"),
    "contract_end_date": ("contract_end_date", "계약만료일", "계약종료일"),
    "left": ("left", "퇴사여부", "퇴사", "attrition"),
}


@dataclass
class Dataset:
    source: str
    manifest: dict
    tables: dict[str, pd.DataFrame] = field(default_factory=dict)
    kind: str = "workbook"          # workbook | roster | folder
    missing: list[str] = field(default_factory=list)

    @property
    def as_of(self) -> date:
        return date.fromisoformat(self.manifest["as_of"])

    def has(self, name: str) -> bool:
        return name in self.tables and len(self.tables[name]) > 0

    def __getitem__(self, name: str) -> pd.DataFrame:
        if name not in self.tables:
            self.missing.append(name)
            self.tables[name] = pd.DataFrame()
        return self.tables[name]


# ---------- 공통 형변환 ----------

def coerce(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    for col in df.columns:
        s = df[col]
        if s.dtype == object:
            s = s.where(s.notna(), None).map(lambda v: None if (isinstance(v, str) and v.strip() == "") else v)
        if any(col.endswith(k) or col == k for k in KEEP_STR):
            df[col] = s.map(lambda v: None if v is None or (isinstance(v, float) and pd.isna(v)) else str(v).strip())
            continue
        if any(col.endswith(h) or col == h for h in DATE_HINTS):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)   # 혼합 형식 날짜의 형식 추론 경고
                df[col] = pd.to_datetime(s, errors="coerce")
            continue
        if s.dtype == object:
            vals = s.dropna()
            if not len(vals):
                df[col] = s
                continue
            as_str = vals.astype(str).str.strip()
            if as_str.str.fullmatch(r"-?\d+(\.\d+)?").all():
                df[col] = pd.to_numeric(s, errors="coerce")
            elif set(as_str.str.lower().unique()) <= {"true", "false"}:
                df[col] = as_str.str.lower().map({"true": True, "false": False}).reindex(s.index)
            else:
                df[col] = s
    return df


# ---------- 폴더(output/<preset>) ----------

def load_folder(root: Path) -> Dataset:
    root = Path(root)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    tables = {}
    for layer in ("hr", "views", "meta"):
        for p in sorted((root / layer).glob("*.csv")):
            try:
                tables[p.stem] = coerce(pd.read_csv(p, dtype=str, keep_default_na=False, encoding="utf-8-sig").replace({"": None}))
            except pd.errors.EmptyDataError:
                tables[p.stem] = pd.DataFrame()
    return Dataset(source=str(root), manifest=manifest, tables=tables, kind="folder")


# ---------- 워크북 ----------

def _norm(s: str) -> str:
    return re.sub(r"[\s_\-()（）/·.]", "", str(s)).lower()


# 피처 계산에 쓰는 테이블만 읽는다(일별 근태·급여 항목 같은 큰 시트는 건너뛰어 로드 시간을 줄인다)
NEEDED_TABLES = {"employees", "employees_current", "compensation_history", "promotion_reviews", "personnel_actions",
                 "performance_reviews", "attendance_monthly", "leave_requests", "training_enrollments", "oncall_shifts",
                 "surveys", "survey_questions", "survey_responses", "survey_answers", "contracts"}
OVERVIEW_SHEETS = ("개요", "overview", "manifest")


def load_workbook(path: Path) -> Dataset:
    path = Path(path)
    xf = pd.ExcelFile(path, engine="openpyxl")
    names = xf.sheet_names
    has_prefix = any(n.startswith(SHEET_PREFIXES) for n in names)

    def want(n: str) -> bool:
        if n in OVERVIEW_SHEETS or n in C.LABEL_SHEETS or _norm(n) in C.LABEL_SHEETS:
            return True
        if n.startswith(SHEET_PREFIXES):
            return re.sub(r"^(hr_|v_|meta_)", "", n) in NEEDED_TABLES
        return not has_prefix and n == names[0]   # 명부 한 장 모드: 첫 시트

    sheets = {n: pd.read_excel(xf, sheet_name=n, dtype=object) for n in names if want(n)}
    prefixed = {n: df for n, df in sheets.items() if n.startswith(SHEET_PREFIXES)}
    if prefixed:
        tables = {re.sub(r"^(hr_|v_|meta_)", "", n): coerce(df) for n, df in prefixed.items()}
        labels = next((sheets[n] for n in sheets if n in C.LABEL_SHEETS or _norm(n) in C.LABEL_SHEETS), None)
        if labels is not None:
            tables["labels"] = coerce(labels)
        manifest = _manifest_from_workbook(sheets, tables, path)
        return Dataset(source=str(path), manifest=manifest, tables=tables, kind="workbook")
    # 직원 명부 한 장
    first_name = next(iter(sheets))
    roster = sheets[first_name]
    labels = next((sheets[n] for n in sheets if n in C.LABEL_SHEETS or _norm(n) in C.LABEL_SHEETS), None)
    return load_roster_frame(roster, str(path), labels)


def _manifest_from_workbook(sheets: dict, tables: dict, path: Path) -> dict:
    info = {}
    overview = next((df for n, df in sheets.items() if n in OVERVIEW_SHEETS), None)
    if overview is not None and overview.shape[1] >= 2:
        for k, v in zip(overview.iloc[:, 0], overview.iloc[:, 1]):
            info[str(k).strip()] = None if pd.isna(v) else str(v).strip()
    company_key = next((k for k in info if k.startswith("회사") or k.lower().startswith("company")), None)
    company = (info[company_key].split(" · ")[0].strip() if company_key and info[company_key] else None) or path.stem
    as_of = info.get("기준일") or info.get("as_of")
    snap = tables.get("employees_current")
    if not as_of and snap is not None and "as_of" in snap and snap["as_of"].notna().any():
        as_of = pd.to_datetime(snap["as_of"]).max().date().isoformat()
    if not as_of:
        as_of = date.today().isoformat()
    as_of = pd.to_datetime(as_of).date().isoformat()
    n = len(snap) if snap is not None else len(tables.get("employees", []))
    return dict(company=dict(name=company), as_of=as_of, preset=info.get("프리셋") or path.stem, employee_count=int(n),
                source_file=path.name)


# ---------- 직원 명부 한 장 ----------

def _map_roster_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    lookup = {}
    for std, aliases in ROSTER_ALIASES.items():
        for a in aliases:
            lookup.setdefault(_norm(a), std)
    mapping, out = {}, {}
    for col in df.columns:
        std = lookup.get(_norm(col))
        if std and std not in out:
            mapping[str(col)] = std
            out[std] = df[col]
    return pd.DataFrame(out), mapping


def load_roster_frame(df: pd.DataFrame, source: str, labels: pd.DataFrame | None = None) -> Dataset:
    mapped, mapping = _map_roster_columns(df)
    if "employee_id" not in mapped:
        mapped["employee_id"] = [f"R{i + 1:04d}" for i in range(len(mapped))]
    mapped = coerce(mapped)
    mapped["employee_id"] = mapped["employee_id"].astype(str)
    if "name" not in mapped:
        mapped["name"] = mapped["employee_id"]
    as_of = date.today()
    manifest = dict(company=dict(name=Path(source).stem), as_of=as_of.isoformat(), preset="roster",
                    employee_count=int(len(mapped)), source_file=Path(source).name, column_mapping=mapping)
    tables = {"roster": mapped}
    if labels is not None:
        tables["labels"] = coerce(labels)
    elif "left" in mapped:
        tables["labels"] = mapped[["employee_id", "left"]].copy()
    return Dataset(source=source, manifest=manifest, tables=tables, kind="roster")


# ---------- 진입점 ----------

def load_any(path_or_preset: str, dataset_root: Path | None = None) -> Dataset:
    p = Path(path_or_preset).expanduser()
    if p.is_file():
        if p.suffix.lower() in (".xlsx", ".xlsm", ".xls"):
            return load_workbook(p)
        if p.suffix.lower() == ".csv":
            return load_roster_frame(pd.read_csv(p, dtype=object, encoding="utf-8-sig"), str(p))
        raise ValueError(f"지원하지 않는 파일 형식: {p.suffix}")
    if (p / "manifest.json").exists():
        return load_folder(p)
    if dataset_root and (dataset_root / path_or_preset / "manifest.json").exists():
        return load_folder(dataset_root / path_or_preset)
    raise FileNotFoundError(f"입력을 찾을 수 없습니다: {path_or_preset}")
