"""Double-locked one-case runner for L2-D6.0."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import csv
import hashlib
import json
import os
from pathlib import Path

from src.l2_d6_thread_scheduling import (
    AUTHORIZED_CASES, COMPARISON_COLUMNS, DESIGN_VERSION, EVENT_COLUMNS,
    HOST_VERSION, execute_thread_scheduling_case,
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _parser():
    parser = argparse.ArgumentParser(description="Run one authorized L2-D6 support-envelope case")
    parser.add_argument("--case-id", required=True, choices=AUTHORIZED_CASES)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--execute-authorized", action="store_true")
    parser.add_argument("--output-root", type=Path, default=None)
    return parser


def _authorize(args):
    if not args.execute_authorized:
        raise SystemExit("Execution denied: --execute-authorized is required")
    if os.environ.get("L2_D6_EXECUTION_AUTHORIZED") != "YES":
        raise SystemExit("Execution denied: L2_D6_EXECUTION_AUTHORIZED=YES is required")


def _write_json(path: Path, value):
    path.write_text(json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv=None):
    args = _parser().parse_args(argv)
    _authorize(args)
    root = Path(__file__).resolve().parent
    output_root = args.output_root or root / "results" / "L2_D6_thread_scheduling"
    output = output_root / args.case_id / args.run_id
    result = execute_thread_scheduling_case(root, args.case_id, args.run_id)
    output.mkdir(parents=True, exist_ok=False)
    event_path = output / "scheduling_support_event_log.csv"
    comparison_path = output / "scheduling_support_comparison.csv"
    result_path = output / "case_result.json"
    manifest_path = output / "case_manifest.json"
    with event_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=EVENT_COLUMNS)
        writer.writeheader()
        writer.writerows(result.events)
    row = {"case_id": result.case_id, "run_id": result.run_id, **asdict(result.comparison), "primary_gate_classification": result.primary_gate_classification, "observed_outcome": result.observed_outcome, "pass_flag": result.pass_flag}
    with comparison_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COMPARISON_COLUMNS)
        writer.writeheader()
        writer.writerow({key: row.get(key) for key in COMPARISON_COLUMNS})
    _write_json(result_path, result.to_dict())
    _write_json(manifest_path, {
        "design_version": DESIGN_VERSION,
        "host_version": HOST_VERSION,
        "case_id": result.case_id,
        "run_id": result.run_id,
        "execution_authorized": True,
        "processes_per_repetition": 1,
        "threads_per_process": 1,
        "abaqus_used": False,
        "outputs": {p.name: _sha(p) for p in (event_path, comparison_path, result_path)},
        "manifest_self_hash_embedded": False,
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
