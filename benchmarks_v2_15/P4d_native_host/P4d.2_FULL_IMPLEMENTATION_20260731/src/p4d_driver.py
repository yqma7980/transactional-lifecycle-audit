from __future__ import annotations

import pathlib
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

from p4d_canonical import canonical_hash
from p4d_config import (
    LOAD_PATH,
    NEGATIVE_CACHE_SCALE,
    RESTART_LOAD,
    RETRY_FAILED_TARGET,
    RETRY_REPLAY_TARGET,
    RETRY_SOURCE_LOAD,
    is_declared_lag_step,
)
from p4d_host import AttemptResult, TransactionalFEHost
from p4d_io import AcceptedOutputStore, write_checkpoint
from p4d_state import CommittedState, MaterialFieldPacket, PersistentState, initial_committed_state


@dataclass
class HistoryRun:
    history_id: str
    run_id: str
    final_state: CommittedState
    persistent: PersistentState
    output_store: AcceptedOutputStore
    events: list[dict[str, Any]]
    attempts: list[dict[str, Any]]
    replay_packet: dict[str, Any] | None
    checkpoint: dict[str, Any] | None
    prerequisite_status: str
    observer_metadata: dict[str, Any] | None

    def semantic_summary(self) -> dict[str, Any]:
        return {
            "history_id": self.history_id,
            "final_state_hash": self.final_state.full_hash,
            "final_physical_hash": self.final_state.physical_hash,
            "persistent_projection_hash": self.persistent.projection_hash,
            "accepted_loads": [row["accepted_load_factor"] for row in self.output_store.rows if row["source_event"] == "AcceptCommit"],
            "rejected_candidate_reachable": self.output_store.rejected_candidate_reachable(),
            "attempts": self.attempts,
            "replay_packet": self.replay_packet,
            "prerequisite_status": self.prerequisite_status,
        }


def packet_observable(packet: MaterialFieldPacket) -> dict[str, Any]:
    return {
        "candidate_id": packet.candidate_id,
        "primary_hash": packet.primary_hash,
        "committed_hash": packet.committed_hash,
        "target_load": packet.target_load,
        "relation": packet.relation,
        "tau_hash": canonical_hash(packet.tau),
        "tangent_hash": canonical_hash(packet.tangent),
        "gamma_p_candidate_hash": canonical_hash(packet.gamma_p_candidate),
        "alpha_candidate_hash": canonical_hash(packet.alpha_candidate),
        "tau": packet.tau,
        "tangent": packet.tangent,
    }


def _attempt_summary(attempt: AttemptResult) -> dict[str, Any]:
    return {
        "attempt_id": attempt.attempt_id,
        "source_load": attempt.source_load,
        "target_load": attempt.target_load,
        "relation": attempt.relation,
        "snes_reason": attempt.snes_reason,
        "nonlinear_iterations": attempt.nonlinear_iterations,
        "function_evaluations": attempt.function_evaluations,
        "selected_candidate_id": attempt.selected_packet.candidate_id,
        "committed_immutable": attempt.committed_hash_before == attempt.committed_hash_after_callbacks,
        "mechanics": asdict(attempt.metrics),
    }


def run_history(
    history_id: str,
    run_id: str,
    *,
    initial_state: CommittedState | None = None,
    environment_hash: str = "P4D2-ENVIRONMENT-PENDING-FORMAL-RUN",
    checkpoint_directory: pathlib.Path | None = None,
    observer_library: pathlib.Path | None = None,
    observer_ledger: pathlib.Path | None = None,
) -> HistoryRun:
    allowed = {"H_DIRECT", "H_NATIVE_LINESEARCH", "H_DRIVER_RETRY", "H_CACHE_NEGATIVE", "H_OUTPUT_NEGATIVE", "H_RESTART"}
    if history_id not in allowed:
        raise ValueError(f"unsupported lifecycle history {history_id}")
    committed = initial_state if initial_state is not None else initial_committed_state()
    persistent = PersistentState()
    output = AcceptedOutputStore()
    host = TransactionalFEHost(
        committed,
        persistent,
        run_id=run_id,
        observer_library=observer_library,
        observer_ledger=observer_ledger,
    )
    attempts: list[dict[str, Any]] = []
    replay_packet: dict[str, Any] | None = None
    checkpoint: dict[str, Any] | None = None
    prerequisite_status = "PASS"
    start_index = committed.accepted_index + 1

    for accepted_index in range(start_index, len(LOAD_PATH)):
        target_load = LOAD_PATH[accepted_index]
        source_load = host.committed.accepted_load
        if history_id in {"H_DRIVER_RETRY", "H_CACHE_NEGATIVE", "H_OUTPUT_NEGATIVE"} and source_load == RETRY_SOURCE_LOAD and target_load == RETRY_REPLAY_TARGET:
            persistent_before = persistent.snapshot()
            host.begin_attempt(RETRY_FAILED_TARGET, f"{run_id}-FAILED-020", "EXACT_CURRENT", maximum_iterations=1)
            failed_attempt = host.solve_attempt()
            attempts.append(_attempt_summary(failed_attempt))
            if failed_attempt.converged:
                prerequisite_status = "NOT_SUPPORTED_FORCED_RETRY_TRIGGER"
                break
            if history_id == "H_CACHE_NEGATIVE":
                persistent.hidden_trial_cache += NEGATIVE_CACHE_SCALE * (
                    failed_attempt.selected_packet.gamma_p_candidate - host.committed.gamma_p
                )
                persistent.mutation_count += 1
                host.events.append(
                    "UnsafePersistentMutation",
                    solve_id=run_id,
                    attempt_id=failed_attempt.attempt_id,
                    candidate_id=failed_attempt.selected_packet.candidate_id,
                    persistent_before_hash=persistent_before["projection_hash"],
                    persistent_projection_hash=persistent.projection_hash,
                    scale=NEGATIVE_CACHE_SCALE,
                    reachable_from_accepted_output=False,
                )
            if history_id == "H_OUTPUT_NEGATIVE":
                output.inject_rejected_candidate(
                    candidate_id=failed_attempt.selected_packet.candidate_id,
                    source_load=failed_attempt.source_load,
                    target_load=failed_attempt.target_load,
                )
                host.events.append(
                    "UnsafeRejectedCandidateOutput",
                    solve_id=run_id,
                    attempt_id=failed_attempt.attempt_id,
                    candidate_id=failed_attempt.selected_packet.candidate_id,
                    reachable_from_accepted_output=True,
                )
            host.restore_after_failed_attempt(failed_attempt)

        relation = "EXACT_CURRENT"
        if history_id == "H_NATIVE_LINESEARCH" and is_declared_lag_step(source_load, target_load, accepted_index):
            relation = "DECLARED_ACCEPTED_STATE_LAG"
        host.begin_attempt(target_load, f"{run_id}-A{accepted_index:02d}", relation, maximum_iterations=25)
        attempt = host.solve_attempt()
        attempts.append(_attempt_summary(attempt))
        if target_load == RETRY_REPLAY_TARGET and source_load == RETRY_SOURCE_LOAD:
            packets = tuple(host._packet_cache.values())
            if not packets:
                raise RuntimeError("replay boundary has no material packet")
            replay_packet = packet_observable(packets[0])
        if not attempt.converged:
            prerequisite_status = "FAILED_NORMAL_ATTEMPT"
            break
        host.commit(attempt)
        host.events.append(
            "OutputAcceptedState",
            solve_id=run_id,
            attempt_id=attempt.attempt_id,
            candidate_id=attempt.selected_packet.candidate_id,
            committed_state_hash=host.committed.full_hash,
            accepted_version=host.committed.accepted_version,
            reachable_from_accepted_output=True,
        )
        output.append_after_commit(
            state=host.committed,
            candidate_id=attempt.selected_packet.candidate_id,
            metrics=attempt.metrics,
            mesh_hashes=host.context.hashes,
            relation=relation,
        )
        if target_load == RESTART_LOAD and checkpoint_directory is not None:
            host.events.append(
                "CheckpointWrite",
                solve_id=run_id,
                attempt_id=attempt.attempt_id,
                candidate_id=attempt.selected_packet.candidate_id,
                committed_state_hash=host.committed.full_hash,
                reachable_from_accepted_output=False,
            )
            checkpoint = write_checkpoint(checkpoint_directory, host.committed, host.context.hashes, environment_hash)

    result = HistoryRun(
        history_id=history_id,
        run_id=run_id,
        final_state=host.committed,
        persistent=persistent,
        output_store=output,
        events=host.events.records,
        attempts=attempts,
        replay_packet=replay_packet,
        checkpoint=checkpoint,
        prerequisite_status=prerequisite_status,
        observer_metadata=host.observer_metadata,
    )
    host.close()
    return result


def operator_drift(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    residual_delta = np.asarray(right["tau"]) - np.asarray(left["tau"])
    tangent_delta = np.asarray(right["tangent"]) - np.asarray(left["tangent"])
    return {
        "declared_primary_equal": left["primary_hash"] == right["primary_hash"],
        "declared_committed_equal": left["committed_hash"] == right["committed_hash"],
        "declared_target_equal": left["target_load"] == right["target_load"],
        "residual_drift_norm": float(np.linalg.norm(residual_delta)),
        "tangent_drift_norm": float(np.linalg.norm(tangent_delta)),
        "residual_drift_finite": bool(np.isfinite(residual_delta).all()),
        "tangent_drift_finite": bool(np.isfinite(tangent_delta).all()),
    }
