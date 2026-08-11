"""Frozen L6-D1 case assembly and classification."""

from __future__ import annotations

from dataclasses import dataclass
import csv
import hashlib
import importlib
import json
import math
from pathlib import Path
from typing import Any

from benchmarks.L6_external_host.oracle.l6_stationary_oracle import (
    derive_stationary_oracle,
)
from benchmarks.L6_external_host.src.l6_scipy_adapter import (
    HostExecution,
    ScipyLifecycleAdapter,
    event_rows,
    output_rows,
)
from benchmarks.L6_external_host.src.l6_state import DESIGN_VERSION


EXPECTED_CASES = {
    "L6-EH-RT-01": "PASS_SAFE_EXTERNAL_HOST_RETRY",
    "L6-EH-OP-01": "PASS_EXTERNAL_HOST_OUTPUT_PROVENANCE",
    "L6-EH-CO-01": "PASS_EXTERNAL_HOST_CALLBACK_ORDER_PARITY",
    "L6-EH-RT-02": "DETECT_EXTERNAL_HOST_FINITE_DRIFT",
    "L6-EH-TV-01": "REJECT_VERSION_MISMATCH_BEFORE_HOST_CORRECTION",
}


@dataclass
class CaseArtifacts:
    case_result: dict[str, Any]
    event_rows: list[dict[str, Any]]
    comparison_rows: list[dict[str, Any]]
    accepted_output_rows: list[dict[str, Any]]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_frozen_design(root: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    base = root / "benchmarks" / "L6_external_host"
    freeze = json.loads((base / "L6_D1_execution_freeze.json").read_text())
    with (base / "L6_D1_case_matrix.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        matrix = list(csv.DictReader(handle))
    return freeze, matrix


def validate_frozen_design(root: Path) -> None:
    freeze, matrix = load_frozen_design(root)
    if freeze["design_version"] != DESIGN_VERSION:
        raise RuntimeError("L6 design-version mismatch")
    if freeze["design_status"] != "FROZEN_NOT_IMPLEMENTED":
        raise RuntimeError("Unexpected frozen design status")
    if freeze["execution_authorized"] or freeze["results_exist"]:
        raise RuntimeError("Frozen design must remain unexecuted")
    if [row["case_id"] for row in matrix] != list(EXPECTED_CASES):
        raise RuntimeError("L6 case order differs from frozen matrix")
    base = root / "benchmarks" / "L6_external_host"
    expected = {
        "L6_D1_case_matrix.csv": (
            "c073d796d661ef1113577f3d625c65106328a48fc83f28eb936b5f58671eee81"
        ),
        "L6_D1_execution_freeze.json": (
            "7180148893dc8e17ab6d3b882939f7782c9c59622b798a248dd09adca7e7c469"
        ),
    }
    for name, digest in expected.items():
        if _sha256(base / name) != digest:
            raise RuntimeError(f"Frozen input hash mismatch: {name}")
    module_hashes = {
        "scipy.optimize._lsq.least_squares": (
            "b6becbe3b248ea5edcbc40434f101f5d46e5304b66d3c97331bced459dc38765"
        ),
        "scipy.optimize._lsq.trf": (
            "a174a6e79b67067823804666c9e97413dd0d432c7ac7cd148c0c9ee5cfa9732b"
        ),
        "scipy.optimize._lsq.common": (
            "6bdec514d2b0e8172cd438421218ae3977f144ad89867346157ea885408f489e"
        ),
        "scipy._lib._util": (
            "3a3837ae4094263e936394bae513b3a91387b12fa9cb7bae91f43117b5bc3293"
        ),
    }
    for module_name, digest in module_hashes.items():
        module_path = Path(importlib.import_module(module_name).__file__)
        if _sha256(module_path) != digest:
            raise RuntimeError(f"External host hash mismatch: {module_name}")


def _execution_dict(execution: HostExecution) -> dict[str, Any]:
    return {
        "path_id": execution.path_id,
        "variant": execution.variant,
        "jacobian_mode": execution.jacobian_mode,
        "success": execution.success,
        "status": execution.status,
        "message": execution.message,
        "final_x": execution.final_x,
        "final_residual": execution.final_residual,
        "final_cost": execution.final_cost,
        "nfev": execution.nfev,
        "njev": execution.njev,
        "residual_event_count": sum(
            event["event"] == "FormResidual" for event in execution.events
        ),
        "tangent_event_count": sum(
            event["event"] == "FormTangent" for event in execution.events
        ),
        "accepted_callback_count": sum(
            event["event"] == "HostAcceptedCallback"
            for event in execution.events
        ),
        "nonaccepted_residual_count": len(
            execution.nonaccepted_residual_events
        ),
        "committed_before_fingerprint": (
            execution.committed_before.fingerprint
        ),
        "committed_after_fingerprint": (
            execution.committed_after.fingerprint
            if execution.committed_after is not None
            else None
        ),
        "committed_transition_valid": (
            execution.committed_transition_valid
        ),
        "persistent_before_fingerprint": (
            execution.persistent_before_fingerprint
        ),
        "persistent_after_fingerprint": (
            execution.persistent_after_fingerprint
        ),
        "rejected_candidates_unreachable": (
            execution.rejected_candidates_unreachable
        ),
        "accepted_output_count": len(execution.outputs),
        "all_values_finite": execution.all_values_finite,
        "version_mismatch": execution.version_mismatch,
    }


def _tag_rows(
    rows: list[dict[str, Any]], *, case_id: str, run_id: str
) -> list[dict[str, Any]]:
    return [
        {"case_id": case_id, "run_id": run_id, **row}
        for row in rows
    ]


def _comparison(
    *,
    case_id: str,
    run_id: str,
    metric: str,
    left_path: str,
    right_path: str,
    left: float,
    right: float,
    gate: float | None,
    passed: bool,
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "run_id": run_id,
        "metric": metric,
        "left_path": left_path,
        "right_path": right_path,
        "left_value": left,
        "right_value": right,
        "delta": right - left,
        "absolute_delta": abs(right - left),
        "gate": gate,
        "pass_flag": passed,
    }


def _versions_compatible(execution: HostExecution) -> bool:
    tangents = [
        event
        for event in execution.events
        if event["event"] == "FormTangent"
    ]
    return bool(tangents) and all(
        event.get("version_compatible") is True for event in tangents
    )


def _case_result(
    *,
    case_id: str,
    run_id: str,
    classification: str,
    gates: dict[str, bool],
    executions: list[HostExecution],
    details: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "L6-D1-CASE-1.0",
        "design_version": DESIGN_VERSION,
        "host_version": "L6-SCIPY-TRF-1.17.1",
        "case_id": case_id,
        "run_id": run_id,
        "expected_classification": EXPECTED_CASES[case_id],
        "observed_classification": classification,
        "pass_flag": (
            classification == EXPECTED_CASES[case_id]
            and all(gates.values())
        ),
        "gates": gates,
        "executions": [_execution_dict(execution) for execution in executions],
        "details": details,
        "abaqus_used": False,
        "comsol_used": False,
        "production_model_used": False,
        "processes_per_repetition": 1,
        "threads_per_process": 1,
    }


def _safe_execution(path_id: str) -> HostExecution:
    return ScipyLifecycleAdapter(
        path_id=path_id, variant="safe_transactional"
    ).run(jacobian_mode="analytic")


def execute_l6_case(root: Path, case_id: str, run_id: str) -> CaseArtifacts:
    validate_frozen_design(root)
    if case_id not in EXPECTED_CASES:
        raise ValueError(f"Unauthorized L6 case: {case_id}")
    if not run_id:
        raise ValueError("run_id is required")
    oracle = derive_stationary_oracle()
    events: list[dict[str, Any]] = []
    outputs: list[dict[str, Any]] = []
    comparisons: list[dict[str, Any]] = []

    if case_id == "L6-EH-RT-01":
        safe = _safe_execution("safe_analytic")
        x_error = abs(safe.final_x - float(oracle["x_star"]))
        gates = {
            "host_success": safe.success,
            "genuine_nonaccepted_trial": (
                len(safe.nonaccepted_residual_events) >= 1
            ),
            "oracle_x_within_1e_6": x_error <= 1.0e-6,
            "committed_transition_valid": safe.committed_transition_valid,
            "versions_compatible": _versions_compatible(safe),
            "rejected_candidates_unreachable": (
                safe.rejected_candidates_unreachable
            ),
            "one_accepted_output": len(safe.outputs) == 1,
            "all_values_finite": safe.all_values_finite,
        }
        classification = (
            EXPECTED_CASES[case_id]
            if all(gates.values())
            else "FAIL_SAFE_EXTERNAL_HOST_RETRY"
        )
        comparisons.append(
            _comparison(
                case_id=case_id,
                run_id=run_id,
                metric="oracle_x",
                left_path="stationary_oracle",
                right_path=safe.path_id,
                left=float(oracle["x_star"]),
                right=safe.final_x,
                gate=1.0e-6,
                passed=gates["oracle_x_within_1e_6"],
            )
        )
        result = _case_result(
            case_id=case_id,
            run_id=run_id,
            classification=classification,
            gates=gates,
            executions=[safe],
            details={"oracle": oracle, "oracle_x_absolute_error": x_error},
        )
        events.extend(event_rows(safe))
        outputs.extend(output_rows(safe))

    elif case_id == "L6-EH-OP-01":
        safe = _safe_execution("output_provenance")
        names = [event["event"] for event in safe.events]
        output_index = names.index("OutputAcceptedState")
        commit_index = names.index("Commit")
        return_index = names.index("HostReturn")
        source_ids = {output.source_event_id for output in safe.outputs}
        accepted_ids = {
            event["event_id"] for event in safe.accepted_residual_events
        }
        gates = {
            "host_success": safe.success,
            "genuine_nonaccepted_trial": (
                len(safe.nonaccepted_residual_events) >= 1
            ),
            "one_accepted_output": len(safe.outputs) == 1,
            "output_after_host_return_and_commit": (
                return_index < commit_index < output_index
            ),
            "output_matches_host_return": (
                len(safe.outputs) == 1
                and safe.outputs[0].x.hex() == safe.final_x.hex()
            ),
            "output_source_is_accepted_residual": (
                source_ids.issubset(accepted_ids)
            ),
            "rejected_candidates_unreachable": (
                safe.rejected_candidates_unreachable
            ),
            "committed_transition_valid": safe.committed_transition_valid,
            "all_values_finite": safe.all_values_finite,
        }
        classification = (
            EXPECTED_CASES[case_id]
            if all(gates.values())
            else "FAIL_EXTERNAL_HOST_OUTPUT_PROVENANCE"
        )
        result = _case_result(
            case_id=case_id,
            run_id=run_id,
            classification=classification,
            gates=gates,
            executions=[safe],
            details={
                "host_return_event_ordinal": return_index + 1,
                "commit_event_ordinal": commit_index + 1,
                "output_event_ordinal": output_index + 1,
            },
        )
        events.extend(event_rows(safe))
        outputs.extend(output_rows(safe))

    elif case_id == "L6-EH-CO-01":
        analytic = _safe_execution("analytic_jacobian")
        finite_difference = ScipyLifecycleAdapter(
            path_id="finite_difference_jacobian",
            variant="safe_transactional",
        ).run(jacobian_mode="2-point")
        x_delta = abs(finite_difference.final_x - analytic.final_x)
        cost_delta = abs(
            finite_difference.final_cost - analytic.final_cost
        )
        analytic_residual_events = sum(
            event["event"] == "FormResidual" for event in analytic.events
        )
        finite_residual_events = sum(
            event["event"] == "FormResidual"
            for event in finite_difference.events
        )
        gates = {
            "both_host_paths_success": (
                analytic.success and finite_difference.success
            ),
            "callback_histories_differ": (
                finite_residual_events > analytic_residual_events
            ),
            "accepted_x_within_1e_6": x_delta <= 1.0e-6,
            "accepted_cost_within_1e_8": cost_delta <= 1.0e-8,
            "analytic_transition_valid": (
                analytic.committed_transition_valid
            ),
            "finite_difference_transition_valid": (
                finite_difference.committed_transition_valid
            ),
            "both_outputs_provenanced": (
                len(analytic.outputs) == 1
                and len(finite_difference.outputs) == 1
                and analytic.rejected_candidates_unreachable
                and finite_difference.rejected_candidates_unreachable
            ),
            "all_values_finite": (
                analytic.all_values_finite
                and finite_difference.all_values_finite
            ),
        }
        classification = (
            EXPECTED_CASES[case_id]
            if all(gates.values())
            else "FAIL_EXTERNAL_HOST_CALLBACK_ORDER_PARITY"
        )
        comparisons.extend(
            [
                _comparison(
                    case_id=case_id,
                    run_id=run_id,
                    metric="accepted_x",
                    left_path=analytic.path_id,
                    right_path=finite_difference.path_id,
                    left=analytic.final_x,
                    right=finite_difference.final_x,
                    gate=1.0e-6,
                    passed=gates["accepted_x_within_1e_6"],
                ),
                _comparison(
                    case_id=case_id,
                    run_id=run_id,
                    metric="accepted_cost",
                    left_path=analytic.path_id,
                    right_path=finite_difference.path_id,
                    left=analytic.final_cost,
                    right=finite_difference.final_cost,
                    gate=1.0e-8,
                    passed=gates["accepted_cost_within_1e_8"],
                ),
                _comparison(
                    case_id=case_id,
                    run_id=run_id,
                    metric="residual_event_count",
                    left_path=analytic.path_id,
                    right_path=finite_difference.path_id,
                    left=float(analytic_residual_events),
                    right=float(finite_residual_events),
                    gate=None,
                    passed=gates["callback_histories_differ"],
                ),
            ]
        )
        result = _case_result(
            case_id=case_id,
            run_id=run_id,
            classification=classification,
            gates=gates,
            executions=[analytic, finite_difference],
            details={
                "accepted_x_absolute_delta": x_delta,
                "accepted_cost_absolute_delta": cost_delta,
                "analytic_residual_event_count": analytic_residual_events,
                "finite_difference_residual_event_count": (
                    finite_residual_events
                ),
            },
        )
        for execution in (analytic, finite_difference):
            events.extend(event_rows(execution))
            outputs.extend(output_rows(execution))

    elif case_id == "L6-EH-RT-02":
        safe = _safe_execution("safe_control")
        unsafe = ScipyLifecycleAdapter(
            path_id="unsafe_persistent_cache",
            variant="unsafe_persistent_cache",
        ).run(jacobian_mode="analytic")
        drift = abs(unsafe.final_x - safe.final_x)
        unsafe_nonaccepted_mutations = [
            event
            for event in unsafe.nonaccepted_residual_events
            if event["persistent_before_fingerprint"]
            != event["persistent_after_fingerprint"]
        ]
        gates = {
            "safe_control_success": (
                safe.success
                and len(safe.nonaccepted_residual_events) >= 1
                and safe.committed_transition_valid
            ),
            "unsafe_host_success": unsafe.success,
            "unsafe_nonaccepted_mutation_detected": (
                len(unsafe_nonaccepted_mutations) >= 1
            ),
            "finite_drift_above_1e_8": drift >= 1.0e-8,
            "committed_immutable_until_return": all(
                event["committed_fingerprint"]
                == unsafe.committed_before.fingerprint
                for event in unsafe.events
                if event["event"]
                not in {"Commit", "OutputAcceptedState"}
            ),
            "unsafe_transition_valid": (
                unsafe.committed_transition_valid
            ),
            "all_values_finite": (
                safe.all_values_finite and unsafe.all_values_finite
            ),
        }
        classification = (
            EXPECTED_CASES[case_id]
            if all(gates.values())
            else "FAIL_EXTERNAL_HOST_UNSAFE_CONTROL"
        )
        comparisons.append(
            _comparison(
                case_id=case_id,
                run_id=run_id,
                metric="accepted_x",
                left_path=safe.path_id,
                right_path=unsafe.path_id,
                left=safe.final_x,
                right=unsafe.final_x,
                gate=1.0e-8,
                passed=gates["finite_drift_above_1e_8"],
            )
        )
        result = _case_result(
            case_id=case_id,
            run_id=run_id,
            classification=classification,
            gates=gates,
            executions=[safe, unsafe],
            details={
                "accepted_x_absolute_drift": drift,
                "unsafe_nonaccepted_mutation_count": len(
                    unsafe_nonaccepted_mutations
                ),
                "negative_control_only": True,
            },
        )
        for execution in (safe, unsafe):
            events.extend(event_rows(execution))
            outputs.extend(output_rows(execution))

    else:
        mismatch = ScipyLifecycleAdapter(
            path_id="version_mismatch",
            variant="version_mismatch",
        ).mismatch_execution()
        mismatch_data = mismatch.version_mismatch or {}
        gates = {
            "version_mismatch_detected": bool(mismatch_data),
            "finite_operator_values": bool(
                mismatch_data.get("all_values_finite")
            ),
            "rejected_before_host_correction": bool(
                mismatch_data.get(
                    "rejected_before_host_correction"
                )
            ),
            "no_accepted_callback": not any(
                event["event"] == "HostAcceptedCallback"
                for event in mismatch.events
            ),
            "no_commit": mismatch.committed_after is None,
            "no_accepted_output": len(mismatch.outputs) == 0,
            "committed_state_unchanged": (
                mismatch.committed_before.fingerprint
                == mismatch.events[0]["committed_fingerprint"]
            ),
            "persistent_state_unchanged": (
                mismatch.persistent_before_fingerprint
                == mismatch.persistent_after_fingerprint
            ),
        }
        classification = (
            EXPECTED_CASES[case_id]
            if all(gates.values())
            else "FAIL_VERSION_MISMATCH_CONTRACT"
        )
        result = _case_result(
            case_id=case_id,
            run_id=run_id,
            classification=classification,
            gates=gates,
            executions=[mismatch],
            details={"version_mismatch": mismatch_data},
        )
        events.extend(event_rows(mismatch))

    return CaseArtifacts(
        case_result=result,
        event_rows=_tag_rows(events, case_id=case_id, run_id=run_id),
        comparison_rows=comparisons,
        accepted_output_rows=_tag_rows(
            outputs, case_id=case_id, run_id=run_id
        ),
    )


__all__ = [
    "CaseArtifacts",
    "EXPECTED_CASES",
    "execute_l6_case",
    "load_frozen_design",
    "validate_frozen_design",
]
