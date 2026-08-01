"""Separately authorized one-case runner for L2-D2.0a.

The runner is deliberately locked by both a command-line flag and an
environment variable. Importing this module performs no execution or I/O.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from src.l2_d2_callback_order import (
    AUTHORIZED_CASES,
    DESIGN_VERSION,
    EVENT_LOG_COLUMNS,
    HOST_VERSION,
    REPLAY_COMPARISON_COLUMNS,
    CallbackOrderCaseResult,
    execute_callback_order_case,
)


AUTHORIZATION_ENVIRONMENT_VARIABLE = "L2_D2_EXECUTION_AUTHORIZED"
AUTHORIZATION_ENVIRONMENT_VALUE = "YES"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run one separately authorized L2-D2 callback-order case."
    )
    parser.add_argument("--case-id", required=True, choices=AUTHORIZED_CASES)
    parser.add_argument("--run-id", required=True)
    parser.add_argument(
        "--execute-authorized",
        action="store_true",
        help="First execution lock; the environment lock is also required.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=None,
        help="Optional future output root; no directory is created before authorization.",
    )
    return parser


def _require_double_authorization(arguments: argparse.Namespace) -> None:
    if not arguments.execute_authorized:
        raise SystemExit("Execution denied: --execute-authorized is required")
    if os.environ.get(AUTHORIZATION_ENVIRONMENT_VARIABLE) != AUTHORIZATION_ENVIRONMENT_VALUE:
        raise SystemExit(
            "Execution denied: L2_D2_EXECUTION_AUTHORIZED=YES is required"
        )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_event_log(path: Path, result: CallbackOrderCaseResult) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=EVENT_LOG_COLUMNS)
        writer.writeheader()
        for execution in (result.direct, result.extra):
            for row in execution.event_log:
                writer.writerow({key: row.get(key) for key in EVENT_LOG_COLUMNS})


def _write_replay_comparison(path: Path, result: CallbackOrderCaseResult) -> None:
    comparison = result.comparison
    row = {
        "case_id": result.case_id,
        "run_id": result.run_id,
        "variant": result.variant,
        "direct_declared_fingerprint": comparison[
            "direct_declared_replay_context_fingerprint"
        ],
        "extra_declared_fingerprint": comparison[
            "extra_declared_replay_context_fingerprint"
        ],
        "direct_observed_fingerprint": comparison[
            "direct_observed_replay_fingerprint"
        ],
        "extra_observed_fingerprint": comparison[
            "extra_observed_replay_fingerprint"
        ],
        "direct_residual": comparison["direct_residual"],
        "extra_residual": comparison["extra_residual"],
        "delta_residual": comparison["delta_residual"],
        "direct_tangent": comparison["direct_tangent"],
        "extra_tangent": comparison["extra_tangent"],
        "delta_tangent": comparison["delta_tangent"],
        "classification": result.observed_classification,
        "pass_flag": result.pass_flag,
    }
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=REPLAY_COMPARISON_COLUMNS)
        writer.writeheader()
        writer.writerow(row)


def _write_future_outputs(
    output_directory: Path,
    result: CallbackOrderCaseResult,
) -> None:
    output_directory.mkdir(parents=True, exist_ok=False)
    event_path = output_directory / "callback_event_log.csv"
    comparison_path = output_directory / "replay_comparison.csv"
    result_path = output_directory / "case_result.json"
    manifest_path = output_directory / "case_manifest.json"

    _write_event_log(event_path, result)
    _write_replay_comparison(comparison_path, result)
    _write_json(result_path, result.to_dict())
    _write_json(
        manifest_path,
        {
            "design_version": DESIGN_VERSION,
            "host_version": HOST_VERSION,
            "case_id": result.case_id,
            "run_id": result.run_id,
            "execution_authorized": True,
            "abaqus_used": False,
            "outputs": {
                event_path.name: _sha256_file(event_path),
                comparison_path.name: _sha256_file(comparison_path),
                result_path.name: _sha256_file(result_path),
            },
            "manifest_self_hash_embedded": False,
        },
    )


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    _require_double_authorization(arguments)

    benchmark_root = Path(__file__).resolve().parent
    output_root = arguments.output_root
    if output_root is None:
        output_root = benchmark_root / "results" / "L2_D2_callback_order"
    output_directory = output_root / arguments.case_id / arguments.run_id

    result = execute_callback_order_case(
        benchmark_root,
        arguments.case_id,
        arguments.run_id,
    )
    _write_future_outputs(output_directory, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
