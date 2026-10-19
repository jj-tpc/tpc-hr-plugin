"""퇴사 라벨: 워크북의 '퇴사라벨'/'labels' 시트, 명부의 '퇴사여부' 컬럼, 또는 별도 CSV. 형식: employee_id,left[,left_date]."""
from pathlib import Path

import pandas as pd

from .data import Dataset

_TRUTHY = {"1": 1, "0": 0, "true": 1, "false": 0, "y": 1, "n": 0, "yes": 1, "no": 0, "예": 1, "아니오": 0, "퇴사": 1, "재직": 0}


def _to_series(df: pd.DataFrame, where: str) -> pd.Series:
    cols = {str(c).strip().lower(): c for c in df.columns}
    id_col = cols.get("employee_id") or cols.get("사번")
    left_col = cols.get("left") or cols.get("퇴사여부") or cols.get("퇴사")
    if id_col is None or left_col is None:
        raise ValueError(f"{where}: employee_id(사번)와 left(퇴사여부) 컬럼이 필요합니다.")
    raw = df[left_col].map(lambda v: None if v is None or (isinstance(v, float) and pd.isna(v)) else str(v).strip().lower())
    left = raw.map(lambda v: _TRUTHY.get(v) if v is not None else None)
    if left.isna().any():
        bad = raw[left.isna()].dropna().unique()[:5]
        raise ValueError(f"{where}: left 값은 0/1, true/false, 예/아니오여야 합니다. 잘못된 값: {list(bad)}")
    s = pd.Series(left.astype(int).to_numpy(), index=df[id_col].astype(str).str.strip(), name="left")
    if s.index.duplicated().any():
        raise ValueError(f"{where}: employee_id가 중복된 라벨 행이 있습니다.")
    return s


def load_labels(ds: Dataset, path: Path | None = None) -> pd.Series | None:
    """우선순위: --labels CSV > 워크북 라벨 시트/명부 컬럼. 없으면 None."""
    if path is not None:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"라벨 파일 없음: {path}")
        return _to_series(pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig"), str(path))
    if ds.has("labels"):
        return _to_series(ds["labels"], "라벨 시트")
    return None


def describe_labels(s: pd.Series | None, n_employees: int) -> dict:
    if s is None:
        return dict(present=False, rows=0, positives=0, coverage_pct=0.0)
    return dict(present=True, rows=int(len(s)), positives=int(s.sum()), coverage_pct=round(100 * len(s) / max(n_employees, 1), 1))
