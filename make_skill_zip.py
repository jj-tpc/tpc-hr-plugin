"""claude.ai 업로드용 스킬 zip 두 개 생성. 각 zip에 공용 엔진(engine/hrattrition)을 scripts/hrattrition으로 동봉한다.

    python make_skill_zip.py   → dist/predict_attrition.zip, dist/make_dashboard.zip
"""
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENGINE = ROOT / "engine" / "hrattrition"
SKILLS = ("predict_attrition", "make_dashboard")
SKIP_DIRS = {"__pycache__", ".pytest_cache"}


def _ok(p: Path) -> bool:
    return p.is_file() and not any(part in SKIP_DIRS or part.endswith(".egg-info") for part in p.parts) and p.suffix != ".pyc"


def main():
    (ROOT / "dist").mkdir(exist_ok=True)
    for name in SKILLS:
        src = ROOT / "skill" / name
        out = ROOT / "dist" / f"{name}.zip"
        n = 0
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            for p in sorted(src.rglob("*")):
                if _ok(p):
                    z.write(p, Path(name) / p.relative_to(src))
                    n += 1
            for p in sorted(ENGINE.rglob("*")):
                if _ok(p):
                    z.write(p, Path(name) / "scripts" / "hrattrition" / p.relative_to(ENGINE))
                    n += 1
        print(f"{out} ← {n} files, {out.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
