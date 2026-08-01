"""Double-locked one-case runner for L2-D5.0a."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import csv
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from src.l2_d5_checkpoint_provenance import (
    AUTHORIZED_CASES,
    COMPARISON_COLUMNS,
    DESIGN_VERSION,
    EVENT_LOG_COLUMNS,
    HOST_VERSION,
    CheckpointCaseResult,
    execute_checkpoint_provenance_case,
)


AUTHORIZATION_ENVIRONMENT_VARIABLE = "L2_D5_EXECUTION_AUTHORIZED"
AUTHORIZATION_ENVIRONMENT_VALUE = "YES"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run one separately authorized L2-D5 checkpoint case."
    )
    parser.add_argument("--case-id", required=True, choices=AUTHORIZED_CASES)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--execute-authorized", action="store_true")
    parser.add_argument("--output-root", type=Path, default=None)
    return parser


def _require_double_authorization(arguments: argparse.Namespace) -> None:
    if not arguments.execute_authorized:
        raise SystemExit("Execution denied: --execute-authorized is required")
    if os.environ.get(AUTHORIZATION_ENVIRONMENT_VARIABLE) != AUTHORIZATION_ENVIRONMENT_VALUE:
        raise SystemExit("Execution denied: L2_D5_EXECUTION_AUTHORIZED=YES is required")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_outputs(output_directory: Path, result: CheckpointCaseResult) -> None:
    output_directory.mkdir(parents=True, exist_ok=False)
    event_path = output_directory / "checkpoint_event_log.csv"
    comparison_path = output_directory / "checkpoint_comparison.csv"
    result_path = output_directory / "case_result.json"
    manifest_path = output_directory / "case_manifest.json"

    with event_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=EVENT_LOG_COLUMNS)
        writer.writeheader()
        for event in result.events:
            writer.writerow(asdict(event))

    comparison_row = {
        "case_id": result.case_id,
        "run_id": result.run_id,
        **asdict(result.comparison),
        "classification": result.observed_classification,
        "pass_flag": result.pass_flag,
    }
    with comparison_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=COMPARISON_COLUMNS)
        writer.writeheader()
        writer.writerow({key: comparison_row.get(key) for key in COMPARISON_COLUMNS})

    _write_json(result_path, result.to_dict())
    _write_json(
        manifest_path,
        {
            "design_version": DESIGN_VERSION,
            "host_version": HOST_VERSION,
            "case_id": result.case_id,
            "run_id": result.run_id,
            "execution_authorized": True,
            "processes_per_repetition": 1,
            "threads_per_process": 1,
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
        output_root = benchmark_root / "results" / "L2_D5_checkpoint_provenance"
    result = execute_checkpoint_provenance_case(
        benchmark_root,
        arguments.case_id,
        arguments.run_id,
    )
    _write_outputs(output_root / arguments.case_id / arguments.run_id, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
