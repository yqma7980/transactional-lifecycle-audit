from __future__ import annotations

import math
from typing import Any

from .adapter_contract import AdapterOutcome
from .common import CaseSpec


FINDING_KEYS = (
    "operator_replay_drift_detected",
    "committed_state_mutated_before_accept",
    "accepted_output_provenance_violation",
    "operator_version_incompatibility",
)


def maximum_absolute_distance(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    if len(left) != len(right):
        raise ValueError("operator packets have different lengths")
    return max((abs(a - b) for a, b in zip(left, right)), default=0.0)


def _signal(detected: bool) -> str:
    return "DETECT" if detected else "QUIET"


def full_verdict(spec: CaseSpec, metrics: dict[str, Any]) -> str:
    if not spec.applicable:
        return "NOT_SUPPORTED"
    if not spec.eligible:
        return "INVALID_DECLARED_STATE"
    if any(bool(metrics[key]) for key in FINDING_KEYS):
        return "DETECT_LIFECYCLE_DRIFT"
    return "PASS_INVARIANT"


def build_common_metrics(
    spec: CaseSpec,
    outcome: AdapterOutcome,
    *,
    operator_drift_gate: float,
) -> dict[str, Any]:
    drift = maximum_absolute_distance(outcome.direct_operator, outcome.perturbed_operator)
    accepted_drift = maximum_absolute_distance(outcome.direct_accepted, outcome.perturbed_accepted)
    operator_drift_detected = drift > operator_drift_gate
    finding = {
        "operator_replay_drift_detected": operator_drift_detected,
        "committed_state_mutated_before_accept": outcome.committed_state_mutated_before_accept,
        "accepted_output_provenance_violation": outcome.accepted_output_provenance_violation,
        "operator_version_incompatibility": outcome.operator_version_incompatibility,
    }
    ranked = [
        f"{spec.ground_truth_owner}|{spec.ground_truth_module}|{spec.ground_truth_event}|{spec.ground_truth_field}|{spec.ground_truth_source_plane}",
        f"OperatorPacket|{spec.ground_truth_module}|FormResidual|declared_replay_pair|operator_metadata",
        f"AcceptedOutput|{spec.ground_truth_module}|OutputAcceptedState|source_candidate|accepted_current_state",
    ]
    return {
        "finite": outcome.finite,
        "converged": outcome.converged,
        "accuracy_gate_pass": outcome.accuracy_error <= 1.0e-5,
        "balance_gate_pass": outcome.balance_error <= 1.0e-10,
        "accuracy_error": outcome.accuracy_error,
        "balance_error": outcome.balance_error,
        "checkpoint_applicable": outcome.checkpoint_applicable,
        "checkpoint_parity": outcome.checkpoint_parity,
        "checkpoint_stage": outcome.checkpoint_stage,
        "checkpoint_field": outcome.checkpoint_field,
        "operator_replay_drift": drift,
        "accepted_field_drift": accepted_drift,
        "operator_drift_gate": operator_drift_gate,
        "operator_replay_drift_detected": operator_drift_detected,
        "operator_versions_compatible": outcome.operator_versions_compatible,
        "state_owner_class": spec.ground_truth_owner,
        "ranked_suspects": ranked,
        "committed_state_mutated_before_accept": outcome.committed_state_mutated_before_accept,
        "accepted_output_provenance_violation": outcome.accepted_output_provenance_violation,
        "operator_version_incompatibility": outcome.operator_version_incompatibility,
        "rejected_candidate_unreachable": outcome.rejected_candidate_unreachable,
        "all_outputs_after_commit": outcome.all_outputs_after_commit,
        "owner_field_observed": outcome.owner_field_observed,
        "activation_event_observed": outcome.activation_event_observed,
        "restoration_failure_observed": outcome.restoration_failure_observed,
        "output_reachability_observed": outcome.output_reachability_observed,
        "first_drift_after_mutation": outcome.first_drift_after_mutation,
        "all_finding_fields_present": all(key in finding for key in FINDING_KEYS),
    }


def evaluate_baselines(spec: CaseSpec, metrics: dict[str, Any]) -> list[dict[str, Any]]:
    b1_detect = not all(
        bool(metrics[key])
        for key in ("finite", "converged", "accuracy_gate_pass", "balance_gate_pass")
    )
    if metrics["checkpoint_applicable"]:
        b2_signal = _signal(not metrics["checkpoint_parity"])
    else:
        b2_signal = "NOT_SUPPORTED"
    if not spec.applicable:
        b3_signal = "NOT_SUPPORTED"
        b5_signal = "NOT_SUPPORTED"
        b6_signal = "NOT_SUPPORTED"
    elif not spec.eligible:
        b3_signal = "INVALID"
        b5_signal = "INVALID"
        b6_signal = "INVALID"
    else:
        b3_signal = _signal(metrics["operator_replay_drift_detected"])
        b5_signal = _signal(metrics["operator_replay_drift_detected"])
        b6_signal = _signal(any(bool(metrics[key]) for key in FINDING_KEYS))
    return [
        {"baseline_id": "B1", "signal": _signal(b1_detect), "detected": b1_detect, "localization": []},
        {"baseline_id": "B2", "signal": b2_signal, "detected": b2_signal == "DETECT", "localization": [] if b2_signal != "DETECT" else [metrics["checkpoint_stage"], metrics["checkpoint_field"]]},
        {"baseline_id": "B3", "signal": b3_signal, "detected": b3_signal == "DETECT", "localization": ["declared_replay_pair"] if b3_signal == "DETECT" else []},
        {"baseline_id": "B4", "signal": _signal(not metrics["operator_versions_compatible"]), "detected": not metrics["operator_versions_compatible"], "localization": ["operator_packet"] if not metrics["operator_versions_compatible"] else []},
        {"baseline_id": "B5", "signal": b5_signal, "detected": b5_signal == "DETECT", "localization": [spec.ground_truth_owner] if b5_signal == "DETECT" else []},
        {"baseline_id": "B6", "signal": b6_signal, "detected": b6_signal == "DETECT", "localization": metrics["ranked_suspects"] if b6_signal == "DETECT" else []},
    ]


def semantic_case_result(result: dict[str, Any]) -> dict[str, Any]:
    payload = dict(result)
    payload.pop("run_id", None)
    payload.pop("runtime", None)
    return payload

