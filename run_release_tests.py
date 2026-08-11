from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parent
STUDIES = (
    "P5B_four_way_adjudication",
    "P5C_localization_v2",
    "P5D_performance",
)


def ignored(_: str, names: list[str]) -> set[str]:
    excluded = {"results", "__pycache__"}
    return {name for name in names if name in excluded or name.endswith(".pyc")}


def main() -> int:
    environment = os.environ.copy()
    environment.update(
        {
            "PYTHONDONTWRITEBYTECODE": "1",
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
        }
    )
    temporary_parent = ROOT / ".release_test_tmp"
    temporary_parent.mkdir(exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix="tla_v3_tests_", dir=temporary_parent) as temporary:
            temporary_root = Path(temporary)
            for study in STUDIES:
                source = ROOT / "studies_jss_p5" / study
                target = temporary_root / study
                shutil.copytree(source, target, ignore=ignored)
                environment["PYTHONPATH"] = os.pathsep.join((str(target / "src"), str(target)))
                print(f"=== {study} ===", flush=True)
                result = subprocess.run(
                    [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"],
                    cwd=target,
                    env=environment,
                    check=False,
                )
                if result.returncode:
                    return result.returncode
    finally:
        temporary_parent.rmdir()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
