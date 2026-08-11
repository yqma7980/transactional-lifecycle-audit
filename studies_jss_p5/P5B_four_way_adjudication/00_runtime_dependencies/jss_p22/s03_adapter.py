from __future__ import annotations

from typing import Any

from benchmarks.L6_external_host.src.l6_scipy_adapter import ScipyLifecycleAdapter
from benchmarks.L6_external_host.src.l6_state import CommittedState, canonical_hash

from .adapter_contract import AdapterOutcome
from .common import CaseSpec, finite, standard_event


def _safe_execution(path_id: str):
    return ScipyLifecycleAdapter(
        path_id=path_id, variant="safe_transactional"
    ).run(jacobian_mode="analytic")


def _replay_packet(execution) -> tuple[float, float, float, str]:
    candidates = execution.nonaccepted_residual_events
    if not candidates:
        raise RuntimeError("frozen SciPy history produced no host-nonaccepted residual")
    # The frozen oracle packet is the first host-nonaccepted trial at x=1.
    row = next(
        (item for item in candidates if item.get("x_hex") == "0x1.0000000000000p+0"),
        None,
    )
    if row is None:
        raise RuntimeError("frozen SciPy history lacks the x=1 nonaccepted packet")
    x = float(row["x"])
    residual = float(row["residual"])
    tangent = 3.0 * x * x - 2.0
    return x, residual, tangent, str(row["event_id"])


def _accepted(execution) -> tuple[float, ...]:
    return (execution.final_x, execution.final_residual, execution.final_cost)


def execute(spec: CaseSpec, run_id: str) -> AdapterOutcome:
    if spec.subject_id != "JSS-S03":
        raise ValueError("S03 adapter received a different subject")
    direct = _safe_execution(f"{run_id}-DIRECT")
    perturbed = _safe_execution(f"{run_id}-PERTURBED")
    dx, dr, dk, direct_event = _replay_packet(direct)
    px, pr, pk, perturbed_event = _replay_packet(perturbed)

    committed_before = perturbed.committed_before
    committed_after_trial = committed_before
    persistent_before = canonical_hash({"feedback": 0.0, "callback_bias": 0.0})
    persistent_after = persistent_before
    output_violation = False
    version_mismatch = False
    committed_mutated = False
    residual_bias = 0.0
    tangent_bias = 0.0
    mutation_event = "Rollback"
    mutation_owner = "CommittedState"
    mutation_field = "none"

    if spec.fault_id == "F03":
        committed_after_trial = CommittedState(
            history=spec.strength * px,
            accepted_version=committed_before.accepted_version,
        )
        committed_mutated = committed_after_trial.fingerprint != committed_before.fingerprint
        residual_bias = committed_after_trial.history
        mutation_event = "TrialEvaluate"
        mutation_field = "history"
    elif spec.fault_id == "F05":
        residual_bias = spec.strength * pr
        output_violation = True
        persistent_after = canonical_hash({"feedback": residual_bias, "callback_bias": 0.0})
        mutation_event = "OutputAcceptedState"
        mutation_owner = "AcceptedOutputMirror"
        mutation_field = "residual_feedback"
    elif spec.fault_id == "F07":
        residual_bias = spec.strength * len(perturbed.nonaccepted_residual_events)
        persistent_after = canonical_hash({"feedback": 0.0, "callback_bias": residual_bias})
        mutation_event = "FormResidual"
        mutation_owner = "CallbackState"
        mutation_field = "callback_count_bias"
    else:
        raise ValueError(f"unsupported S03 fault {spec.fault_id}")

    direct_operator = (dr, dk)
    perturbed_operator = (pr + residual_bias, pk + tangent_bias)
    direct_accepted = _accepted(direct)
    perturbed_accepted = _accepted(perturbed)
    accuracy = max(abs(a - b) for a, b in zip(direct_accepted, perturbed_accepted))

    events = (
        standard_event(1, "BeginAttempt", owner="SciPyTRF", field_name="direct"),
        standard_event(
            2,
            "TrialEvaluate",
            candidate_id=direct_event,
            before_hash=direct.committed_before.fingerprint,
            after_hash=direct.committed_before.fingerprint,
            residual_version="L6-RJ-D1.0",
            tangent_version="L6-RJ-D1.0",
        ),
        standard_event(3, "RejectAttempt", candidate_id=perturbed_event),
        standard_event(
            4,
            mutation_event,
            candidate_id=perturbed_event,
            owner=mutation_owner,
            field_name=mutation_field,
            before_hash=committed_before.fingerprint,
            after_hash=committed_after_trial.fingerprint,
            source_plane="host_nonaccepted_residual",
        ),
        standard_event(
            5,
            "FormResidual",
            candidate_id=perturbed_event,
            residual_version="L6-RJ-D1.0",
            tangent_version="L6-RJ-D1.0",
        ),
        standard_event(
            6,
            "AcceptCommit",
            accepted=True,
            candidate_id=(perturbed.outputs[0].source_event_id if perturbed.outputs else None),
            after_hash=(perturbed.committed_after.fingerprint if perturbed.committed_after else None),
        ),
        standard_event(
            7,
            "OutputAcceptedState",
            accepted=True,
            candidate_id=(perturbed_event if output_violation else perturbed.outputs[0].source_event_id),
            source_plane=("host_nonaccepted_residual" if output_violation else "accepted_current_state"),
        ),
    )
    all_values = (*direct_operator, *perturbed_operator, *direct_accepted, *perturbed_accepted)
    return AdapterOutcome(
        subject_id=spec.subject_id,
        case_id=spec.case_id,
        run_id=run_id,
        direct_operator=direct_operator,
        perturbed_operator=perturbed_operator,
        direct_accepted=direct_accepted,
        perturbed_accepted=perturbed_accepted,
        direct_hash=direct.committed_after.fingerprint,
        perturbed_hash=perturbed.committed_after.fingerprint,
        committed_before_hash=committed_before.fingerprint,
        committed_after_trial_hash=committed_after_trial.fingerprint,
        persistent_before_hash=persistent_before,
        persistent_after_hash=persistent_after,
        finite=direct.all_values_finite and perturbed.all_values_finite and finite(all_values),
        converged=direct.success and perturbed.success,
        accuracy_error=accuracy,
        # This scalar optimization host has no conservation-balance quantity.
        balance_error=0.0,
        checkpoint_applicable=False,
        checkpoint_parity=True,
        checkpoint_stage="NOT_SUPPORTED",
        checkpoint_field="NOT_SUPPORTED",
        operator_versions_compatible=not version_mismatch,
        committed_state_mutated_before_accept=committed_mutated,
        accepted_output_provenance_violation=output_violation,
        operator_version_incompatibility=version_mismatch,
        rejected_candidate_unreachable=not output_violation,
        all_outputs_after_commit=not output_violation,
        owner_field_observed=True,
        activation_event_observed=True,
        restoration_failure_observed=committed_mutated,
        output_reachability_observed=output_violation,
        first_drift_after_mutation=True,
        events=events,
        diagnostics={
            "direct_nfev": direct.nfev,
            "perturbed_nfev": perturbed.nfev,
            "direct_nonaccepted_count": len(direct.nonaccepted_residual_events),
            "perturbed_nonaccepted_count": len(perturbed.nonaccepted_residual_events),
            "replay_x_hex": px.hex(),
            "residual_bias": residual_bias,
        },
    )


def execute_safe_null(run_id: str) -> dict[str, Any]:
    left = _safe_execution(f"{run_id}-LEFT")
    right = _safe_execution(f"{run_id}-RIGHT")
    lx, lr, lk, _ = _replay_packet(left)
    rx, rr, rk, _ = _replay_packet(right)
    drift = max(abs(lr - rr), abs(lk - rk), abs(lx - rx))
    return {
        "subject_id": "JSS-S03",
        "run_id": run_id,
        "operator_drift": drift,
        "structural_parity": (
            left.committed_before.fingerprint == right.committed_before.fingerprint
            and left.committed_after.fingerprint == right.committed_after.fingerprint
            and len(left.nonaccepted_residual_events) == len(right.nonaccepted_residual_events)
        ),
        "finite": left.all_values_finite and right.all_values_finite,
        "direct_operator": (lr, lk),
        "retry_operator": (rr, rk),
    }
