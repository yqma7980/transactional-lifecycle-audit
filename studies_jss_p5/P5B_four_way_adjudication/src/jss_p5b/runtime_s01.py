from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import sys
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
P4D_SRC = ROOT / "00_runtime_dependencies" / "P22_frozen_inputs" / "P4d_subject_src"
P5_SRC = ROOT / "00_runtime_dependencies" / "P22_frozen_inputs" / "P5_subject_src"
for _path in (P5_SRC, P4D_SRC, ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from p4d_canonical import canonical_hash
from p4d_state import CommittedState, initial_committed_state
from p5_fe_adapter import P5PersistentState
from p5_quadrature_backend_erratum_v2 import P5QuadratureAwareFEHost

from .cases import CaseSpec
from .model import PrecomparisonRelation
from .runtime import (
    RuntimeRecord,
    max_abs_delta,
    raw_observation,
    replay_packet,
    runtime_environment,
)


ETA_LOW = 1.0e-10
ACTIVE_INDEX = (27, 0, 1)
ACTIVE_REFERENCE_DELTA = float.fromhex("0x1.434e28dc72c89p-3")


def _clone_committed(state: CommittedState) -> CommittedState:
    return CommittedState(
        primary=state.primary.copy(),
        gamma_p=state.gamma_p.copy(),
        alpha=state.alpha.copy(),
        accepted_index=state.accepted_index,
        accepted_load=state.accepted_load,
        accepted_version=state.accepted_version,
    )


def _clone_persistent(state: P5PersistentState) -> P5PersistentState:
    return P5PersistentState(
        hidden_trial_cache=state.hidden_trial_cache.copy(),
        declared_alpha_cache=state.declared_alpha_cache.copy(),
        feedback_mirror_E=float(state.feedback_mirror_E),
        feedback_mirror_J=float(state.feedback_mirror_J),
        callback_bias_F=float(state.callback_bias_F),
        mutation_count=int(state.mutation_count),
        rejected_source_candidate_id=state.rejected_source_candidate_id,
    )


def _accept(host: P5QuadratureAwareFEHost, target: float, label: str):
    host.begin_attempt(target, label, "EXACT_CURRENT", maximum_iterations=25)
    attempt = host.solve_attempt()
    if not attempt.converged:
        raise RuntimeError(f"S01 accepted increment did not converge: {label}")
    if not attempt.metrics.pass_flag:
        raise RuntimeError(f"S01 mechanics gate failed: {label}")
    host.commit(attempt)
    host.events.append(
        "OutputAcceptedState",
        solve_id=host.run_id,
        attempt_id=attempt.attempt_id,
        candidate_id=attempt.selected_packet.candidate_id,
        committed_state_hash=host.committed.full_hash,
        accepted_version=host.committed.accepted_version,
        reachable_from_accepted_output=True,
    )
    return attempt


def _s01_packet(*, declared_state: CommittedState, persistent_hash: str):
    return replay_packet(
        primary={"primary_hash": canonical_hash(declared_state.primary)},
        committed={"full_hash": declared_state.full_hash},
        persistent={"projection_hash": persistent_hash},
        load={"source": 0.08, "target": 0.10},
        residual_version="P4D-R1",
        tangent_version="P4D-K1",
        environment={"subject": "JSS-S01", "host": "DOLFINx-PETSc-P5"},
    )


def _checkpoint_control(run_id: str) -> tuple[Any, ...]:
    direct = P5QuadratureAwareFEHost(
        initial_committed_state(), P5PersistentState(), run_id=f"{run_id}-DIRECT"
    )
    restart_before = P5QuadratureAwareFEHost(
        initial_committed_state(), P5PersistentState(), run_id=f"{run_id}-CHECKPOINT"
    )
    restart_after = None
    try:
        _accept(direct, 0.04, "DIRECT-A01")
        _accept(direct, 0.08, "DIRECT-A02")
        direct_declared = _clone_committed(direct.committed)
        direct_persistent = direct.persistent.projection_hash
        direct_final_attempt = _accept(direct, 0.10, "DIRECT-A03")

        _accept(restart_before, 0.04, "RESTART-A01")
        _accept(restart_before, 0.08, "RESTART-A02")
        checkpoint_state = _clone_committed(restart_before.committed)
        checkpoint_persistent = _clone_persistent(restart_before.persistent)
        checkpoint_hash = checkpoint_state.full_hash
        checkpoint_persistent_hash = checkpoint_persistent.projection_hash
        restart_before.events.append(
            "CheckpointWrite",
            solve_id=restart_before.run_id,
            committed_state_hash=checkpoint_hash,
            persistent_projection_hash=checkpoint_persistent_hash,
            reachable_from_accepted_output=True,
        )
        before_events = restart_before.events.records
        restart_before.close()

        restart_after = P5QuadratureAwareFEHost(
            _clone_committed(checkpoint_state),
            _clone_persistent(checkpoint_persistent),
            run_id=f"{run_id}-RESTORED",
        )
        restart_after.events.append(
            "CheckpointRead",
            solve_id=restart_after.run_id,
            committed_state_hash=restart_after.committed.full_hash,
            persistent_projection_hash=restart_after.persistent.projection_hash,
            reachable_from_accepted_output=True,
        )
        restart_final_attempt = _accept(restart_after, 0.10, "RESTORED-A03")

        if checkpoint_hash != direct_declared.full_hash:
            raise RuntimeError("checkpoint control did not share the declared replay state")
        if checkpoint_persistent_hash != direct_persistent:
            raise RuntimeError("checkpoint control persistent projection drifted")
        if direct.committed.full_hash != restart_after.committed.full_hash:
            raise RuntimeError("checkpoint/restart continuation lost final-state parity")

        accepted_delta = max(
            float(np.max(np.abs(direct.committed.primary - restart_after.committed.primary))),
            float(np.max(np.abs(direct.committed.gamma_p - restart_after.committed.gamma_p))),
            float(np.max(np.abs(direct.committed.alpha - restart_after.committed.alpha))),
        )
        events = tuple(direct.events.records + before_events + restart_after.events.records)
        return (
            direct_declared,
            checkpoint_state,
            direct_persistent,
            checkpoint_persistent_hash,
            direct.committed,
            restart_after.committed,
            direct_final_attempt,
            restart_final_attempt,
            accepted_delta,
            events,
        )
    finally:
        direct.close()
        restart_before.close()
        if restart_after is not None:
            restart_after.close()


def _forced_retry_history(run_id: str, *, faulty: bool) -> dict[str, Any]:
    role = "FAULT" if faulty else "SAFE"
    host = P5QuadratureAwareFEHost(
        initial_committed_state(), P5PersistentState(), run_id=f"{run_id}-{role}"
    )
    try:
        _accept(host, 0.04, f"{role}-A01")
        _accept(host, 0.08, f"{role}-A02")
        declared = _clone_committed(host.committed)
        persistent_declared = host.persistent.projection_hash

        host.begin_attempt(0.20, f"{role}-FAILED-020", "EXACT_CURRENT", maximum_iterations=1)
        failed = host.solve_attempt()
        if failed.converged:
            raise RuntimeError("frozen forced-retry trigger unexpectedly converged")
        committed_before_fault = host.committed.full_hash
        physical_delta = 0.0
        if faulty:
            gamma_p = host.committed.gamma_p.copy()
            candidate_delta = (
                float(failed.selected_packet.gamma_p_candidate[ACTIVE_INDEX])
                - float(gamma_p[ACTIVE_INDEX])
            )
            if candidate_delta == 0.0:
                raise RuntimeError("frozen S01 activity binding is inactive")
            if abs(candidate_delta - ACTIVE_REFERENCE_DELTA) > 1.0e-12:
                raise RuntimeError("S01 activity binding drifted from its frozen qualification")
            physical_delta = ETA_LOW * candidate_delta
            gamma_p[ACTIVE_INDEX] += physical_delta
            host.committed = CommittedState(
                primary=host.committed.primary,
                gamma_p=gamma_p,
                alpha=host.committed.alpha,
                accepted_index=host.committed.accepted_index,
                accepted_load=host.committed.accepted_load,
                accepted_version=host.committed.accepted_version,
            )
            host.events.append(
                "SeededPrematureCommitMutation",
                solve_id=host.run_id,
                attempt_id=failed.attempt_id,
                field_name="gamma_p[27,0,1]",
                eta=ETA_LOW,
                physical_delta=physical_delta,
                committed_before_hash=committed_before_fault,
                committed_after_hash=host.committed.full_hash,
                reachable_from_accepted_output=False,
            )
        committed_after_fault = host.committed.full_hash
        host.restore_after_failed_attempt(failed)
        replay = _accept(host, 0.10, f"{role}-REPLAY-010")
        return {
            "declared": declared,
            "persistent_declared": persistent_declared,
            "committed_before_fault": committed_before_fault,
            "committed_after_fault": committed_after_fault,
            "physical_delta": physical_delta,
            "failed_attempt": failed,
            "replay_attempt": replay,
            "final_state": _clone_committed(host.committed),
            "events": tuple(host.events.records),
        }
    finally:
        host.close()


def _s01_environment() -> dict[str, Any]:
    import dolfinx
    import petsc4py

    return runtime_environment(
        "JSS-S01",
        backend={
            "name": "DOLFINx/PETSc path-dependent finite-element host",
            "dolfinx": dolfinx.__version__,
            "petsc4py": petsc4py.__version__,
            "cells": 32,
            "quadrature_points": 96,
        },
    )


def execute_s01_runtime(case: CaseSpec, run_id: str, runtime_mode: str) -> RuntimeRecord:
    environment = _s01_environment()

    if case.case_id == "P5B-PASS-04":
        (
            direct_declared,
            restart_declared,
            direct_persistent,
            restart_persistent,
            direct_final,
            restart_final,
            direct_attempt,
            restart_attempt,
            accepted_delta,
            events,
        ) = _checkpoint_control(run_id)
        packet_a = _s01_packet(
            declared_state=direct_declared, persistent_hash=direct_persistent
        )
        packet_b = _s01_packet(
            declared_state=restart_declared, persistent_hash=restart_persistent
        )
        if accepted_delta != 0.0:
            raise RuntimeError("checkpoint/restart accepted fields are not exactly equal")
        raw = raw_observation(
            packet_a,
            packet_b,
            PrecomparisonRelation.COMPATIBLE,
            evidence_tokens=("ACCEPTED_OUTPUT", "CHECKPOINT_STATE"),
        )
        measurements = {
            "accepted_field_delta": accepted_delta,
            "final_full_hash_equal": direct_final.full_hash == restart_final.full_hash,
            "checkpoint_hash_equal": direct_declared.full_hash == restart_declared.full_hash,
            "direct_mechanics": asdict(direct_attempt.metrics),
            "restart_mechanics": asdict(restart_attempt.metrics),
            "finite": direct_attempt.metrics.all_values_finite
            and restart_attempt.metrics.all_values_finite,
            "converged": direct_attempt.converged and restart_attempt.converged,
        }
    elif case.case_id == "P5B-DETECT-01":
        safe = _forced_retry_history(run_id, faulty=False)
        faulty = _forced_retry_history(run_id, faulty=True)
        if safe["declared"].full_hash != faulty["declared"].full_hash:
            raise RuntimeError("F03 histories do not share the declared replay state")
        if safe["committed_before_fault"] != faulty["committed_before_fault"]:
            raise RuntimeError("F03 histories diverged before the seeded mutation")
        if faulty["committed_before_fault"] == faulty["committed_after_fault"]:
            raise RuntimeError("F03 premature commit did not mutate authoritative state")
        packet_a = _s01_packet(
            declared_state=safe["declared"], persistent_hash=safe["persistent_declared"]
        )
        packet_b = _s01_packet(
            declared_state=faulty["declared"], persistent_hash=faulty["persistent_declared"]
        )
        tau_drift = float(
            np.max(
                np.abs(
                    safe["replay_attempt"].selected_packet.tau
                    - faulty["replay_attempt"].selected_packet.tau
                )
            )
        )
        tangent_drift = float(
            np.max(
                np.abs(
                    safe["replay_attempt"].selected_packet.tangent
                    - faulty["replay_attempt"].selected_packet.tangent
                )
            )
        )
        raw = raw_observation(
            packet_a,
            packet_b,
            PrecomparisonRelation.COMPATIBLE,
            evidence_tokens=("COMMIT_BOUNDARY", "COMMITTED_FINGERPRINT", "REJECT_EVENT"),
            signal_names=("authoritative_state_mutation", "commit_violation"),
        )
        measurements = {
            "seed_strength": ETA_LOW,
            "field_binding": "gamma_p[27,0,1]",
            "physical_delta": faulty["physical_delta"],
            "committed_hash_changed_before_accept": True,
            "tau_replay_drift": tau_drift,
            "tangent_replay_drift": tangent_drift,
            "safe_failed_reason": safe["failed_attempt"].snes_reason,
            "faulty_failed_reason": faulty["failed_attempt"].snes_reason,
            "safe_replay_mechanics": asdict(safe["replay_attempt"].metrics),
            "faulty_replay_mechanics": asdict(faulty["replay_attempt"].metrics),
            "finite": safe["replay_attempt"].metrics.all_values_finite
            and faulty["replay_attempt"].metrics.all_values_finite,
            "converged": safe["replay_attempt"].converged
            and faulty["replay_attempt"].converged,
        }
        events = tuple(safe["events"] + faulty["events"])
    elif case.case_id == "P5B-INVALID-02":
        base = initial_committed_state()
        persistent_a = P5PersistentState()
        gamma_p = base.gamma_p.copy()
        gamma_p[ACTIVE_INDEX] += ACTIVE_REFERENCE_DELTA
        alternate = CommittedState(
            primary=base.primary,
            gamma_p=gamma_p,
            alpha=base.alpha,
            accepted_index=base.accepted_index,
            accepted_load=base.accepted_load,
            accepted_version=base.accepted_version,
        )
        persistent_b = P5PersistentState()
        persistent_b.hidden_trial_cache[ACTIVE_INDEX] += ACTIVE_REFERENCE_DELTA
        packet_a = _s01_packet(
            declared_state=base, persistent_hash=persistent_a.projection_hash
        )
        packet_b = _s01_packet(
            declared_state=alternate, persistent_hash=persistent_b.projection_hash
        )
        raw = raw_observation(
            packet_a,
            packet_b,
            PrecomparisonRelation.INCOMPATIBLE,
            evidence_tokens=("COMMITTED_FINGERPRINT", "SEMANTIC_PERSISTENT_PROJECTION"),
        )
        measurements = {
            "committed_projection_equal": False,
            "persistent_projection_equal": False,
            "active_field_binding": "gamma_p[27,0,1]",
            "alternate_delta": ACTIVE_REFERENCE_DELTA,
            "lifecycle_not_evaluated": True,
        }
        events = (
            {
                "event_type": "PrecomparisonCommittedProjectionAudit",
                "field_name": "gamma_p[27,0,1]",
            },
        )
    elif case.case_id == "P5B-NS-04":
        base = initial_committed_state()
        persistent = P5PersistentState()
        packet_a = _s01_packet(
            declared_state=base, persistent_hash=persistent.projection_hash
        )
        packet_b = packet_a
        raw = raw_observation(
            packet_a,
            packet_b,
            PrecomparisonRelation.NOT_EVALUATED,
            evidence_tokens=(),
        )
        measurements = {
            "native_linesearch_observer_available": True,
            "frozen_history_unselected_candidate_observed": False,
            "missing_evidence": "UNSELECTED_NATIVE_LINESEARCH_CANDIDATE",
            "no_fe_solve_executed_for_capability_audit": True,
        }
        events = (
            {
                "event_type": "StaticCapabilityAudit",
                "missing_event": "UNSELECTED_NATIVE_LINESEARCH_CANDIDATE",
            },
        )
    else:
        raise ValueError(f"unsupported S01 development case: {case.case_id}")

    return RuntimeRecord(
        case_id=case.case_id,
        run_id=run_id,
        subject_id=case.subject_id,
        runtime_mode=runtime_mode,
        raw=raw,
        events=events,
        measurements=measurements,
        environment=environment,
    )
