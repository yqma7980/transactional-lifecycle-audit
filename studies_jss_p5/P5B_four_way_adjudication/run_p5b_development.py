from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from jss_p5b.cases import load_case_matrix
from jss_p5b.development_guard import authorize_development, select_development_case
from jss_p5b.formal_executor import execute_development_case


S01_IMAGE = (
    "dolfinx/dolfinx@sha256:"
    "1bb0d528457c78db65ba5445421abe37d0cdfa542cc182bf36d3b4aca02f1fab"
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one frozen P5B DEVELOPMENT case")
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--execute-authorized", action="store_true")
    parser.add_argument("--inside-container", action="store_true", help=argparse.SUPPRESS)
    return parser.parse_args()


def _docker_command(case_id: str, run_id: str) -> list[str]:
    mount = f"{ROOT}:/workspace"
    python_path = ":".join(
        (
            "/workspace/src",
            "/workspace",
            "/workspace/00_runtime_dependencies",
            "/workspace/00_runtime_dependencies/P22_frozen_inputs/P5_subject_src",
            "/workspace/00_runtime_dependencies/P22_frozen_inputs/P4d_subject_src",
            "/workspace/benchmarks",
            "/usr/local/dolfinx-real/lib/python3.12/dist-packages",
        )
    )
    return [
        "docker",
        "run",
        "--rm",
        "--pull=never",
        "--platform=linux/amd64",
        "--network=none",
        "--cpus=1",
        "-e",
        "JSS_P5B_DEVELOPMENT_AUTHORIZED=YES",
        "-e",
        "PYTHONDONTWRITEBYTECODE=1",
        "-e",
        "OMP_NUM_THREADS=1",
        "-e",
        "OPENBLAS_NUM_THREADS=1",
        "-e",
        "MKL_NUM_THREADS=1",
        "-e",
        f"PYTHONPATH={python_path}",
        "-v",
        mount,
        "-w",
        "/workspace",
        S01_IMAGE,
        "python3",
        "run_p5b_development.py",
        "--case-id",
        case_id,
        "--run-id",
        run_id,
        "--execute-authorized",
        "--inside-container",
    ]


def main() -> int:
    args = _arguments()
    case_result_path = authorize_development(
        ROOT,
        case_id=args.case_id,
        run_id=args.run_id,
        cli_authorized=args.execute_authorized,
    )
    case = select_development_case(load_case_matrix(ROOT), args.case_id)
    if case.subject_id == "JSS-S01" and not args.inside_container:
        completed = subprocess.run(
            _docker_command(args.case_id, args.run_id),
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.stdout:
            sys.stdout.write(completed.stdout)
        if completed.stderr:
            sys.stderr.write(completed.stderr)
        return completed.returncode
    result = execute_development_case(
        ROOT,
        case_id=args.case_id,
        run_id=args.run_id,
        case_result_path=case_result_path,
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
