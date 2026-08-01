"""One-case, one-process runner for frozen L6-D1."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _write_csv(
    path: Path, rows: list[dict[str, Any]], fieldnames: list[str]
) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--execute-authorized", action="store_true")
    return parser


def main() -> int:
    args = _parser().parse_args()
    if not args.execute_authorized:
        raise SystemExit("Missing --execute-authorized")
    if os.environ.get("L6_D1_EXECUTION_AUTHORIZED") != "YES":
        raise SystemExit("L6_D1_EXECUTION_AUTHORIZED must equal YES")
    required_threads = {
        "L6_D1_THREADS": "1",
        "OMP_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
    }
    for name, expected in required_threads.items():
        if os.environ.get(name) != expected:
            raise SystemExit(f"{name} must equal {expected}")

    root = Path(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from benchmarks.L6_external_host.src.l6_cases import (
        EXPECTED_CASES,
        execute_l6_case,
    )

    if args.case_id not in EXPECTED_CASES:
        raise SystemExit(f"Unauthorized case: {args.case_id}")
    output_dir = (
        root
        / "benchmarks"
        / "L6_external_host"
        / "results"
        / "L6_D1_external_host"
        / args.case_id
        / args.run_id
    )
    if output_dir.exists():
        raise SystemExit(f"Refusing to overwrite: {output_dir}")

    artifacts = execute_l6_case(root, args.case_id, args.run_id)
    output_dir.mkdir(parents=True, exist_ok=False)
    result_path = output_dir / "case_result.json"
    event_path = output_dir / "host_event_log.csv"
    comparison_path = output_dir / "host_comparison.csv"
    accepted_path = output_dir / "accepted_output.csv"
    manifest_path = output_dir / "case_manifest.json"

    _write_json(result_path, artifacts.case_result)
    event_fields = [
        "case_id", "run_id", "ordinal", "path_id", "variant", "event",
        "event_id", "resolution", "x", "x_hex", "residual", "tangent",
        "cost", "residual_state_version", "tangent_state_version",
        "candidate_fingerprint", "committed_fingerprint",
        "persistent_before_fingerprint", "persistent_after_fingerprint",
        "candidate_reachable", "output_reachable", "host_nfev",
        "host_njev", "host_nit", "residual_packet_fingerprint",
        "tangent_packet_fingerprint", "version_compatible",
        "accepted_residual_event_id", "source_event_id",
        "output_fingerprint", "committed_before_fingerprint",
        "committed_after_fingerprint", "host_status",
    ]
    comparison_fields = [
        "case_id", "run_id", "metric", "left_path", "right_path",
        "left_value", "right_value", "delta", "absolute_delta", "gate",
        "pass_flag",
    ]
    output_fields = [
        "case_id", "run_id", "path_id", "x", "residual", "cost",
        "committed_fingerprint", "accepted_version", "source_event_id",
        "source",
    ]
    _write_csv(event_path, artifacts.event_rows, event_fields)
    _write_csv(comparison_path, artifacts.comparison_rows, comparison_fields)
    _write_csv(accepted_path, artifacts.accepted_output_rows, output_fields)

    manifest = {
        "schema_version": "L6-D1-RUN-MANIFEST-1.0",
        "design_version": "L6-D1.0",
        "case_id": args.case_id,
        "run_id": args.run_id,
        "external_host": "scipy.optimize.least_squares:1.17.1:trf",
        "threads_per_process": 1,
        "processes_per_repetition": 1,
        "abaqus_used": False,
        "comsol_used": False,
        "production_model_used": False,
        "inputs": {
            "L6_D1_execution_freeze.json": _sha256(
                root
                / "benchmarks"
                / "L6_external_host"
                / "L6_D1_execution_freeze.json"
            ),
            "L6_D1_case_matrix.csv": _sha256(
                root
                / "benchmarks"
                / "L6_external_host"
                / "L6_D1_case_matrix.csv"
            ),
            "l6_scipy_adapter.py": _sha256(
                root
                / "benchmarks"
                / "L6_external_host"
                / "src"
                / "l6_scipy_adapter.py"
            ),
            "l6_cases.py": _sha256(
                root
                / "benchmarks"
                / "L6_external_host"
                / "src"
                / "l6_cases.py"
            ),
        },
        "outputs": {
            result_path.name: _sha256(result_path),
            event_path.name: _sha256(event_path),
            comparison_path.name: _sha256(comparison_path),
            accepted_path.name: _sha256(accepted_path),
        },
        "manifest_self_hash_embedded": False,
    }
    _write_json(manifest_path, manifest)
    return 0 if artifacts.case_result["pass_flag"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
