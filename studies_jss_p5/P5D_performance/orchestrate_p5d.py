from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any


IMAGE = "dolfinx/dolfinx@sha256:1bb0d528457c78db65ba5445421abe37d0cdfa542cc182bf36d3b4aca02f1fab"
QUALIFICATION_STORAGE_PHASE = "qualification_v3"
S03_BACKEND = "HOST_PYTHON_SCIPY_1_17_1"


def write_json_new(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load_matrix(root: Path) -> list[dict[str, str]]:
    path = root / "frozen_inputs" / "P5D_performance_matrix.csv"
    with path.open("r", encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != 18 or len({row["cell_id"] for row in rows}) != 18:
        raise RuntimeError("P5D matrix is not the frozen 18-cell design")
    return rows


def run_one(root: Path, row: dict[str, str], phase: str, run_id: str) -> dict[str, Any]:
    storage_phase = QUALIFICATION_STORAGE_PHASE if phase == "qualification" else phase
    run_root = root / "results" / storage_phase / row["cell_id"] / run_id
    if run_root.exists():
        raise FileExistsError(run_root)
    run_root.mkdir(parents=True)
    relative_output = run_root.relative_to(root).as_posix() + "/case_result.json"
    child_environment = None
    if row["subject_id"] == "JSS-S03":
        backend = S03_BACKEND
        command = [
            sys.executable, str(root / "run_p5d.py"),
            "--cell-id", row["cell_id"],
            "--run-id", run_id,
            "--phase", phase,
            "--output", str(root / relative_output),
            "--execute-authorized",
        ]
        child_environment = os.environ.copy()
        child_environment.update({
            "PYTHONDONTWRITEBYTECODE": "1",
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "P5D_EXECUTION_AUTHORIZED": "YES",
        })
    else:
        backend = "DOLFINX_CONTAINER"
        command = [
            "docker", "run", "--rm",
            "--network", "none",
            "--platform", "linux/amd64",
            "--cpuset-cpus", "0",
            "-e", "PYTHONDONTWRITEBYTECODE=1",
            "-e", "OMP_NUM_THREADS=1",
            "-e", "OPENBLAS_NUM_THREADS=1",
            "-e", "MKL_NUM_THREADS=1",
            "-e", "P5D_EXECUTION_AUTHORIZED=YES",
            "-v", f"{root}:/workspace",
            "-w", "/workspace",
            IMAGE,
            "python3", "run_p5d.py",
            "--cell-id", row["cell_id"],
            "--run-id", run_id,
            "--phase", phase,
            "--output", "/workspace/" + relative_output,
            "--execute-authorized",
        ]
    started = time.perf_counter()
    process = subprocess.run(command, capture_output=True, timeout=900, env=child_environment)
    external_wall = time.perf_counter() - started
    stdout_path = run_root / "stdout.log"
    stderr_path = run_root / "stderr.log"
    stdout_path.write_bytes(process.stdout)
    stderr_path.write_bytes(process.stderr)
    result_path = run_root / "case_result.json"
    envelope = {
        "cell_id": row["cell_id"],
        "phase": phase,
        "run_id": run_id,
        "exit_code": process.returncode,
        "external_wall_time_seconds": external_wall,
        "stdout_sha256": sha256_bytes(process.stdout),
        "stderr_sha256": sha256_bytes(process.stderr),
        "case_result_exists": result_path.exists(),
        "image": IMAGE,
        "execution_backend": backend,
        "cpuset_cpus": "0",
        "network": "none",
        "threads": 1,
    }
    write_json_new(run_root / "process_envelope.json", envelope)
    if process.returncode != 0 or not result_path.exists():
        raise RuntimeError(
            f"P5D stopped at {row['cell_id']} {phase} {run_id}; exit={process.returncode}; "
            f"stderr={process.stderr.decode('utf-8', errors='replace')[-1000:]}"
        )
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if result.get("pass_flag") is not True:
        raise RuntimeError(f"P5D case contract failed at {row['cell_id']} {phase} {run_id}")
    return envelope


def host_environment(root: Path) -> None:
    try:
        power = subprocess.run(["powercfg", "/GETACTIVESCHEME"], capture_output=True, timeout=30)
        power_text = (power.stdout + power.stderr).decode(errors="replace").strip()
    except Exception as exc:
        power_text = f"UNAVAILABLE: {exc}"
    try:
        inspect = subprocess.run(
            ["docker", "image", "inspect", IMAGE, "--format", "{{json .RepoDigests}}"],
            capture_output=True,
            timeout=60,
        )
        image_identity = inspect.stdout.decode(errors="replace").strip()
        image_exit = inspect.returncode
    except Exception as exc:
        image_identity = f"UNAVAILABLE: {exc}"
        image_exit = -1
    if image_exit != 0 or "sha256:1bb0d528" not in image_identity:
        raise RuntimeError("frozen P5D container image is unavailable")
    scipy_probe = subprocess.run(
        [sys.executable, "-c", "import numpy, scipy; print(numpy.__version__); print(scipy.__version__)"],
        capture_output=True,
        timeout=30,
    )
    scipy_versions = scipy_probe.stdout.decode(errors="replace").splitlines()
    if scipy_probe.returncode != 0 or scipy_versions[-1:] != ["1.17.1"]:
        raise RuntimeError("frozen S03 host environment is unavailable")
    write_json_new(root / "runtime" / "host_environment_v2.json", {
        "host_platform": sys.platform,
        "host_python": sys.version,
        "active_power_scheme": power_text,
        "container_image": IMAGE,
        "container_image_identity": image_identity,
        "s03_backend": S03_BACKEND,
        "s03_host_python": sys.version,
        "s03_numpy": scipy_versions[0],
        "s03_scipy": scipy_versions[1],
        "formal_affinity": "container cpuset CPU 0",
        "formal_processes_per_run": 1,
        "formal_threads_per_process": 1,
    })


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("qualification", "formal"), required=True)
    parser.add_argument("--execute-authorized", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.execute_authorized or os.environ.get("P5D_MATRIX_EXECUTION_AUTHORIZED") != "YES":
        raise SystemExit("P5D matrix dual authorization lock rejected execution")
    root = Path(__file__).resolve().parent
    matrix = load_matrix(root)
    if not (root / "runtime" / "host_environment_v2.json").exists():
        host_environment(root)
    if args.phase == "qualification":
        for row in matrix:
            run_one(root, row, "qualification", "qualification_01")
    else:
        gate_path = root / "qualification_v3" / "P5D_equivalence_gate_results_v3.json"
        if not gate_path.exists():
            raise RuntimeError("formal timing remains locked before qualification analysis")
        gate = json.loads(gate_path.read_text(encoding="utf-8"))
        if gate.get("status") != "PASS_P5D_EQUIVALENCE_GATES":
            raise RuntimeError("formal timing remains locked because equivalence did not pass")
        for row in matrix:
            for ordinal in range(1, 3):
                run_one(root, row, "warmup", f"warmup_{ordinal:02d}")
            for ordinal in range(1, 11):
                run_one(root, row, "formal", f"run_{ordinal:02d}")
    status_name = "qualification_v3" if args.phase == "qualification" else args.phase
    write_json_new(root / "runtime" / f"{status_name}_execution_status.json", {
        "phase": args.phase,
        "status": "COMPLETE",
        "cells": 18,
        "warmups_per_cell": 0 if args.phase == "qualification" else 2,
        "formal_runs_per_cell": 0 if args.phase == "qualification" else 10,
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
