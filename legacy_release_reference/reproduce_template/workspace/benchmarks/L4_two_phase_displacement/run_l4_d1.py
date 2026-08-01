"""Double-locked one-case runner for L4-D1.0."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import platform
import sys


BENCHMARK_ROOT = Path(__file__).resolve().parent
NCS_ROOT = BENCHMARK_ROOT.parents[1]
if str(NCS_ROOT) not in sys.path:
    sys.path.insert(0, str(NCS_ROOT))

from benchmarks.L4_two_phase_displacement.src.l4_cases import (
    EVENT_COLUMNS,
    METRIC_COLUMNS,
    PROFILE_COLUMNS,
    execute_case,
    load_design,
)


AUTHORIZED_CASES = (
    "L4-REF-01",
    "L4-CV-S-01",
    "L4-CV-T-01",
    "L4-MB-W-01",
    "L4-MB-N-01",
    "L4-FR-01",
    "L4-MECH-01",
    "L4-ST-01",
    "L4-RT-01",
    "L4-RT-02",
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(
            value,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        ) + "\n",
        encoding="utf-8",
    )


def _write_csv(path: Path, columns: tuple[str, ...], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="raise")
        writer.writeheader()
        writer.writerows(
            {key: row.get(key, "NA") for key in columns} for row in rows
        )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run one authorized L4-D1 case")
    parser.add_argument("--case-id", required=True, choices=AUTHORIZED_CASES)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--execute-authorized", action="store_true")
    parser.add_argument("--output-root", type=Path, default=None)
    return parser


def _authorize(args: argparse.Namespace) -> None:
    if not args.execute_authorized:
        raise SystemExit("Execution denied: --execute-authorized is required")
    if os.environ.get("L4_D1_EXECUTION_AUTHORIZED") != "YES":
        raise SystemExit("Execution denied: L4_D1_EXECUTION_AUTHORIZED=YES is required")
    if os.environ.get("L4_D1_THREADS") != "1":
        raise SystemExit("Execution denied: L4_D1_THREADS=1 is required")


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    _authorize(args)
    benchmark_root = BENCHMARK_ROOT
    ncs_root = NCS_ROOT
    freeze, matrix = load_design(ncs_root)
    if args.case_id not in matrix:
        raise SystemExit(f"Unauthorized frozen case: {args.case_id}")
    output_root = args.output_root or benchmark_root / "results" / "L4_D1_two_phase_displacement"
    output = output_root / args.case_id / args.run_id
    if output.exists():
        raise SystemExit(f"Refusing to overwrite existing output: {output}")

    payload = execute_case(ncs_root, args.case_id, args.run_id)
    result = payload["case_result"]
    metrics = payload["metric_comparison"]
    profiles = payload["accepted_profile"]
    events = payload["phase_event_log"]
    output.mkdir(parents=True, exist_ok=False)

    result_path = output / "case_result.json"
    metric_path = output / "metric_comparison.csv"
    profile_path = output / "accepted_profile.csv"
    event_path = output / "phase_event_log.csv"
    manifest_path = output / "case_manifest.json"
    _write_json(result_path, result)
    _write_csv(metric_path, METRIC_COLUMNS, metrics)
    _write_csv(profile_path, PROFILE_COLUMNS, profiles)
    _write_csv(event_path, EVENT_COLUMNS, events)

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
            for key in (
                "L4_D1_THREADS",
                "OMP_NUM_THREADS",
                "MKL_NUM_THREADS",
                "OPENBLAS_NUM_THREADS",
            )
        },
        "abaqus_used": False,
        "production_model_used": False,
        "inputs": {
            "L4_D1_execution_freeze.json": _sha(benchmark_root / "L4_D1_execution_freeze.json"),
            "L4_D0_case_matrix.csv": _sha(benchmark_root / "L4_D0_case_matrix.csv"),
        },
        "outputs": {
            path.name: _sha(path)
            for path in (result_path, metric_path, profile_path, event_path)
        },
        "manifest_self_hash_embedded": False,
    })
    return 0 if result["pass_flag"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

