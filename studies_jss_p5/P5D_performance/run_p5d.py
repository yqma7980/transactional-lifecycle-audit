from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path
import sys
import time


PROCESS_START_WALL = time.perf_counter()
PROCESS_START_CPU = time.process_time()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Execute one frozen JSS P5D cell repetition")
    parser.add_argument("--cell-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--phase", choices=("qualification", "warmup", "formal"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute-authorized", action="store_true")
    return parser.parse_args()


def load_cell(root: Path, cell_id: str) -> dict[str, str]:
    matrix = root / "frozen_inputs" / "P5D_performance_matrix.csv"
    with matrix.open("r", encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    matches = [row for row in rows if row["cell_id"] == cell_id]
    if len(matches) != 1:
        raise ValueError(f"cell ID is not uniquely frozen: {cell_id}")
    return matches[0]


def main() -> int:
    args = parse_args()
    if not args.execute_authorized or os.environ.get("P5D_EXECUTION_AUTHORIZED") != "YES":
        raise SystemExit("P5D dual authorization lock rejected execution")
    root = Path(__file__).resolve().parent
    sys.path.insert(0, str(root / "src"))
    sys.path.insert(0, str(root / "subjects"))
    sys.path.insert(0, str(root / "subjects" / "p4d"))
    from p5d_common import (
        DESIGN_ID,
        bind_process_to_cpu0,
        environment_packet,
        finite_values,
        peak_rss_bytes,
        write_json_new,
    )
    from p5d_subjects import execute_subject

    cell = load_cell(root, args.cell_id)
    if cell["status"] != "FROZEN_NOT_IMPLEMENTED" or cell["execution_authorized"].lower() != "false":
        raise RuntimeError("frozen matrix identity changed")
    bind_process_to_cpu0()
    initialization_seconds = time.perf_counter() - PROCESS_START_WALL
    subject_started = time.perf_counter()
    subject_result = execute_subject(
        cell["subject_id"], cell["workload_id"], cell["instrumentation_mode"]
    )
    subject_elapsed = time.perf_counter() - subject_started
    teardown_started = time.perf_counter()
    environment = environment_packet()
    pass_flag = bool(
        subject_result["all_values_finite"]
        and (
            cell["instrumentation_mode"] == "M0_AUDIT_OFF"
            or subject_result["audit"]["generic_replay_equal"] is True
        )
        and finite_values(subject_result)
        and environment.get("mpi_size") == 1
        and environment["threads"] == {
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
        }
        and environment.get("affinity") == [0]
    )
    teardown_seconds = time.perf_counter() - teardown_started
    payload = {
        "design_id": DESIGN_ID,
        "implementation_id": "JSS-P5D-IMPLEMENTATION-1.0",
        "cell_id": args.cell_id,
        "run_id": args.run_id,
        "phase": args.phase,
        "subject_id": cell["subject_id"],
        "workload_id": cell["workload_id"],
        "instrumentation_mode": cell["instrumentation_mode"],
        "processes": 1,
        "threads": 1,
        "initialization_seconds": initialization_seconds,
        "subject_elapsed_seconds": subject_elapsed,
        "teardown_seconds": teardown_seconds,
        "internal_wall_time_seconds": time.perf_counter() - PROCESS_START_WALL,
        "cpu_time_seconds": time.process_time() - PROCESS_START_CPU,
        "peak_rss_bytes": peak_rss_bytes(),
        "environment": environment,
        "result": subject_result,
        "pass_flag": pass_flag,
        "abaqus_used": False,
        "production_model_used": False,
    }
    write_json_new(args.output, payload)
    return 0 if pass_flag else 3


if __name__ == "__main__":
    raise SystemExit(main())
