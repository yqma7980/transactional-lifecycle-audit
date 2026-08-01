"""Doubly locked future runner for corrected L2-D3.0b TG-02."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import csv
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from src.l2_d3b_tangent_path import (
    AUTHORIZED_CASES,
    DESIGN_VERSION,
    EVENT_LOG_COLUMNS,
    HOST_VERSION,
    IMPLEMENTATION_REVISION,
    CorrectedTangentPathCaseResult,
    execute_tangent_path_case,
)


AUTHORIZATION_ENVIRONMENT_VARIABLE = "L2_D3B_EXECUTION_AUTHORIZED"
AUTHORIZATION_ENVIRONMENT_VALUE = "YES"
COMPARISON_COLUMNS = (
    "case_id",
    "run_id",
    "left_id",
    "right_id",
    "left_evaluation_count",
    "right_evaluation_count",
    "accepted_field_equal",
    "accepted_fingerprint_equal",
    "iteration_count_equal",
    "left_committed_transition_valid",
    "right_committed_transition_valid",
    "cross_path_committed_fingerprint_equal",
    "committed_transition_valid",
    "candidates_unreachable",
    "all_values_finite",
    "u_delta",
    "sigma_delta",
    "epsilon_p_delta",
    "kappa_delta",
    "force_delta",
    "classification",
    "pass_flag",
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run one separately authorized corrected TG-02 case."
    )
    parser.add_argument("--case-id", required=True, choices=AUTHORIZED_CASES)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--execute-authorized", action="store_true")
    parser.add_argument("--output-root", type=Path, default=None)
    return parser


def _require_double_authorization(arguments: argparse.Namespace) -> None:
    if not arguments.execute_authorized:
        raise SystemExit("Execution denied: --execute-authorized is required")
    if (
        os.environ.get(AUTHORIZATION_ENVIRONMENT_VARIABLE)
        != AUTHORIZATION_ENVIRONMENT_VALUE
    ):
        raise SystemExit(
            "Execution denied: L2_D3B_EXECUTION_AUTHORIZED=YES is required"
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


def _write_event_log(
    path: Path,
    result: CorrectedTangentPathCaseResult,
) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=EVENT_LOG_COLUMNS)
        writer.writeheader()
        for row in result.event_log:
            writer.writerow({key: row.get(key) for key in EVENT_LOG_COLUMNS})


def _comparison_row(
    result: CorrectedTangentPathCaseResult,
) -> dict[str, Any]:
    comparison = result.comparison
    fields = comparison.accepted_fields
    return {
        "case_id": result.case_id,
        "run_id": result.run_id,
        "left_id": comparison.left_id,
        "right_id": comparison.right_id,
        "left_evaluation_count": comparison.left_evaluation_count,
        "right_evaluation_count": comparison.right_evaluation_count,
        "accepted_field_equal": comparison.accepted_field_equal,
        "accepted_fingerprint_equal": comparison.accepted_fingerprint_equal,
        "iteration_count_equal": comparison.iteration_count_equal,
        "left_committed_transition_valid": (
            comparison.left_committed_transition_valid
        ),
        "right_committed_transition_valid": (
            comparison.right_committed_transition_valid
        ),
        "cross_path_committed_fingerprint_equal": (
            comparison.cross_path_committed_fingerprint_equal
        ),
        "committed_transition_valid": comparison.committed_transition_valid,
        "candidates_unreachable": comparison.candidates_unreachable,
        "all_values_finite": comparison.all_values_finite,
        "u_delta": fields.u_delta,
        "sigma_delta": fields.sigma_delta,
        "epsilon_p_delta": fields.epsilon_p_delta,
        "kappa_delta": fields.kappa_delta,
        "force_delta": fields.force_delta,
        "classification": result.observed_classification,
        "pass_flag": result.pass_flag,
    }


def _write_outputs(
    output_directory: Path,
    result: CorrectedTangentPathCaseResult,
) -> None:
    output_directory.mkdir(parents=True, exist_ok=False)
    event_path = output_directory / "tangent_event_log.csv"
    comparison_path = output_directory / "path_comparison.csv"
    result_path = output_directory / "case_result.json"
    manifest_path = output_directory / "case_manifest.json"
    _write_event_log(event_path, result)
    with comparison_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=COMPARISON_COLUMNS)
        writer.writeheader()
        writer.writerow(_comparison_row(result))
    _write_json(result_path, result.to_dict())
    _write_json(
        manifest_path,
        {
            "design_version": DESIGN_VERSION,
            "implementation_revision": IMPLEMENTATION_REVISION,
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
        output_root = benchmark_root / "results" / "L2_D3b_tangent_path"
    output_directory = output_root / arguments.case_id / arguments.run_id

    result = execute_tangent_path_case(
        benchmark_root,
        arguments.case_id,
        arguments.run_id,
    )
    _write_outputs(output_directory, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
