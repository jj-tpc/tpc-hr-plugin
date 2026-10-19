#!/usr/bin/env python
"""예측 결과 엑셀(+원본 HR xlsx) → dashboard.html.

    python make_dashboard.py --result <퇴사위험_결과.xlsx> [--data <HR.xlsx>] --out <출력 폴더>
    python make_dashboard.py --data <HR.xlsx> --out <출력 폴더>        # 결과가 없으면 예측부터 수행

동봉된 hrattrition 패키지(zip 안 scripts/hrattrition, 저장소에서는 engine/hrattrition)를 쓴다.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
for cand in (HERE, HERE.parents[2] / "engine"):
    if (cand / "hrattrition").is_dir():
        sys.path.insert(0, str(cand))
        break

from hrattrition.cli import main  # noqa: E402

if __name__ == "__main__":
    main(["dashboard", *sys.argv[1:]])
