"""1단계 질문 정의: 대상(어떤 퇴사)·기간(기준일 이후 며칠)·모집단(누구)·기준일을 명시한다.

미상의 프롬프트가 와도 기본 정의로 시작할 수 있게 기본값을 두고, 결과에 그대로 기록한다(재사용 스펙의 일부).
"""
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import pandas as pd

DEFAULT_TARGET = "자발적 퇴사"
DEFAULT_HORIZON_DAYS = 90
FILTERABLE = ("division_name", "org_unit_name", "job_family", "grade_title", "employment_type", "employment_status", "role_title")
FILTER_ALIASES = {"본부": "division_name", "팀": "org_unit_name", "부서": "org_unit_name", "직군": "job_family", "직급": "grade_title",
                  "고용형태": "employment_type", "재직상태": "employment_status", "직책": "role_title"}


@dataclass
class QuestionSpec:
    target: str = DEFAULT_TARGET                 # 예: 자발적 퇴사 / 전체 퇴사 / 1년 내 조기 퇴사
    horizon_days: int = DEFAULT_HORIZON_DAYS     # 기준일 이후 N일
    population: str = "기준일 현재 재직자 전원(휴직자 포함)"
    filters: dict = field(default_factory=dict)  # {"job_family": "개발직"} 등 모집단 제한
    as_of: str | None = None                     # 입력 데이터의 기준일(로드 후 채움)
    raw_prompt: str = ""                         # 사용자가 실제로 한 말(있으면)

    def sentence(self) -> str:
        pop = self.population + (" 중 " + ", ".join(f"{k}={v}" for k, v in self.filters.items()) if self.filters else "")
        return f"기준일 {self.as_of or '(입력 파일 기준)'} 이후 {self.horizon_days}일 이내 {self.target} 위험을 {pop}에 대해 평가한다."

    def to_dict(self) -> dict:
        d = asdict(self)
        d["sentence"] = self.sentence()
        return d

    @classmethod
    def from_args(cls, target=None, horizon_days=None, population=None, filters=None, spec_path: Path | None = None, raw_prompt="") -> "QuestionSpec":
        base = {}
        if spec_path:
            base = json.loads(Path(spec_path).read_text(encoding="utf-8")).get("question", {})
            base.pop("sentence", None)
        q = cls(**{k: v for k, v in base.items() if k in cls.__dataclass_fields__})
        if target:
            q.target = target
        if horizon_days:
            q.horizon_days = int(horizon_days)
        if population:
            q.population = population
        if filters:
            q.filters.update(filters)
        if raw_prompt:
            q.raw_prompt = raw_prompt
        return q


def parse_filters(items: list[str] | None) -> dict:
    """--filter 본부=개발본부 --filter job_family=개발직 → {"division_name": "개발본부", "job_family": "개발직"}"""
    out = {}
    for it in items or []:
        if "=" not in it:
            raise ValueError(f"--filter 형식은 키=값 입니다: {it}")
        k, v = it.split("=", 1)
        k = FILTER_ALIASES.get(k.strip(), k.strip())
        if k not in FILTERABLE:
            raise ValueError(f"필터 가능한 키: {', '.join(FILTERABLE)} (별칭: {', '.join(FILTER_ALIASES)})")
        out[k] = v.strip()
    return out


def apply_population(features: pd.DataFrame, q: QuestionSpec) -> tuple[pd.DataFrame, dict]:
    """모집단 제한을 적용하고 전후 인원을 돌려준다. 민감 속성으로는 거를 수 없다(FILTERABLE에 없음)."""
    before = len(features)
    f = features
    for k, v in q.filters.items():
        if k in f:
            f = f[f[k].astype(str) == str(v)]
    f = f.copy()
    f.attrs = dict(features.attrs)
    return f, dict(before=before, after=int(len(f)), filters=dict(q.filters))
