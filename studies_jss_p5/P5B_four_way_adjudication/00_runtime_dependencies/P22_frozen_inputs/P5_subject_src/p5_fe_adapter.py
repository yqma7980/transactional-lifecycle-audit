from __future__ import annotations

from dataclasses import dataclass, field
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
from p4d_config import RESIDUAL_VERSION, TANGENT_VERSION
from p4d_host import AttemptResult, TransactionalFEHost
from p4d_material import evaluate_material
from p4d_mesh import cell_gradients
from p4d_state import MaterialFieldPacket


@dataclass
class P5PersistentState:
    hidden_trial_cache: np.ndarray = field(default_factory=lambda: np.zeros((32, 3, 2), dtype=np.float64))
    declared_alpha_cache: np.ndarray = field(default_factory=lambda: np.zeros((32, 3), dtype=np.float64))
    feedback_mirror_E: float = 0.0
    feedback_mirror_J: float = 0.0
    callback_bias_F: float = 0.0
    mutation_count: int = 0
    rejected_source_candidate_id: str | None = None

    @property
    def projection_hash(self) -> str:
        return canonical_hash({
            "hidden_trial_cache": self.hidden_trial_cache,
            "declared_alpha_cache": self.declared_alpha_cache,
            "feedback_mirror_E": self.feedback_mirror_E,
            "feedback_mirror_J": self.feedback_mirror_J,
            "callback_bias_F": self.callback_bias_F,
            "mutation_count": self.mutation_count,
            "rejected_source_candidate_id": self.rejected_source_candidate_id,
        })

    def snapshot(self) -> dict[str, Any]:
        return {
            "hidden_trial_cache": self.hidden_trial_cache.copy(),
            "declared_alpha_cache": self.declared_alpha_cache.copy(),
            "feedback_mirror_E": float(self.feedback_mirror_E),
            "feedback_mirror_J": float(self.feedback_mirror_J),
            "callback_bias_F": float(self.callback_bias_F),
            "mutation_count": int(self.mutation_count),
            "rejected_source_candidate_id": self.rejected_source_candidate_id,
            "projection_hash": self.projection_hash,
        }


def evaluate_p5_material_field(
    context,
    primary_values: np.ndarray,
    committed,
    persistent: P5PersistentState,
    target_load: float,
    relation: str,
    lag_primary_values: np.ndarray | None = None,
) -> MaterialFieldPacket:
    primary = np.asarray(primary_values, dtype=np.float64)
    gradients = cell_gradients(context, primary)
    lag_primary = primary if lag_primary_values is None else np.asarray(lag_primary_values, dtype=np.float64)
    lag_gradients = cell_gradients(context, lag_primary)
    tau = np.empty((32, 3, 2), dtype=np.float64)
    tangent = np.empty((32, 3, 2, 2), dtype=np.float64)
    candidate_gamma_p = np.empty((32, 3, 2), dtype=np.float64)
    candidate_alpha = np.empty((32, 3), dtype=np.float64)
    branches = np.empty((32, 3), dtype="U7")
    yield_function = np.empty((32, 3), dtype=np.float64)
    delta_lambda = np.empty((32, 3), dtype=np.float64)
    effective_gamma_p = committed.gamma_p + persistent.hidden_trial_cache
    effective_alpha = committed.alpha + persistent.declared_alpha_cache

    for cell in range(32):
        for point in range(3):
            current = evaluate_material(gradients[cell], effective_gamma_p[cell, point], effective_alpha[cell, point])
            tau[cell, point] = current.tau
            candidate_gamma_p[cell, point] = current.candidate.gamma_p
            candidate_alpha[cell, point] = current.candidate.alpha
            branches[cell, point] = current.branch
            yield_function[cell, point] = current.yield_function
            delta_lambda[cell, point] = current.delta_lambda
            if relation == "DECLARED_ACCEPTED_STATE_LAG":
                lagged = evaluate_material(lag_gradients[cell], effective_gamma_p[cell, point], effective_alpha[cell, point])
                tangent[cell, point] = lagged.tangent
            else:
                tangent[cell, point] = current.tangent

    # Seeded negative-control overlays are zero on every safe path. They are
    # applied uniformly over a cell so the frozen P1 quadrature contract holds.
    tau[0, :, 0] += persistent.feedback_mirror_E
    tangent[31, :, 1, 1] += persistent.feedback_mirror_J
    tau[31, :, 0] += persistent.callback_bias_F

    primary_hash = canonical_hash(primary)
    lag_hash = canonical_hash(lag_primary)
    packet_payload = {
        "primary_hash": primary_hash,
        "committed_hash": committed.full_hash,
        "persistent_hash": persistent.projection_hash,
        "target_load": target_load,
        "relation": relation,
        "tau": tau,
        "tangent": tangent,
        "gamma_p_candidate": candidate_gamma_p,
        "alpha_candidate": candidate_alpha,
        "tangent_source_primary_hash": lag_hash,
    }
    return MaterialFieldPacket(
        candidate_id=canonical_hash(packet_payload),
        primary_hash=primary_hash,
        committed_hash=committed.full_hash,
        persistent_hash=persistent.projection_hash,
        target_load=float(target_load),
        relation=relation,
        tau=tau,
        tangent=tangent,
        gamma_p_candidate=candidate_gamma_p,
        alpha_candidate=candidate_alpha,
        branch=branches,
        yield_function=yield_function,
        delta_lambda=delta_lambda,
        tangent_source_primary_hash=lag_hash,
    )


class P5TransactionalFEHost(TransactionalFEHost):
    persistent: P5PersistentState

    def _evaluate_primary(self, primary: np.ndarray) -> MaterialFieldPacket:
        return evaluate_p5_material_field(
            self.context,
            primary,
            self.committed,
            self.persistent,
            self.target_load,
            self.relation,
            self.lag_primary if self.relation == "DECLARED_ACCEPTED_STATE_LAG" else None,
        )

    def _prepare_packet(self, x) -> MaterialFieldPacket:
        from dolfinx.fem.petsc import assign

        assign(x, self.solution)
        self.solution.x.scatter_forward()
        primary = self.solution.x.array.copy()
        key = self._packet_key(primary)
        packet = self._packet_cache.get(key)
        if packet is None:
            committed_before = self.committed.full_hash
            packet = self._evaluate_primary(primary)
            if self.committed.full_hash != committed_before:
                raise RuntimeError("P5 TrialEvaluate mutated the committed source")
            self._packet_cache[key] = packet
            self.events.append(
                "TrialEvaluate",
                solve_id=self.run_id,
                attempt_id=self.current_attempt_id,
                candidate_id=packet.candidate_id,
                primary_vector_hash=packet.primary_hash,
                primary_vector_hex=[float(value).hex() for value in primary],
                committed_state_hash=packet.committed_hash,
                persistent_projection_hash=packet.persistent_hash,
                candidate_state_hash=canonical_hash({"gamma_p": packet.gamma_p_candidate, "alpha": packet.alpha_candidate}),
                residual_version=packet.residual_version,
                tangent_version=packet.tangent_version,
                line_search_lambda=None,
                line_search_reason=None,
                reachable_from_accepted_output=False,
            )
        self._activate_packet(packet)
        return packet

    def solve_attempt(self) -> AttemptResult:
        committed_before = self.committed.full_hash
        self.problem.solve()
        reason = int(self.problem.solver.getConvergedReason())
        selected_primary = self.solution.x.array.copy()
        key = self._packet_key(selected_primary)
        packet = self._packet_cache.get(key)
        if packet is None:
            packet = self._evaluate_primary(selected_primary)
            self._packet_cache[key] = packet
            self._activate_packet(packet)
            self.events.append(
                "SelectedCandidateReconstruct",
                solve_id=self.run_id,
                attempt_id=self.current_attempt_id,
                candidate_id=packet.candidate_id,
                primary_vector_hash=packet.primary_hash,
                committed_state_hash=self.committed.full_hash,
                persistent_projection_hash=self.persistent.projection_hash,
                reachable_from_accepted_output=False,
            )
        metrics = self.mechanics_metrics(selected_primary, packet)
        committed_after = self.committed.full_hash
        self.events.append(
            "SolveCompleted",
            solve_id=self.run_id,
            attempt_id=self.current_attempt_id,
            candidate_id=packet.candidate_id,
            snes_reason=reason,
            nonlinear_iterations=int(self.problem.solver.getIterationNumber()),
            committed_state_hash=committed_after,
            reachable_from_accepted_output=False,
        )
        return AttemptResult(
            attempt_id=self.current_attempt_id,
            source_load=self.committed.accepted_load,
            target_load=self.target_load,
            relation=self.relation,
            snes_reason=reason,
            nonlinear_iterations=int(self.problem.solver.getIterationNumber()),
            function_evaluations=int(self.problem.solver.getFunctionEvaluations()),
            residual_sequence_hex=tuple(self._residual_sequence),
            selected_primary=selected_primary,
            selected_packet=packet,
            metrics=metrics,
            committed_hash_before=committed_before,
            committed_hash_after_callbacks=committed_after,
        )


def inject_fault(persistent: P5PersistentState, family_id: str, eta: float, candidate_id: str | None) -> dict[str, Any]:
    if not np.isfinite(eta) or eta <= 0.0:
        raise ValueError("eta must be positive and finite")
    before = persistent.projection_hash
    if family_id == "F01":
        persistent.hidden_trial_cache[0, 0, 0] += eta * 0.1
        binding = "trial_cache.gamma_p[0,0,0]"
        verdict = "FAIL_PERSISTENT_STATE_RESTORATION"
    elif family_id == "F02":
        persistent.declared_alpha_cache[0, 1] += eta * 0.1
        binding = "declared_snapshot.alpha[0,1]"
        verdict = "FAIL_DECLARED_PERSISTENT_FIELD_RESTORATION"
    elif family_id == "F05":
        persistent.feedback_mirror_E += eta
        persistent.rejected_source_candidate_id = candidate_id
        binding = "feedback_mirror_E@first_lambda_0.10_replay"
        verdict = "FAIL_REJECTED_SOURCE_REACHABILITY"
    elif family_id == "F07":
        persistent.callback_bias_F += eta
        binding = "callback_bias_F@extra_nonaccepting_residual"
        verdict = "FAIL_PROCESS_GLOBAL_STATE_RESTORATION"
    else:
        raise ValueError(f"unsupported P5 fault family {family_id}")
    persistent.mutation_count += 1
    return {
        "family_id": family_id,
        "eta": float(eta),
        "physical_delta": float(eta * 0.1 if family_id in {"F01", "F02"} else eta),
        "field_binding": binding,
        "expected_lifecycle_verdict": verdict,
        "persistent_before_hash": before,
        "persistent_after_hash": persistent.projection_hash,
        "candidate_id": candidate_id,
    }
