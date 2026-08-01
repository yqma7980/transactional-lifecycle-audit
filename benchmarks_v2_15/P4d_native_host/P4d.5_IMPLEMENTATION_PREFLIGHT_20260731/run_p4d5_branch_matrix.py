
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parent
for path in (ROOT / "src",):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from p4d5_protocol import (
    P4D2_RESULTS_ROOT,
    P4D_ROOT,
    RUN_IDS,
    load_case_contracts,
    matrix_authorized,
    require_descendant,
    verify_inherited_prerequisites,
    verify_protected_inputs,
)
from p4d5_scheduler import PASS, RETRY_DEPENDENTS, WAVE_ONE, aggregate_boundary, classify_case_pair

IMAGE = "dolfinx/dolfinx@sha256:1bb0d528457c78db65ba5445421abe37d0cdfa542cc182bf36d3b4aca02f1fab"
CONTAINER_ROOT = "/p4droot"
CONTAINER_WORKDIR = f"{CONTAINER_ROOT}/{ROOT.name}"
CONTAINER_DEPENDENCY_ROOT = f"{CONTAINER_ROOT}/P4d.2_FULL_IMPLEMENTATION_20260731/results/P4d2_formal_20260731"


def parse_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--execution-tag", required=True)
    parser.add_argument("--execute-authorized", action="store_true")
    return parser.parse_args(argv)


def write_json_new(path: Path, value: Any) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2)
        handle.write("\n")


def write_json_replace(path: Path, value: Any) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2)
        handle.write("\n")


def run_one(case_id: str, run_id: str, execution_tag: str, log_root: Path) -> dict[str, Any]:
    mount = f"type=bind,source={P4D_ROOT},target={CONTAINER_ROOT}"
    container_results = f"{CONTAINER_WORKDIR}/results/{execution_tag}"
    command = [
        "docker", "run", "--rm", "--network", "none", "--platform", "linux/amd64",
        "--env", "PYTHONDONTWRITEBYTECODE=1", "--env", "OMP_NUM_THREADS=1",
        "--env", "OPENBLAS_NUM_THREADS=1", "--env", "MKL_NUM_THREADS=1",
        "--env", "P4D5_EXECUTION_AUTHORIZED=YES", "--mount", mount,
        "--workdir", CONTAINER_WORKDIR, IMAGE, "python3", "run_p4d5.py",
        "--case-id", case_id, "--run-id", run_id, "--results-root", container_results,
        "--dependency-root", CONTAINER_DEPENDENCY_ROOT, "--execute-authorized",
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    log_path = log_root / f"{case_id}_{run_id}.log"
    log_path.write_text(completed.stdout + completed.stderr, encoding="utf-8", newline="\n")
    result_path = ROOT / "results" / execution_tag / case_id / run_id / "case_result.json"
    if not result_path.is_file():
        return {"case_id": case_id, "run_id": run_id, "exit_code": completed.returncode, "infrastructure_failure": True}
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result["exit_code"] = completed.returncode
    return result


def execute_pair(case_id: str, execution_tag: str, log_root: Path) -> tuple[list[dict[str, Any]], str]:
    observations = [run_one(case_id, run_id, execution_tag, log_root) for run_id in RUN_IDS]
    if any(item.get("infrastructure_failure") for item in observations):
        return observations, "FAIL"
    return observations, classify_case_pair(case_id, observations).classification


def main(argv=None) -> int:
    args = parse_args(argv)
    if not matrix_authorized(args.execute_authorized):
        raise SystemExit("P4d.5 matrix execution requires both authorization locks")
    if not args.execution_tag.startswith("P4d5_branch_resumption_"):
        raise SystemExit("execution tag must begin with P4d5_branch_resumption_")
    verify_protected_inputs()
    verify_inherited_prerequisites()
    load_case_contracts()

    result_root = require_descendant(ROOT / "results" / args.execution_tag, ROOT / "results")
    log_root = require_descendant(ROOT / "formal_execution_logs" / args.execution_tag, ROOT / "formal_execution_logs")
    if result_root.exists() or log_root.exists():
        raise SystemExit("refusing to reuse P4d.5 result or log root")
    subprocess.run(["docker", "image", "inspect", IMAGE], check=True, capture_output=True, text=True)

    log_root.mkdir(parents=True)
    progress_path = log_root / "branch_progress.json"
    pair_statuses: dict[str, str] = {}
    records: dict[str, list[dict[str, Any]]] = {}
    write_json_new(progress_path, {"status": "RUNNING", "pair_statuses": pair_statuses, "records": records})

    for case_id in WAVE_ONE:
        observations, classification = execute_pair(case_id, args.execution_tag, log_root)
        records[case_id] = observations
        pair_statuses[case_id] = classification
        write_json_replace(progress_path, {"status": "RUNNING", "pair_statuses": pair_statuses, "records": records})

    if pair_statuses.get("P4D-SAFE-RT-01") == PASS:
        for case_id in RETRY_DEPENDENTS:
            observations, classification = execute_pair(case_id, args.execution_tag, log_root)
            records[case_id] = observations
            pair_statuses[case_id] = classification
            write_json_replace(progress_path, {"status": "RUNNING", "pair_statuses": pair_statuses, "records": records})
    else:
        for case_id in RETRY_DEPENDENTS:
            pair_statuses[case_id] = "SKIPPED_DEPENDENCY"

    final = {
        "schema_version": "CMAME-P4D5-RAW-BRANCH-PROGRESS-1.0",
        "status": "RAW_EXECUTION_COMPLETE_PENDING_DUPLICATE_QA",
        "pair_statuses": pair_statuses,
        "aggregate_boundary": aggregate_boundary(pair_statuses),
        "records": records,
        "native_linesearch_status": "NOT_SUPPORTED_BY_DIAGNOSTIC_ENVELOPE",
        "full_p4d_matrix_pass": False,
    }
    write_json_replace(progress_path, final)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
