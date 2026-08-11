from __future__ import annotations

import math
import pathlib
from dataclasses import dataclass
from typing import Any

import numpy as np

from p4d_bridge import attach_observer
from p4d_canonical import canonical_hash, file_sha256
from p4d_config import (
    EQUILIBRIUM_TOL,
    FINITE_LIMIT,
    G,
    HARDENING,
    RESIDUAL_VERSION,
    SNES_OPTIONS,
    TANGENT_VERSION,
    TAU_Y0,
    YIELD_TOL,
)
from p4d_evaluator import evaluate_material_field, representative_cell_coefficients
from p4d_mesh import MeshContext, assign_cellwise_tensor, assign_cellwise_vector, build_mesh_context
from p4d_state import (
    CommittedState,
    EventLedger,
    MaterialFieldPacket,
    OperatorVersionPacket,
    PersistentState,
    validate_operator_versions,
)


class OperatorVersionError(RuntimeError):
    pass


@dataclass(frozen=True)
class MechanicsMetrics:
    all_values_finite: bool
    alpha_bounded: bool
    alpha_nondecreasing: bool
    free_residual_relative: float
    reaction_balance_relative: float
    yield_consistency_relative: float
    top_reaction: float
    bottom_reaction: float
    residual_norm: float
    maximum_alpha: float
    plastic_point_count: int

    @property
    def pass_flag(self) -> bool:
        return bool(
            self.all_values_finite
            and self.alpha_bounded
            and self.alpha_nondecreasing
            and self.free_residual_relative <= EQUILIBRIUM_TOL
            and self.reaction_balance_relative <= EQUILIBRIUM_TOL
            and self.yield_consistency_relative <= YIELD_TOL
        )


@dataclass(frozen=True)
class AttemptResult:
    attempt_id: str
    source_load: float
    target_load: float
    relation: str
    snes_reason: int
    nonlinear_iterations: int
    function_evaluations: int
    residual_sequence_hex: tuple[str, ...]
    selected_primary: np.ndarray
    selected_packet: MaterialFieldPacket
    metrics: MechanicsMetrics
    committed_hash_before: str
    committed_hash_after_callbacks: str

    @property
    def converged(self) -> bool:
        return self.snes_reason > 0


class TransactionalFEHost:
    def __init__(
        self,
        committed: CommittedState,
        persistent: PersistentState | None = None,
        *,
        run_id: str,
        observer_library: pathlib.Path | None = None,
        observer_ledger: pathlib.Path | None = None,
    ) -> None:
        from dolfinx import fem
        from dolfinx.fem.petsc import NonlinearProblem
        from petsc4py import PETSc
        import ufl

        self.context: MeshContext = build_mesh_context()
        if committed.primary.shape != (25,) or committed.gamma_p.shape != (32, 3, 2) or committed.alpha.shape != (32, 3):
            raise ValueError("committed state does not match the frozen P4d topology")
        self.committed = committed
        self.persistent = persistent if persistent is not None else PersistentState()
        self.run_id = run_id
        self.events = EventLedger()
        self.solution = fem.Function(self.context.primary_space, name="w")
        self.solution.x.array[:] = committed.primary
        self.solution.x.scatter_forward()
        self.tau_coefficient = fem.Function(self.context.stress_space, name="tau_trial")
        self.tangent_coefficient = fem.Function(self.context.tangent_space, name="C_alg_trial")
        self.test = ufl.TestFunction(self.context.primary_space)
        self.trial = ufl.TrialFunction(self.context.primary_space)
        measure = ufl.Measure("dx", domain=self.context.domain, metadata={"quadrature_degree": 2})
        self.residual_ufl = ufl.inner(self.tau_coefficient, ufl.grad(self.test)) * measure
        self.jacobian_ufl = ufl.inner(ufl.dot(self.tangent_coefficient, ufl.grad(self.trial)), ufl.grad(self.test)) * measure
        self.bottom_bc = fem.dirichletbc(PETSc.ScalarType(0.0), self.context.bottom_dofs, self.context.primary_space)
        self.top_value = fem.Function(self.context.primary_space, name="top_value")
        self.top_bc = fem.dirichletbc(self.top_value, self.context.top_dofs)
        self.bcs = [self.bottom_bc, self.top_bc]
        self.target_load = committed.accepted_load
        self.relation = "EXACT_CURRENT"
        self.lag_primary = committed.primary.copy()
        self.current_attempt_id = "UNSET"
        self._packet_cache: dict[str, MaterialFieldPacket] = {}
        self._last_packet: MaterialFieldPacket | None = None
        self._residual_sequence: list[str] = []
        self._observer_keepalive = None
        initial_packet = evaluate_material_field(
            self.context,
            committed.primary,
            committed,
            self.persistent,
            committed.accepted_load,
            "EXACT_CURRENT",
        )
        self._activate_packet(initial_packet)
        self.problem = NonlinearProblem(
            self.residual_ufl,
            self.solution,
            bcs=self.bcs,
            J=self.jacobian_ufl,
            petsc_options_prefix=f"p4d2_{run_id}_",
            petsc_options=dict(SNES_OPTIONS),
        )
        self.problem.solver.setFunction(self._assemble_residual, self.problem.b)
        self.problem.solver.setJacobian(self._assemble_jacobian, self.problem.A, self.problem.P_mat)
        self.problem.solver.setMonitor(lambda _s, _i, norm: self._residual_sequence.append(float(norm).hex()))
        self.observer_metadata: dict[str, Any] | None = None
        if observer_library is not None:
            if observer_ledger is None:
                raise ValueError("observer ledger is required with an observer library")
            metadata = attach_observer(
                self.problem.solver,
                observer_library,
                observer_ledger,
                "CMAME-P4D2-C-LEDGER-1.0",
                file_sha256(observer_library),
                run_id,
            )
            self._observer_keepalive = metadata.pop("library_keepalive")
            self.observer_metadata = metadata

    def _set_top_value(self, target_load: float) -> None:
        self.top_value.interpolate(lambda x: target_load * (1.0 + 0.2 * np.sin(math.pi * x[0])))
        self.top_value.x.scatter_forward()

    def _activate_packet(self, packet: MaterialFieldPacket) -> None:
        tau, tangent = representative_cell_coefficients(packet)
        assign_cellwise_vector(self.tau_coefficient, tau)
        assign_cellwise_tensor(self.tangent_coefficient, tangent)
        self._last_packet = packet

    def _packet_key(self, primary: np.ndarray) -> str:
        return canonical_hash({
            "primary": primary,
            "committed": self.committed.full_hash,
            "persistent": self.persistent.projection_hash,
            "target_load": self.target_load,
            "relation": self.relation,
            "lag_primary": self.lag_primary,
        })

    def _prepare_packet(self, x) -> MaterialFieldPacket:
        from dolfinx.fem.petsc import assign

        assign(x, self.solution)
        self.solution.x.scatter_forward()
        primary = self.solution.x.array.copy()
        key = self._packet_key(primary)
        packet = self._packet_cache.get(key)
        if packet is None:
            committed_before = self.committed.full_hash
            packet = evaluate_material_field(
                self.context,
                primary,
                self.committed,
                self.persistent,
                self.target_load,
                self.relation,
                self.lag_primary if self.relation == "DECLARED_ACCEPTED_STATE_LAG" else None,
            )
            if self.committed.full_hash != committed_before:
                raise RuntimeError("TrialEvaluate mutated the committed source")
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

    def _assemble_residual(self, snes, x, b) -> None:
        from dolfinx.fem.petsc import assemble_residual

        packet = self._prepare_packet(x)
        self.events.append(
            "FormResidual",
            solve_id=self.run_id,
            attempt_id=self.current_attempt_id,
            candidate_id=packet.candidate_id,
            primary_vector_hash=packet.primary_hash,
            committed_state_hash=self.committed.full_hash,
            persistent_projection_hash=self.persistent.projection_hash,
            candidate_state_hash=canonical_hash({"gamma_p": packet.gamma_p_candidate, "alpha": packet.alpha_candidate}),
            residual_version=RESIDUAL_VERSION,
            tangent_version=TANGENT_VERSION,
            line_search_lambda=None,
            line_search_reason=None,
            reachable_from_accepted_output=False,
        )
        assemble_residual(self.solution, self.problem.F, self.problem.J, self.bcs, snes, x, b)

    def _assemble_jacobian(self, snes, x, matrix, preconditioner) -> None:
        from dolfinx.fem.petsc import assemble_jacobian

        packet = self._prepare_packet(x)
        current_version = self.committed.accepted_version + 1
        tangent_version = self.committed.accepted_version if self.relation == "DECLARED_ACCEPTED_STATE_LAG" else current_version
        guard = validate_operator_versions(OperatorVersionPacket(
            residual_version=RESIDUAL_VERSION,
            tangent_version=TANGENT_VERSION,
            relation=self.relation,
            residual_state_version=current_version,
            tangent_state_version=tangent_version,
        ))
        self.events.append(
            "FormTangent" if guard.compatible else "RejectVersionMismatch",
            solve_id=self.run_id,
            attempt_id=self.current_attempt_id,
            candidate_id=packet.candidate_id,
            primary_vector_hash=packet.primary_hash,
            committed_state_hash=self.committed.full_hash,
            persistent_projection_hash=self.persistent.projection_hash,
            candidate_state_hash=canonical_hash({"gamma_p": packet.gamma_p_candidate, "alpha": packet.alpha_candidate}),
            residual_version=RESIDUAL_VERSION,
            tangent_version=TANGENT_VERSION,
            operator_version_relation=self.relation,
            line_search_lambda=None,
            line_search_reason=None,
            reachable_from_accepted_output=False,
        )
        if not guard.compatible:
            raise OperatorVersionError(guard.reason)
        assemble_jacobian(self.solution, self.problem.J, self.problem.preconditioner, self.bcs, snes, x, matrix, preconditioner)

    def begin_attempt(self, target_load: float, attempt_id: str, relation: str = "EXACT_CURRENT", maximum_iterations: int = 25) -> None:
        self.target_load = float(target_load)
        self.current_attempt_id = attempt_id
        self.relation = relation
        self.lag_primary = self.committed.primary.copy()
        self._packet_cache.clear()
        self._last_packet = None
        self._residual_sequence.clear()
        self.solution.x.array[:] = self.committed.primary
        self.solution.x.scatter_forward()
        self._set_top_value(self.target_load)
        self.problem.solver.setTolerances(max_it=int(maximum_iterations))
        self.events.append(
            "BeginAttempt",
            solve_id=self.run_id,
            attempt_id=attempt_id,
            source_load=self.committed.accepted_load,
            target_load=self.target_load,
            committed_state_hash=self.committed.full_hash,
            persistent_projection_hash=self.persistent.projection_hash,
            operator_version_relation=relation,
            maximum_iterations=maximum_iterations,
        )

    def solve_attempt(self) -> AttemptResult:
        committed_before = self.committed.full_hash
        self.problem.solve()
        reason = int(self.problem.solver.getConvergedReason())
        selected_primary = self.solution.x.array.copy()
        key = self._packet_key(selected_primary)
        packet = self._packet_cache.get(key)
        if packet is None:
            packet = evaluate_material_field(
                self.context,
                selected_primary,
                self.committed,
                self.persistent,
                self.target_load,
                self.relation,
                self.lag_primary if self.relation == "DECLARED_ACCEPTED_STATE_LAG" else None,
            )
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

    def mechanics_metrics(self, primary: np.ndarray, packet: MaterialFieldPacket) -> MechanicsMetrics:
        from dolfinx import fem

        self._activate_packet(packet)
        raw_residual = fem.assemble_vector(fem.form(self.residual_ufl)).array.copy()
        constrained = np.unique(np.concatenate((self.context.bottom_dofs, self.context.top_dofs))).astype(np.int32)
        free = np.setdiff1d(np.arange(raw_residual.size, dtype=np.int32), constrained)
        free_norm = float(np.linalg.norm(raw_residual[free])) if free.size else 0.0
        top_reaction = float(np.sum(raw_residual[self.context.top_dofs]))
        bottom_reaction = float(np.sum(raw_residual[self.context.bottom_dofs]))
        reaction_scale = max(abs(top_reaction) + abs(bottom_reaction), np.finfo(float).tiny)
        free_relative = free_norm / reaction_scale
        reaction_relative = abs(top_reaction + bottom_reaction) / reaction_scale
        plastic = packet.branch == "PLASTIC"
        if np.any(plastic):
            q = np.linalg.norm(packet.tau[plastic], axis=1)
            strength = TAU_Y0 + HARDENING * packet.alpha_candidate[plastic]
            yield_relative = float(np.max(np.abs(q - strength) / np.maximum(1.0, strength)))
        else:
            yield_relative = 0.0
        arrays = (primary, packet.tau, packet.tangent, packet.gamma_p_candidate, packet.alpha_candidate, raw_residual)
        finite = all(np.isfinite(array).all() and np.max(np.abs(array), initial=0.0) < FINITE_LIMIT for array in arrays)
        return MechanicsMetrics(
            all_values_finite=finite,
            alpha_bounded=bool(np.min(packet.alpha_candidate) >= -1.0e-14),
            alpha_nondecreasing=bool(np.all(packet.alpha_candidate + 1.0e-14 >= self.committed.alpha)),
            free_residual_relative=free_relative,
            reaction_balance_relative=reaction_relative,
            yield_consistency_relative=yield_relative,
            top_reaction=top_reaction,
            bottom_reaction=bottom_reaction,
            residual_norm=float(np.linalg.norm(raw_residual[free])) if free.size else 0.0,
            maximum_alpha=float(np.max(packet.alpha_candidate)),
            plastic_point_count=int(np.count_nonzero(plastic)),
        )

    def commit(self, attempt: AttemptResult) -> CommittedState:
        if not attempt.converged:
            raise RuntimeError("cannot commit a nonconverged SNES attempt")
        if not attempt.metrics.pass_flag:
            raise RuntimeError(f"cannot commit failed mechanics gates: {attempt.metrics}")
        if attempt.committed_hash_before != attempt.committed_hash_after_callbacks or self.committed.full_hash != attempt.committed_hash_before:
            raise RuntimeError("committed state changed before AcceptCommit")
        new_state = CommittedState(
            primary=attempt.selected_primary,
            gamma_p=attempt.selected_packet.gamma_p_candidate,
            alpha=attempt.selected_packet.alpha_candidate,
            accepted_index=self.committed.accepted_index + 1,
            accepted_load=attempt.target_load,
            accepted_version=self.committed.accepted_version + 1,
        )
        self.events.append(
            "AcceptCommit",
            solve_id=self.run_id,
            attempt_id=attempt.attempt_id,
            candidate_id=attempt.selected_packet.candidate_id,
            old_committed_state_hash=self.committed.full_hash,
            committed_state_hash=new_state.full_hash,
            accepted_version=new_state.accepted_version,
            reachable_from_accepted_output=True,
        )
        self.committed = new_state
        return new_state

    def restore_after_failed_attempt(self, attempt: AttemptResult) -> None:
        if attempt.converged:
            raise RuntimeError("restore_after_failed_attempt requires a nonconverged attempt")
        before = self.committed.full_hash
        self.solution.x.array[:] = self.committed.primary
        self.solution.x.scatter_forward()
        self._packet_cache.clear()
        self._last_packet = None
        self.events.append(
            "RollbackOrRetry",
            solve_id=self.run_id,
            attempt_id=attempt.attempt_id,
            primary_vector_hash=canonical_hash(self.committed.primary),
            committed_state_hash=self.committed.full_hash,
            persistent_projection_hash=self.persistent.projection_hash,
            committed_unchanged=before == self.committed.full_hash,
            reachable_from_accepted_output=False,
        )

    def close(self) -> None:
        self._observer_keepalive = None
