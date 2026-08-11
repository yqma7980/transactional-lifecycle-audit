from __future__ import annotations

from dataclasses import replace
from typing import Any

from benchmarks.L4_two_phase_displacement.src.l4_fv import (
    accept_candidate,
    make_candidate,
    make_snapshot,
)
from benchmarks.L4_two_phase_displacement.src.l4_state import (
    CommittedState,
    TwoPhaseModel,
    canonical_hash,
    initial_state,
)

from .adapter_contract import AdapterOutcome
from .common import CaseSpec, finite, standard_event


CELL_COUNT = 32
REJECTED_DT = 0.01
REPLAY_DT = 0.005


def _accepted_vector(model: TwoPhaseModel, state: CommittedState) -> tuple[float, ...]:
    snapshot = make_snapshot(model, state)
    return (
        *snapshot.saturation_n,
        *snapshot.pressure,
        snapshot.displacement,
        snapshot.phase_mass_n,
        snapshot.phase_mass_w,
        snapshot.front_location,
    )


def _operator_vector(candidate, *, residual_bias: float = 0.0) -> tuple[float, ...]:
    # The finite-volume flux balance is the subject's declared operator packet.
    return (
        candidate.flux_n_in + residual_bias,
        candidate.flux_n_out,
        candidate.flux_w_in,
        candidate.flux_w_out,
        candidate.declared_n_mass_defect + residual_bias,
        candidate.declared_w_mass_defect,
    )


def _mutated_committed(committed: CommittedState, rejected, eta: float) -> CommittedState:
    saturation = list(committed.saturation_n)
    saturation[0] += eta * (rejected.saturation_n[0] - saturation[0])
    return replace(committed, saturation_n=tuple(saturation))


def execute(spec: CaseSpec, run_id: str) -> AdapterOutcome:
    if spec.subject_id != "JSS-S02":
        raise ValueError("S02 adapter received a different subject")
    model = TwoPhaseModel()
    direct_committed = initial_state(CELL_COUNT)
    perturbed_committed = initial_state(CELL_COUNT)
    committed_before_hash = perturbed_committed.fingerprint
    persistent_before = canonical_hash({"feedback": 0.0, "callback_bias": 0.0})

    direct_candidate = make_candidate(
        model, direct_committed, REPLAY_DT, attempt_id=f"{run_id}-DIRECT"
    )
    rejected = make_candidate(
        model, perturbed_committed, REJECTED_DT, attempt_id=f"{run_id}-REJECTED"
    )

    feedback = 0.0
    callback_bias = 0.0
    committed_mutated = False
    output_violation = False
    version_mismatch = False
    versions_compatible = True
    mutation_event = "Rollback"
    mutation_owner = "CommittedState"
    mutation_field = "none"

    if spec.fault_id == "F03":
        perturbed_committed = _mutated_committed(
            perturbed_committed, rejected, spec.strength
        )
        committed_mutated = perturbed_committed.fingerprint != committed_before_hash
        mutation_event = "TrialEvaluate"
        mutation_field = "saturation_n[0]"
    elif spec.fault_id == "F05":
        feedback = spec.strength * rejected.declared_n_mass_defect
        # A zero conservative defect would make this seeded control degenerate;
        # the rejected pressure observable supplies the frozen nonzero source.
        if feedback == 0.0:
            feedback = spec.strength * make_snapshot(
                model,
                replace(
                    perturbed_committed,
                    time=rejected.time,
                    saturation_n=rejected.saturation_n,
                ),
            ).pressure[0]
        output_violation = True
        mutation_event = "OutputAcceptedState"
        mutation_owner = "AcceptedOutputMirror"
        mutation_field = "pressure_feedback"
    elif spec.fault_id == "F07":
        callback_bias = spec.strength
        mutation_event = "FormResidual"
        mutation_owner = "CallbackState"
        mutation_field = "flux_bias"
    elif spec.fault_id == "F08":
        versions_compatible = False
        version_mismatch = True
        mutation_event = "FormTangent"
        mutation_owner = "OperatorPacket"
        mutation_field = "tangent_state_version"
    elif spec.fault_id != "BENIGN-01":
        raise ValueError(f"unsupported S02 fault {spec.fault_id}")

    perturbed_candidate = make_candidate(
        model,
        perturbed_committed,
        REPLAY_DT,
        attempt_id=f"{run_id}-REPLAY",
    )
    direct_accepted_state = accept_candidate(direct_committed, direct_candidate)
    perturbed_accepted_state = accept_candidate(
        perturbed_committed, perturbed_candidate
    )
    direct_accepted = _accepted_vector(model, direct_accepted_state)
    perturbed_accepted = _accepted_vector(model, perturbed_accepted_state)
    direct_operator = _operator_vector(direct_candidate)
    perturbed_operator = _operator_vector(
        perturbed_candidate, residual_bias=feedback + callback_bias
    )
    persistent_after = canonical_hash(
        {"feedback": feedback, "callback_bias": callback_bias}
    )

    balance = max(
        abs(direct_candidate.declared_n_mass_defect),
        abs(direct_candidate.declared_w_mass_defect),
        abs(perturbed_candidate.internal_n_mass_defect),
        abs(perturbed_candidate.internal_w_mass_defect),
    )
    accuracy = max(
        (abs(a - b) for a, b in zip(direct_accepted, perturbed_accepted)),
        default=0.0,
    )
    events = (
        standard_event(1, "BeginAttempt", owner="Host", field_name="direct"),
        standard_event(
            2,
            "TrialEvaluate",
            candidate_id=direct_candidate.fingerprint,
            before_hash=direct_committed.fingerprint,
            after_hash=direct_committed.fingerprint,
            residual_version="L4-FV-R1",
            tangent_version="L4-FV-K1",
        ),
        standard_event(3, "RejectAttempt", candidate_id=rejected.fingerprint),
        standard_event(
            4,
            mutation_event,
            candidate_id=rejected.fingerprint,
            owner=mutation_owner,
            field_name=mutation_field,
            before_hash=committed_before_hash,
            after_hash=perturbed_committed.fingerprint,
            source_plane="rejected_trial",
        ),
        standard_event(
            5,
            "Rollback",
            candidate_id=rejected.fingerprint,
            before_hash=perturbed_committed.fingerprint,
            after_hash=perturbed_committed.fingerprint,
        ),
        standard_event(
            6,
            "FormResidual",
            candidate_id=perturbed_candidate.fingerprint,
            residual_version="L4-FV-R1",
            tangent_version=("STALE" if version_mismatch else "L4-FV-K1"),
        ),
        standard_event(
            7,
            "AcceptCommit",
            accepted=True,
            candidate_id=perturbed_candidate.fingerprint,
            after_hash=perturbed_accepted_state.fingerprint,
        ),
        standard_event(
            8,
            "OutputAcceptedState",
            accepted=True,
            candidate_id=(
                rejected.fingerprint if output_violation else perturbed_candidate.fingerprint
            ),
            source_plane=("rejected_trial" if output_violation else "accepted_current_state"),
        ),
    )
    if version_mismatch:
        # Version-incompatible packets are rejected before correction, commit, or output.
        events = events[:6] + (
            standard_event(
                7,
                "RejectAttempt",
                candidate_id=perturbed_candidate.fingerprint,
                owner="OperatorPacket",
                field_name="tangent_state_version",
                source_plane="pre_correction_version_guard",
                residual_version="L4-FV-R1",
                tangent_version="STALE",
            ),
        )
    return AdapterOutcome(
        subject_id=spec.subject_id,
        case_id=spec.case_id,
        run_id=run_id,
        direct_operator=direct_operator,
        perturbed_operator=perturbed_operator,
        direct_accepted=direct_accepted,
        perturbed_accepted=perturbed_accepted,
        direct_hash=direct_accepted_state.fingerprint,
        perturbed_hash=perturbed_accepted_state.fingerprint,
        committed_before_hash=committed_before_hash,
        committed_after_trial_hash=perturbed_committed.fingerprint,
        persistent_before_hash=persistent_before,
        persistent_after_hash=persistent_after,
        finite=finite((*direct_operator, *perturbed_operator, *direct_accepted, *perturbed_accepted)),
        converged=True,
        accuracy_error=accuracy,
        balance_error=balance,
        checkpoint_applicable=True,
        checkpoint_parity=not committed_mutated,
        checkpoint_stage="pre_accept_committed_state",
        checkpoint_field="saturation_n[0]",
        operator_versions_compatible=versions_compatible,
        committed_state_mutated_before_accept=committed_mutated,
        accepted_output_provenance_violation=output_violation,
        operator_version_incompatibility=version_mismatch,
        rejected_candidate_unreachable=not output_violation,
        all_outputs_after_commit=not output_violation,
        owner_field_observed=spec.fault_id != "BENIGN-01",
        activation_event_observed=spec.fault_id != "BENIGN-01",
        restoration_failure_observed=committed_mutated,
        output_reachability_observed=output_violation,
        first_drift_after_mutation=spec.fault_id in {"F03", "F05", "F07"},
        events=events,
        diagnostics={
            "model_fingerprint": model.fingerprint,
            "cell_count": CELL_COUNT,
            "rejected_candidate": rejected.fingerprint,
            "direct_candidate": direct_candidate.fingerprint,
            "perturbed_candidate": perturbed_candidate.fingerprint,
            "feedback": feedback,
            "callback_bias": callback_bias,
        },
    )


def execute_safe_null(run_id: str) -> dict[str, Any]:
    model = TwoPhaseModel()
    left = initial_state(CELL_COUNT)
    right = initial_state(CELL_COUNT)
    a = make_candidate(model, left, REPLAY_DT, attempt_id=f"{run_id}-A")
    rejected = make_candidate(model, right, REJECTED_DT, attempt_id=f"{run_id}-X")
    b = make_candidate(model, right, REPLAY_DT, attempt_id=f"{run_id}-B")
    av = _operator_vector(a)
    bv = _operator_vector(b)
    return {
        "subject_id": "JSS-S02",
        "run_id": run_id,
        "operator_drift": max(abs(x - y) for x, y in zip(av, bv)),
        "structural_parity": (
            left.fingerprint == right.fingerprint
            and a.saturation_n == b.saturation_n
            and rejected.attempt_id.endswith("-X")
        ),
        "finite": finite((*av, *bv)),
        "direct_operator": av,
        "retry_operator": bv,
    }
