"""Double-locked one-case runner for L3-D1.0a."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import platform
import sys

from benchmarks.L3_poroelastic_consolidation.src.l3_cases import (
    COMPARISON_COLUMNS,
    EVENT_COLUMNS,
    execute_case,
    load_design,
)


AUTHORIZED_CASES = (
    "L3-REF-01", "L3-CV-S-01", "L3-CV-T-01", "L3-MB-01",
    "L3-ST-01", "L3-RT-01", "L3-RT-02",
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run one authorized L3-D1 case")
    parser.add_argument("--case-id", required=True, choices=AUTHORIZED_CASES)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--execute-authorized", action="store_true")
    parser.add_argument("--output-root", type=Path, default=None)
    return parser


def _authorize(args: argparse.Namespace) -> None:
    if not args.execute_authorized:
        raise SystemExit("Execution denied: --execute-authorized is required")
    if os.environ.get("L3_D1_EXECUTION_AUTHORIZED") != "YES":
        raise SystemExit("Execution denied: L3_D1_EXECUTION_AUTHORIZED=YES is required")
    if os.environ.get("L3_D1_THREADS") != "1":
        raise SystemExit("Execution denied: L3_D1_THREADS=1 is required")


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    _authorize(args)
    benchmark_root = Path(__file__).resolve().parent
    ncs_root = benchmark_root.parents[1]
    freeze, matrix = load_design(ncs_root)
    if args.case_id not in matrix:
        raise SystemExit(f"Unauthorized frozen case: {args.case_id}")
    output_root = args.output_root or benchmark_root / "results" / "L3_D1_poroelastic_consolidation"
    output = output_root / args.case_id / args.run_id
    if output.exists():
        raise SystemExit(f"Refusing to overwrite existing output: {output}")

    payload = execute_case(ncs_root, args.case_id, args.run_id)
    result = payload["case_result"]
    comparisons = payload["field_comparison"]
    events = payload["poro_event_log"]
    output.mkdir(parents=True, exist_ok=False)

    result_path = output / "case_result.json"
    comparison_path = output / "field_comparison.csv"
    event_path = output / "poro_event_log.csv"
    manifest_path = output / "case_manifest.json"
    _write_json(result_path, result)
    with comparison_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COMPARISON_COLUMNS, extrasaction="raise")
        writer.writeheader()
        writer.writerows({key: row.get(key, "NA") for key in COMPARISON_COLUMNS} for row in comparisons)
    with event_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=EVENT_COLUMNS, extrasaction="raise")
        writer.writeheader()
        writer.writerows({key: row.get(key, "NA") for key in EVENT_COLUMNS} for row in events)

    _write_json(manifest_path, {
        "design_version": freeze["design_version"],
        "host_version": result["host_version"],
        "case_id": args.case_id,
        "run_id": args.run_id,
        "execution_authorized": True,
        "processes_per_repetition": 1,
        "threads_per_process": 1,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "thread_environment": {
            key: os.environ.get(key)
            for key in ("L3_D1_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS")
        },
        "abaqus_used": False,
        "production_model_used": False,
        "inputs": {
            "L3_D1_execution_freeze.json": _sha(benchmark_root / "L3_D1_execution_freeze.json"),
            "L3_D0_case_matrix.csv": _sha(benchmark_root / "L3_D0_case_matrix.csv"),
        },
        "outputs": {path.name: _sha(path) for path in (result_path, comparison_path, event_path)},
        "manifest_self_hash_embedded": False,
    })
    return 0 if result["pass_flag"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
