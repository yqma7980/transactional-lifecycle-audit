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
from p5_fe_adapter import P5PersistentState, inject_fault
from p5_quadrature_backend_erratum_v2 import P5QuadratureAwareFEHost

from .cases import CaseSpec
from .model import PrecomparisonRelation
from .runtime import RuntimeRecord, raw_observation, replay_packet, runtime_environment
from .runtime_s01 import _clone_committed, _s01_environment


ETA_LOW = 1.0e-10


def _declared_packet(
    state: CommittedState,
    persistent_hash: str,
    *,
    boundary_control: str = "FROZEN-A",
):
    return replay_packet(
        primary={"primary_hash": canonical_hash(state.primary)},
        committed={"full_hash": state.full_hash},
        persistent={"projection_hash": persistent_hash},
        load={"source": 0.08, "target": 0.10},
        residual_version="P4D-R1",
        tangent_version="P4D-K1",
        environment={
            "subject": "JSS-S01",
            "host": "DOLFINx-PETSc-P5",
            "boundary_control": boundary_control,
        },
    )


def _accept(
    host: P5QuadratureAwareFEHost,
    target: float,
    label: str,
    *,
    emit_output: bool,
    output_candidate_id: str | None = None,
    source_candidate_reachable: bool = True,
):
    host.begin_attempt(target, label, "EXACT_CURRENT", maximum_iterations=25)
    attempt = host.solve_attempt()
    if not attempt.converged:
        raise RuntimeError(f"held-out accepted increment did not converge: {label}")
    if not attempt.metrics.pass_flag:
        raise RuntimeError(f"held-out mechanics gate failed: {label}")
    host.commit(attempt)
    if emit_output:
        candidate_id = output_candidate_id or attempt.selected_packet.candidate_id
        host.events.append(
            "OutputAcceptedState",
            solve_id=host.run_id,
            attempt_id=attempt.attempt_id,
            candidate_id=candidate_id,
            accepted_candidate_id=attempt.selected_packet.candidate_id,
            committed_state_hash=host.committed.full_hash,
            accepted_version=host.committed.accepted_version,
            source_event=(
                "AcceptCommit" if source_candidate_reachable else "RejectedTrialCandidate"
            ),
            source_candidate_reachable=source_candidate_reachable,
            reachable_from_accepted_output=True,
        )
    return attempt


def _pass_postcommit_output(case: CaseSpec, run_id: str, runtime_mode: str) -> RuntimeRecord:
    direct = P5QuadratureAwareFEHost(
        initial_committed_state(), P5PersistentState(), run_id=f"{run_id}-NO-OUTPUT"
    )
    output = P5QuadratureAwareFEHost(
        initial_committed_state(), P5PersistentState(), run_id=f"{run_id}-POSTCOMMIT"
    )
    try:
        for target, suffix in ((0.04, "A01"), (0.08, "A02")):
            _accept(direct, target, f"DIRECT-{suffix}", emit_output=False)
            _accept(output, target, f"OUTPUT-{suffix}", emit_output=True)
        direct_declared = _clone_committed(direct.committed)
        output_declared = _clone_committed(output.committed)
        direct_persistent = direct.persistent.projection_hash
        output_persistent = output.persistent.projection_hash
        direct_final = _accept(direct, 0.10, "DIRECT-A03", emit_output=False)
        output_final = _accept(output, 0.10, "OUTPUT-A03", emit_output=True)

        if direct_declared.full_hash != output_declared.full_hash:
            raise RuntimeError("post-commit control declared states differ")
        if direct_persistent != output_persistent:
            raise RuntimeError("post-commit control persistent projections differ")
        if direct.committed.full_hash != output.committed.full_hash:
            raise RuntimeError("post-commit output changed the accepted state")
        field_delta = max(
            float(np.max(np.abs(direct.committed.primary - output.committed.primary))),
            float(np.max(np.abs(direct.committed.gamma_p - output.committed.gamma_p))),
            float(np.max(np.abs(direct.committed.alpha - output.committed.alpha))),
        )
        if field_delta != 0.0:
            raise RuntimeError("post-commit output changed accepted fields")

        packet_a = _declared_packet(direct_declared, direct_persistent)
        packet_b = _declared_packet(output_declared, output_persistent)
        raw = raw_observation(
            packet_a,
            packet_b,
            PrecomparisonRelation.COMPATIBLE,
            evidence_tokens=("COMMIT_REACHABILITY", "OUTPUT_CANDIDATE"),
        )
        events = tuple(direct.events.records + output.events.records)
        measurements = {
            "accepted_field_delta": field_delta,
            "accepted_full_hash_equal": True,
            "diagnostic_output_count_direct": 0,
            "diagnostic_output_count_postcommit": 3,
            "postcommit_output_candidate_matches_accepted_candidate": True,
            "postcommit_output_after_commit": True,
            "direct_mechanics": asdict(direct_final.metrics),
            "postcommit_mechanics": asdict(output_final.metrics),
            "finite": bool(
                direct_final.metrics.all_values_finite
                and output_final.metrics.all_values_finite
            ),
            "converged": bool(direct_final.converged and output_final.converged),
        }
    finally:
        direct.close()
        output.close()
    return RuntimeRecord(
        case_id=case.case_id,
        run_id=run_id,
        subject_id=case.subject_id,
        runtime_mode=runtime_mode,
        raw=raw,
        events=events,
        measurements=measurements,
        environment=_s01_environment(),
    )


def _rejected_output_history(run_id: str, *, faulty: bool) -> dict[str, Any]:
    role = "FAULT" if faulty else "DIRECT"
    host = P5QuadratureAwareFEHost(
        initial_committed_state(), P5PersistentState(), run_id=f"{run_id}-{role}"
    )
    try:
        _accept(host, 0.04, f"{role}-A01", emit_output=False)
        _accept(host, 0.08, f"{role}-A02", emit_output=False)
        declared = _clone_committed(host.committed)
        persistent_declared = host.persistent.projection_hash

        host.begin_attempt(0.20, f"{role}-FAILED-020", "EXACT_CURRENT", maximum_iterations=1)
        failed = host.solve_attempt()
        if failed.converged:
            raise RuntimeError("frozen held-out forced-retry trigger unexpectedly converged")
        rejected_candidate_id = failed.selected_packet.candidate_id
        mutation = None
        if faulty:
            mutation = inject_fault(
                host.persistent,
                "F05",
                ETA_LOW,
                rejected_candidate_id,
            )
            host.events.append(
                "SeededLifecycleMutation",
                solve_id=host.run_id,
                attempt_id=failed.attempt_id,
                reachable_from_accepted_output=False,
                **mutation,
            )
        host.restore_after_failed_attempt(failed)
        replay = _accept(host, 0.10, f"{role}-REPLAY-010", emit_output=False)
        accepted_candidate_id = replay.selected_packet.candidate_id
        output_candidate_id = rejected_candidate_id if faulty else accepted_candidate_id
        host.events.append(
            "OutputAcceptedState",
            solve_id=host.run_id,
            attempt_id=replay.attempt_id,
            candidate_id=output_candidate_id,
            accepted_candidate_id=accepted_candidate_id,
            committed_state_hash=host.committed.full_hash,
            accepted_version=host.committed.accepted_version,
            source_event="RejectedTrialCandidate" if faulty else "AcceptCommit",
            source_candidate_reachable=not faulty,
            reachable_from_accepted_output=True,
        )
        if faulty and output_candidate_id == accepted_candidate_id:
            raise RuntimeError("rejected-output negative control did not separate source candidates")
        result = {
            "declared": declared,
            "persistent_declared": persistent_declared,
            "failed": failed,
            "replay": replay,
            "rejected_candidate_id": rejected_candidate_id,
            "accepted_candidate_id": accepted_candidate_id,
            "output_candidate_id": output_candidate_id,
            "mutation": mutation,
            "events": tuple(host.events.records),
            "final_state": _clone_committed(host.committed),
        }
    finally:
        host.close()
    return result


def _detect_rejected_output(case: CaseSpec, run_id: str, runtime_mode: str) -> RuntimeRecord:
    direct = _rejected_output_history(run_id, faulty=False)
    faulty = _rejected_output_history(run_id, faulty=True)
    if direct["declared"].full_hash != faulty["declared"].full_hash:
        raise RuntimeError("rejected-output histories do not share the declared state")
    if direct["persistent_declared"] != faulty["persistent_declared"]:
        raise RuntimeError("rejected-output histories do not share declared persistence")
    if faulty["mutation"] is None:
        raise RuntimeError("rejected-output mutation record is absent")

    packet_a = _declared_packet(direct["declared"], direct["persistent_declared"])
    packet_b = _declared_packet(faulty["declared"], faulty["persistent_declared"])
    raw = raw_observation(
        packet_a,
        packet_b,
        PrecomparisonRelation.COMPATIBLE,
        evidence_tokens=("CANDIDATE_REACHABILITY", "OUTPUT_SOURCE"),
        signal_names=("output_provenance_violation",),
    )
    tau_drift = float(
        np.max(np.abs(direct["replay"].selected_packet.tau - faulty["replay"].selected_packet.tau))
    )
    tangent_drift = float(
        np.max(
            np.abs(
                direct["replay"].selected_packet.tangent
                - faulty["replay"].selected_packet.tangent
            )
        )
    )
    measurements = {
        "seed_strength": ETA_LOW,
        "direct_output_candidate_matches_accepted": True,
        "faulty_output_candidate_matches_rejected": True,
        "faulty_output_candidate_matches_accepted": False,
        "rejected_candidate_unreachable_before_output": True,
        "output_provenance_violation": True,
        "tau_replay_drift": tau_drift,
        "tangent_replay_drift": tangent_drift,
        "direct_failed_reason": direct["failed"].snes_reason,
        "faulty_failed_reason": faulty["failed"].snes_reason,
        "direct_replay_mechanics": asdict(direct["replay"].metrics),
        "faulty_replay_mechanics": asdict(faulty["replay"].metrics),
        "finite": bool(
            direct["replay"].metrics.all_values_finite
            and faulty["replay"].metrics.all_values_finite
        ),
        "converged": bool(direct["replay"].converged and faulty["replay"].converged),
    }
    return RuntimeRecord(
        case_id=case.case_id,
        run_id=run_id,
        subject_id=case.subject_id,
        runtime_mode=runtime_mode,
        raw=raw,
        events=tuple(direct["events"] + faulty["events"]),
        measurements=measurements,
        environment=_s01_environment(),
    )


def _invalid_boundary_control(case: CaseSpec, run_id: str, runtime_mode: str) -> RuntimeRecord:
    base = initial_committed_state()
    persistent = P5PersistentState()
    packet_a = _declared_packet(base, persistent.projection_hash, boundary_control="FROZEN-A")
    packet_b = _declared_packet(base, persistent.projection_hash, boundary_control="FROZEN-B")
    raw = raw_observation(
        packet_a,
        packet_b,
        PrecomparisonRelation.INCOMPATIBLE,
        evidence_tokens=("BOUNDARY_CONTROL_HASHES",),
    )
    return RuntimeRecord(
        case_id=case.case_id,
        run_id=run_id,
        subject_id=case.subject_id,
        runtime_mode=runtime_mode,
        raw=raw,
        events=(
            {
                "event_type": "PrecomparisonBoundaryControlAudit",
                "packet_a_control": "FROZEN-A",
                "packet_b_control": "FROZEN-B",
                "mismatch_field": "environment_hash",
                "lifecycle_evaluation_reachable": False,
            },
        ),
        measurements={
            "boundary_control_hash_equal": False,
            "expected_mismatch_field": "environment_hash",
            "no_fe_solve_executed_for_eligibility_audit": True,
            "lifecycle_not_evaluated": True,
        },
        environment=_s01_environment(),
    )


def _not_supported_parallel_ownership(
    case: CaseSpec,
    run_id: str,
    runtime_mode: str,
) -> RuntimeRecord:
    packet = replay_packet(
        primary={"subject": "JSS-S02", "state": "serial-control"},
        committed={"accepted_version": 0},
        persistent={"projection": "serial-only"},
        load={"case": "parallel-callback-capability-audit"},
        residual_version="L4-R1",
        tangent_version="L4-K1",
        environment={"processes": 1, "threads": 1, "parallel_callbacks": False},
    )
    raw = raw_observation(
        packet,
        packet,
        PrecomparisonRelation.NOT_EVALUATED,
        evidence_tokens=(),
    )
    return RuntimeRecord(
        case_id=case.case_id,
        run_id=run_id,
        subject_id=case.subject_id,
        runtime_mode=runtime_mode,
        raw=raw,
        events=(
            {
                "event_type": "StaticCapabilityAudit",
                "backend_mode": "serial",
                "missing_event": "PARALLEL_CALLBACK_OWNERSHIP",
                "lifecycle_evaluation_reachable": False,
            },
        ),
        measurements={
            "processes": 1,
            "threads": 1,
            "parallel_callback_path_available": False,
            "no_subject_solve_executed_for_capability_audit": True,
        },
        environment=runtime_environment(
            "JSS-S02",
            backend={"name": "serial two-phase subject capability audit"},
        ),
    )


def execute_heldout_runtime(case: CaseSpec, run_id: str, runtime_mode: str) -> RuntimeRecord:
    if case.case_id == "P5B-PASS-05":
        return _pass_postcommit_output(case, run_id, runtime_mode)
    if case.case_id == "P5B-DETECT-05":
        return _detect_rejected_output(case, run_id, runtime_mode)
    if case.case_id == "P5B-INVALID-05":
        return _invalid_boundary_control(case, run_id, runtime_mode)
    if case.case_id == "P5B-NS-05":
        return _not_supported_parallel_ownership(case, run_id, runtime_mode)
    raise ValueError(f"unsupported held-out case: {case.case_id}")
