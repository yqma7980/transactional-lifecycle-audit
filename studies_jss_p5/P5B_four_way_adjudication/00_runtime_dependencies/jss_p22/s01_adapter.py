from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from p4d_state import CommittedState, initial_committed_state
from p5_fe_adapter import P5PersistentState
from p5_quadrature_backend_erratum_v2 import P5QuadratureAwareFEHost

from .adapter_contract import AdapterOutcome
from .common import CaseSpec, canonical_hash, finite, standard_event


@dataclass
class _Path:
    committed_before: str
    committed_after_trial: str
    persistent_before: str
    persistent_after: str
    operator: tuple[float, ...]
    accepted: tuple[float, ...]
    accepted_hash: str
    failed_candidate: str
    replay_candidate: str
    finite: bool
    converged: bool
    accuracy: float
    balance: float
    host_events: tuple[dict[str, Any], ...]


def _accepted_vector(state: CommittedState) -> tuple[float, ...]:
    return (
        *state.primary.tolist(),
        *state.gamma_p.ravel().tolist(),
        *state.alpha.ravel().tolist(),
        state.accepted_load,
        float(state.accepted_version),
    )


def _operator_vector(packet) -> tuple[float, ...]:
    return (
        *packet.tau.ravel().tolist(),
        *packet.tangent.ravel().tolist(),
    )


def _run_path(run_id: str, *, eta: float) -> _Path:
    persistent = P5PersistentState()
    host = P5QuadratureAwareFEHost(
        initial_committed_state(), persistent, run_id=run_id
    )
    persistent_before = persistent.projection_hash
    replay = None
    failed = None
    try:
        for ordinal, target in enumerate((0.04, 0.08), start=1):
            host.begin_attempt(target, f"{run_id}-A{ordinal}", "EXACT_CURRENT", maximum_iterations=25)
            attempt = host.solve_attempt()
            if not attempt.converged or not attempt.metrics.pass_flag:
                raise RuntimeError("S01 prerequisite increment failed")
            host.commit(attempt)

        committed_before = host.committed.full_hash
        host.begin_attempt(0.20, f"{run_id}-REJECTED", "EXACT_CURRENT", maximum_iterations=1)
        failed = host.solve_attempt()
        if failed.converged:
            raise RuntimeError("S01 forced rejected attempt unexpectedly converged")

        if eta:
            gamma_p = host.committed.gamma_p.copy()
            gamma_p[0, 0, 0] += eta * (
                failed.selected_packet.gamma_p_candidate[0, 0, 0]
                - gamma_p[0, 0, 0]
            )
            host.committed = CommittedState(
                primary=host.committed.primary,
                gamma_p=gamma_p,
                alpha=host.committed.alpha,
                accepted_index=host.committed.accepted_index,
                accepted_load=host.committed.accepted_load,
                accepted_version=host.committed.accepted_version,
            )
        committed_after_trial = host.committed.full_hash
        host.restore_after_failed_attempt(failed)

        host.begin_attempt(0.10, f"{run_id}-REPLAY", "EXACT_CURRENT", maximum_iterations=25)
        replay = host.solve_attempt()
        if not replay.converged or not replay.metrics.pass_flag:
            raise RuntimeError("S01 replay increment failed")
        packet = replay.selected_packet
        host.commit(replay)
        accepted = _accepted_vector(host.committed)
        operator = _operator_vector(packet)
        return _Path(
            committed_before=committed_before,
            committed_after_trial=committed_after_trial,
            persistent_before=persistent_before,
            persistent_after=persistent.projection_hash,
            operator=operator,
            accepted=accepted,
            accepted_hash=host.committed.full_hash,
            failed_candidate=failed.selected_packet.candidate_id,
            replay_candidate=packet.candidate_id,
            finite=finite((*operator, *accepted)),
            converged=True,
            accuracy=max(
                replay.metrics.free_residual_relative,
                replay.metrics.yield_consistency_relative,
            ),
            balance=replay.metrics.reaction_balance_relative,
            host_events=tuple(host.events.records),
        )
    finally:
        host.close()


def execute(spec: CaseSpec, run_id: str) -> AdapterOutcome:
    if spec.subject_id != "JSS-S01" or spec.fault_id != "F03":
        raise ValueError("S01 adapter supports only frozen F03 cases")
    direct = _run_path(f"{run_id}-DIRECT", eta=0.0)
    perturbed = _run_path(f"{run_id}-PERTURBED", eta=spec.strength)
    committed_mutated = (
        perturbed.committed_before != perturbed.committed_after_trial
    )
    accepted_drift = max(
        abs(a - b) for a, b in zip(direct.accepted, perturbed.accepted)
    )
    events = (
        standard_event(1, "BeginAttempt", owner="DOLFINxPETSc", field_name="direct"),
        standard_event(
            2,
            "TrialEvaluate",
            candidate_id=perturbed.failed_candidate,
            owner="CommittedState",
            field_name="gamma_p[0,0,0]",
            before_hash=perturbed.committed_before,
            after_hash=perturbed.committed_after_trial,
            source_plane="failed_trial_before_accept",
            residual_version="P4D-R-1.0",
            tangent_version="P4D-J-1.0",
        ),
        standard_event(3, "RejectAttempt", candidate_id=perturbed.failed_candidate),
        standard_event(
            4,
            "Rollback",
            candidate_id=perturbed.failed_candidate,
            before_hash=perturbed.committed_after_trial,
            after_hash=perturbed.committed_after_trial,
        ),
        standard_event(
            5,
            "FormResidual",
            candidate_id=perturbed.replay_candidate,
            residual_version="P4D-R-1.0",
            tangent_version="P4D-J-1.0",
        ),
        standard_event(
            6,
            "AcceptCommit",
            accepted=True,
            candidate_id=perturbed.replay_candidate,
            after_hash=perturbed.accepted_hash,
        ),
        standard_event(
            7,
            "OutputAcceptedState",
            accepted=True,
            candidate_id=perturbed.replay_candidate,
            source_plane="accepted_current_state",
        ),
    )
    return AdapterOutcome(
        subject_id=spec.subject_id,
        case_id=spec.case_id,
        run_id=run_id,
        direct_operator=direct.operator,
        perturbed_operator=perturbed.operator,
        direct_accepted=direct.accepted,
        perturbed_accepted=perturbed.accepted,
        direct_hash=direct.accepted_hash,
        perturbed_hash=perturbed.accepted_hash,
        committed_before_hash=perturbed.committed_before,
        committed_after_trial_hash=perturbed.committed_after_trial,
        persistent_before_hash=perturbed.persistent_before,
        persistent_after_hash=perturbed.persistent_after,
        finite=direct.finite and perturbed.finite,
        converged=direct.converged and perturbed.converged,
        accuracy_error=max(direct.accuracy, perturbed.accuracy, accepted_drift),
        balance_error=max(direct.balance, perturbed.balance),
        checkpoint_applicable=True,
        checkpoint_parity=not committed_mutated,
        checkpoint_stage="pre_accept_committed_state",
        checkpoint_field="gamma_p[0,0,0]",
        operator_versions_compatible=True,
        committed_state_mutated_before_accept=committed_mutated,
        accepted_output_provenance_violation=False,
        operator_version_incompatibility=False,
        rejected_candidate_unreachable=True,
        all_outputs_after_commit=True,
        owner_field_observed=True,
        activation_event_observed=True,
        restoration_failure_observed=committed_mutated,
        output_reachability_observed=False,
        first_drift_after_mutation=True,
        events=events,
        diagnostics={
            "direct_host_event_count": len(direct.host_events),
            "perturbed_host_event_count": len(perturbed.host_events),
            "accepted_field_drift": accepted_drift,
            "direct_replay_candidate": direct.replay_candidate,
            "perturbed_replay_candidate": perturbed.replay_candidate,
        },
    )


def execute_safe_null(run_id: str) -> dict[str, Any]:
    left = _run_path(f"{run_id}-LEFT", eta=0.0)
    right = _run_path(f"{run_id}-RIGHT", eta=0.0)
    drift = max(
        max(abs(a - b) for a, b in zip(left.operator, right.operator)),
        max(abs(a - b) for a, b in zip(left.accepted, right.accepted)),
    )
    return {
        "subject_id": "JSS-S01",
        "run_id": run_id,
        "operator_drift": drift,
        "structural_parity": (
            left.accepted_hash == right.accepted_hash
            and left.committed_before == right.committed_before
            and left.failed_candidate == right.failed_candidate
        ),
        "finite": left.finite and right.finite,
        "direct_operator_hash": canonical_hash(left.operator),
        "retry_operator_hash": canonical_hash(right.operator),
    }
