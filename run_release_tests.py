from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parent
STUDIES = (
    Path("studies_jss_p5") / "P5B_four_way_adjudication",
    Path("studies_jss_p5") / "P5C_localization_v2",
    Path("studies_jss_p5") / "P5D_performance",
    Path("studies_r3_sqlite"),
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
    failed_studies: list[str] = []
    try:
        with tempfile.TemporaryDirectory(prefix="tla_v6_tests_", dir=temporary_parent) as temporary:
            temporary_root = Path(temporary)
            for relative in STUDIES:
                source = ROOT / relative
                target = temporary_root / relative.name
                shutil.copytree(source, target, ignore=ignored)
                environment["PYTHONPATH"] = os.pathsep.join((str(target / "src"), str(target)))
                print(f"=== {relative.as_posix()} ===", flush=True)
                result = subprocess.run(
                    [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"],
                    cwd=target,
                    env=environment,
                    check=False,
                )
                if result.returncode:
                    failed_studies.append(relative.as_posix())
    finally:
        temporary_parent.rmdir()
    print("=== release suite summary ===")
    print(f"studies={len(STUDIES)}")
    print(f"failed_studies={len(failed_studies)}")
    for study in failed_studies:
        print(f"FAILED {study}")
    return 1 if failed_studies else 0


if __name__ == "__main__":
    raise SystemExit(main())
