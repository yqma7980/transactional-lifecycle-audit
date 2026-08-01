from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import sys
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
WORKING = ROOT.parent
P4D2_SRC = WORKING / "P4d_DOLFINx_PETSc_MINIMAL_FE_HOST_20260731" / "P4d.2_FULL_IMPLEMENTATION_20260731" / "src"
if str(P4D2_SRC) not in sys.path:
    sys.path.insert(0, str(P4D2_SRC))

from p4d_canonical import canonical_hash
from p4d_config import LOAD_PATH, RETRY_FAILED_TARGET, RETRY_REPLAY_TARGET, RETRY_SOURCE_LOAD
from p4d_state import initial_committed_state

from p5_fe_adapter import P5PersistentState, P5TransactionalFEHost, evaluate_p5_material_field, inject_fault


@dataclass
class P5HistoryRun:
    history_id: str
    role: str
    family_id: str | None
    eta: float
    final_state: Any
    persistent: P5PersistentState
    output_rows: list[dict[str, Any]]
    events: list[dict[str, Any]]
    attempts: list[dict[str, Any]]
    replay_packet: Any
    context: Any
    prerequisite_status: str
    mutation_record: dict[str, Any] | None

    @property
    def conventional_quiet(self) -> bool:
        normal_attempts = [row for row in self.attempts if not row["forced_rejected_attempt"]]
        return bool(
            self.prerequisite_status == "PASS"
            and self.final_state.accepted_index == len(LOAD_PATH) - 1
            and all(row["snes_reason"] > 0 and row["mechanics_pass"] for row in normal_attempts)
            and all(row["all_values_finite"] for row in self.attempts)
        )

    @property
    def lifecycle_violation_present(self) -> bool:
        if self.role != "faulty" or self.mutation_record is None:
            return False
        if self.persistent.mutation_count != 1:
            return False
        if self.family_id == "F05":
            return self.persistent.rejected_source_candidate_id is not None
        return self.mutation_record["persistent_before_hash"] != self.mutation_record["persistent_after_hash"]


def _attempt_summary(attempt, forced: bool) -> dict[str, Any]:
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
        "forced_rejected_attempt": forced,
        "mechanics_pass": bool(attempt.metrics.pass_flag),
        "all_values_finite": bool(attempt.metrics.all_values_finite),
        "mechanics": asdict(attempt.metrics),
    }


def _accepted_output_row(host: P5TransactionalFEHost, attempt) -> dict[str, Any]:
    state = host.committed
    return {
        "accepted_index": state.accepted_index,
        "accepted_load_factor": state.accepted_load,
        "accepted_version": state.accepted_version,
        "candidate_id": attempt.selected_packet.candidate_id,
        "source_event": "AcceptCommit",
        "primary": state.primary.copy(),
        "gamma_p": state.gamma_p.copy(),
        "alpha": state.alpha.copy(),
        "top_reaction": float(attempt.metrics.top_reaction),
        "bottom_reaction": float(attempt.metrics.bottom_reaction),
        "residual_norm": float(attempt.metrics.residual_norm),
        "relation": attempt.relation,
    }


def _record_mutation(host: P5TransactionalFEHost, attempt_id: str, mutation: dict[str, Any], reachable: bool) -> None:
    host.events.append(
        "SeededLifecycleMutation",
        solve_id=host.run_id,
        attempt_id=attempt_id,
        reachable_from_accepted_output=reachable,
        **mutation,
    )


def run_p5_history(family_id: str | None, faulty: bool, eta: float, run_id: str) -> P5HistoryRun:
    if faulty and family_id not in {"F01", "F02", "F05", "F07"}:
        raise ValueError("faulty P5 history requires a frozen family")
    if not faulty and eta != 0.0:
        raise ValueError("safe P5 history must use eta=0")
    committed = initial_committed_state()
    persistent = P5PersistentState()
    role = "faulty" if faulty else "safe"
    history_id = f"H_{family_id}_{role.upper()}" if family_id else "H_DIRECT_SAFE"
    host = P5TransactionalFEHost(committed, persistent, run_id=f"{run_id}-{role}")
    output_rows: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []
    replay_packet = None
    mutation_record = None
    prerequisite_status = "PASS"

    for accepted_index in range(1, len(LOAD_PATH)):
        target_load = float(LOAD_PATH[accepted_index])
        source_load = float(host.committed.accepted_load)
        at_replay_boundary = source_load == RETRY_SOURCE_LOAD and target_load == RETRY_REPLAY_TARGET

        if family_id in {"F01", "F02", "F05"} and at_replay_boundary:
            attempt_id = f"{run_id}-{role}-FAILED-020"
            host.begin_attempt(RETRY_FAILED_TARGET, attempt_id, "EXACT_CURRENT", maximum_iterations=1)
            failed = host.solve_attempt()
            attempts.append(_attempt_summary(failed, forced=True))
            if failed.converged:
                prerequisite_status = "NOT_SUPPORTED_FORCED_RETRY_TRIGGER"
                break
            if faulty:
                mutation_record = inject_fault(persistent, family_id, eta, failed.selected_packet.candidate_id)
                _record_mutation(host, attempt_id, mutation_record, family_id == "F05")
            host.restore_after_failed_attempt(failed)

        if family_id == "F07" and faulty and at_replay_boundary:
            attempt_id = f"{run_id}-{role}-EXTRA-CALLBACK"
            probe = evaluate_p5_material_field(
                host.context,
                host.committed.primary,
                host.committed,
                persistent,
                target_load,
                "EXACT_CURRENT",
            )
            host.events.append(
                "ExtraNonacceptingResidual",
                solve_id=host.run_id,
                attempt_id=attempt_id,
                candidate_id=probe.candidate_id,
                primary_vector_hash=probe.primary_hash,
                committed_state_hash=host.committed.full_hash,
                persistent_projection_hash=persistent.projection_hash,
                reachable_from_accepted_output=False,
            )
            mutation_record = inject_fault(persistent, family_id, eta, probe.candidate_id)
            _record_mutation(host, attempt_id, mutation_record, False)

        attempt_id = f"{run_id}-{role}-A{accepted_index:02d}"
        host.begin_attempt(target_load, attempt_id, "EXACT_CURRENT", maximum_iterations=25)
        attempt = host.solve_attempt()
        attempts.append(_attempt_summary(attempt, forced=False))
        if at_replay_boundary:
            packets = tuple(host._packet_cache.values())
            if not packets:
                raise RuntimeError("P5 replay boundary has no material packet")
            replay_packet = packets[0]
        if not attempt.converged:
            prerequisite_status = "FAILED_NORMAL_ATTEMPT"
            break
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
        output_rows.append(_accepted_output_row(host, attempt))

    if replay_packet is None and prerequisite_status == "PASS":
        raise RuntimeError("P5 completed without a replay packet")
    result = P5HistoryRun(
        history_id=history_id,
        role=role,
        family_id=family_id,
        eta=float(eta),
        final_state=host.committed,
        persistent=persistent,
        output_rows=output_rows,
        events=host.events.records,
        attempts=attempts,
        replay_packet=replay_packet,
        context=host.context,
        prerequisite_status=prerequisite_status,
        mutation_record=mutation_record,
    )
    host.close()
    return result


def semantic_history_summary(history: P5HistoryRun) -> dict[str, Any]:
    return {
        "history_id": history.history_id,
        "role": history.role,
        "family_id": history.family_id,
        "eta": history.eta,
        "final_state_hash": history.final_state.full_hash,
        "final_physical_hash": history.final_state.physical_hash,
        "persistent_projection_hash": history.persistent.projection_hash,
        "accepted_loads": [row["accepted_load_factor"] for row in history.output_rows],
        "accepted_candidate_ids": [row["candidate_id"] for row in history.output_rows],
        "conventional_quiet": history.conventional_quiet,
        "lifecycle_violation_present": history.lifecycle_violation_present,
        "prerequisite_status": history.prerequisite_status,
        "mutation_record": history.mutation_record,
        "event_projection_hash": canonical_hash([
            {key: value for key, value in row.items() if key not in {"solve_id", "attempt_id"}}
            for row in history.events
        ]),
    }
