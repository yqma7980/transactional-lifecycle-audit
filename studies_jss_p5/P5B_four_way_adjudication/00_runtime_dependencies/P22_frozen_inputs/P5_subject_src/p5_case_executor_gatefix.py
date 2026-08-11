from __future__ import annotations

"""Structured recording for nonquiet P5 strength-sweep observations."""

import json
from typing import Any

import numpy as np

import p5_case_executor as frozen


ORIGINAL_EXECUTE_CASE = frozen.execute_case


def metric_distances_with_availability(
    left: dict[str, np.ndarray],
    right: dict[str, np.ndarray],
) -> tuple[dict[str, float | None], dict[str, bool]]:
    scales = frozen.load_metric_scales(
        frozen.FREEZE_ROOT / "P5_field_and_metric_scale_registry.csv"
    )
    distances: dict[str, float | None] = {}
    availability: dict[str, bool] = {}
    for metric_id, scale in scales.items():
        left_values = np.asarray(left[metric_id], dtype=np.float64)
        right_values = np.asarray(right[metric_id], dtype=np.float64)
        comparable = bool(
            left_values.size > 0
            and left_values.shape == right_values.shape
        )
        availability[metric_id] = comparable
        distances[metric_id] = (
            frozen.scaled_distance(
                left_values.tolist(),
                right_values.tolist(),
                scale.scale,
            )
            if comparable
            else None
        )
    return distances, availability


def execute_case_gateaware(
    *,
    case_id: str,
    run_id: str,
    result_directory,
    environment: dict[str, Any],
    strength_index: int | None,
    eta: float | None,
    thresholds: dict[str, float] | None,
) -> dict[str, Any]:
    if case_id not in frozen.SCALED_CASES:
        return ORIGINAL_EXECUTE_CASE(
            case_id=case_id,
            run_id=run_id,
            result_directory=result_directory,
            environment=environment,
            strength_index=strength_index,
            eta=eta,
            thresholds=thresholds,
        )
    if result_directory.exists() and any(result_directory.iterdir()):
        raise RuntimeError("P5 result directory must be empty")
    if "semantic_environment_hash" not in environment:
        raise RuntimeError("runner did not declare semantic_environment_hash")
    if strength_index is None or eta is None or thresholds is None:
        raise RuntimeError(
            "scaled P5 case requires strength index, eta and frozen thresholds"
        )

    family_id = frozen.SCALED_CASES[case_id]
    safe = frozen.run_p5_history(family_id, False, 0.0, run_id)
    faulty = frozen.run_p5_history(family_id, True, eta, run_id)
    histories = [safe, faulty]
    left_path = right_path = "ARITH_A_REFERENCE"
    left, left_contributions = frozen._metric_packet(safe, left_path)
    right, right_contributions = frozen._metric_packet(faulty, right_path)
    metric_distances, metric_available = metric_distances_with_availability(
        left,
        right,
    )

    operator_metrics_available = bool(
        metric_available["M_R"] and metric_available["M_J"]
    )
    if not operator_metrics_available:
        raise RuntimeError(
            "P5 replay operator metrics are unavailable after a gate stop"
        )

    expected_verdict = frozen.EXPECTED_FAULT_VERDICTS[family_id]
    observed_verdict = (
        faulty.mutation_record["expected_lifecycle_verdict"]
        if faulty.mutation_record
        else "MISSING_MUTATION"
    )
    lifecycle_violation = bool(
        faulty.lifecycle_violation_present
        and observed_verdict == expected_verdict
    )
    endpoint_quiet = all(
        metric_available[metric_id]
        and metric_distances[metric_id] is not None
        and metric_distances[metric_id] <= 1.0e-10
        for metric_id in frozen.CONVENTIONAL_QUIET_METRICS
    )
    conventional_quiet = bool(
        safe.conventional_quiet
        and faulty.conventional_quiet
        and endpoint_quiet
    )
    all_values_finite = frozen._all_finite(left) and frozen._all_finite(right)
    z_residual = float(metric_distances["M_R"] / thresholds["M_R"])
    z_tangent = float(metric_distances["M_J"] / thresholds["M_J"])
    pass_flag = bool(
        lifecycle_violation
        and all_values_finite
        and operator_metrics_available
    )
    incomplete_history = bool(
        safe.prerequisite_status != "PASS"
        or faulty.prerequisite_status != "PASS"
    )
    classification = "SCALED_CASE_EXECUTION_INVALID"
    if pass_flag and conventional_quiet:
        classification = "SWEEP_OBSERVATION_READY_FOR_SELECTION"
    elif pass_flag:
        classification = "SWEEP_NONQUIET_OBSERVATION_READY_FOR_SELECTION"

    result = {
        "case_role": "scaled_development",
        "family_id": family_id,
        "strength_index": int(strength_index),
        "eta": float(eta),
        "expected_lifecycle_verdict": expected_verdict,
        "observed_lifecycle_verdict": observed_verdict,
        "lifecycle_violation_present": lifecycle_violation,
        "metric_distances": metric_distances,
        "metric_comparison_available": metric_available,
        "accepted_output_length_equal": (
            len(safe.output_rows) == len(faulty.output_rows)
        ),
        "incomplete_history_present": incomplete_history,
        "comparison_contract_status": (
            "FULL_METRIC_COMPARISON"
            if all(metric_available.values())
            else "PARTIAL_COMPARISON_AFTER_CONVENTIONAL_GATE"
        ),
        "z_residual": z_residual,
        "z_tangent": z_tangent,
        "z_family": float(max(z_residual, z_tangent)),
        "all_values_finite": all_values_finite,
        "endpoint_quiet": endpoint_quiet,
        "conventional_quiet": conventional_quiet,
        "observed_classification": classification,
        "pass_flag": pass_flag,
        "safe_history": frozen.semantic_history_summary(safe),
        "faulty_history": frozen.semantic_history_summary(faulty),
        "design_version": frozen.DESIGN_VERSION,
        "implementation_version": frozen.IMPLEMENTATION_VERSION,
        "host_version": frozen.HOST_VERSION,
        "case_id": case_id,
        "run_id": run_id,
        "environment_hash": environment["semantic_environment_hash"],
        "formal_execution": True,
        "abaqus_used": False,
        "production_model_used": False,
    }

    frozen.write_json_new(result_directory / "environment.json", environment)
    frozen._write_event_ledger(
        result_directory / "event_ledger.csv",
        histories,
    )
    frozen._write_output_summary(
        result_directory / "accepted_output.csv",
        histories,
    )
    np.savez(
        result_directory / "metric_packets.npz",
        **{f"left_{key}": value for key, value in left.items()},
        **{f"right_{key}": value for key, value in right.items()},
    )
    left_flat = frozen._flatten_contributions(left_contributions)
    right_flat = frozen._flatten_contributions(right_contributions)
    np.savez(
        result_directory / "operator_contributions.npz",
        **{f"left_{key}": value for key, value in left_flat.items()},
        **{f"right_{key}": value for key, value in right_flat.items()},
    )
    frozen.write_json_new(
        result_directory / "case_result.json",
        frozen._jsonable(result),
    )
    files = sorted(
        path for path in result_directory.iterdir() if path.is_file()
    )
    manifest = {
        "case_id": case_id,
        "run_id": run_id,
        "files": [
            {
                "path": path.name,
                "bytes": path.stat().st_size,
                "sha256": frozen.sha256(path),
            }
            for path in files
        ],
        "manifest_self_hash_embedded": False,
    }
    frozen.write_json_new(
        result_directory / "case_manifest.json",
        manifest,
    )
    return result
