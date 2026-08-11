from __future__ import annotations

import math
from typing import Any

import numpy as np

from p4d_canonical import canonical_hash
from p4d_config import SNES_OPTIONS
from p4d_host import AttemptResult, TransactionalFEHost
from p4d_material import evaluate_material
from p4d_mesh import assign_cellwise_tensor, assign_cellwise_vector, build_mesh_context, cell_gradients
from p4d_state import CommittedState, MaterialFieldPacket, PersistentState


class NullEventLedger:
    def append(self, _event_kind: str, **_fields: Any) -> dict[str, Any]:
        return {}

    @property
    def records(self) -> list[dict[str, Any]]:
        return []

    def candidate_is_reachable(self, _candidate_id: str) -> bool:
        return False


def evaluate_dynamic_material_field(
    context,
    primary_values: np.ndarray,
    committed: CommittedState,
    persistent: PersistentState,
    target_load: float,
    relation: str,
    lag_primary_values: np.ndarray | None = None,
) -> MaterialFieldPacket:
    primary = np.asarray(primary_values, dtype=np.float64)
    gradients = cell_gradients(context, primary)
    lag_primary = primary if lag_primary_values is None else np.asarray(lag_primary_values, dtype=np.float64)
    lag_gradients = cell_gradients(context, lag_primary)
    cell_count = int(context.connectivity.shape[0])
    point_count = int(context.quadrature_points.shape[0])
    tau = np.empty((cell_count, point_count, 2), dtype=np.float64)
    tangent = np.empty((cell_count, point_count, 2, 2), dtype=np.float64)
    candidate_gamma_p = np.empty((cell_count, point_count, 2), dtype=np.float64)
    candidate_alpha = np.empty((cell_count, point_count), dtype=np.float64)
    branches = np.empty((cell_count, point_count), dtype="U7")
    yield_function = np.empty((cell_count, point_count), dtype=np.float64)
    delta_lambda = np.empty((cell_count, point_count), dtype=np.float64)
    effective_gamma_p = committed.gamma_p + persistent.hidden_trial_cache

    for cell in range(cell_count):
        for point in range(point_count):
            current = evaluate_material(
                gradients[cell], effective_gamma_p[cell, point], committed.alpha[cell, point]
            )
            tau[cell, point] = current.tau
            candidate_gamma_p[cell, point] = current.candidate.gamma_p
            candidate_alpha[cell, point] = current.candidate.alpha
            branches[cell, point] = current.branch
            yield_function[cell, point] = current.yield_function
            delta_lambda[cell, point] = current.delta_lambda
            if relation == "DECLARED_ACCEPTED_STATE_LAG":
                lagged = evaluate_material(
                    lag_gradients[cell], effective_gamma_p[cell, point], committed.alpha[cell, point]
                )
                tangent[cell, point] = lagged.tangent
            else:
                tangent[cell, point] = current.tangent

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


class DynamicTransactionalFEHost(TransactionalFEHost):
    """P4d equations with a frozen 4x4 or 8x8 topology and audit-only ledger switch."""

    def __init__(self, *, nx: int, ny: int, run_id: str, capture_ledger: bool) -> None:
        from dolfinx import fem
        from dolfinx.fem.petsc import NonlinearProblem
        from petsc4py import PETSc
        import ufl

        self.context = build_mesh_context(nx=nx, ny=ny)
        cell_count = int(self.context.connectivity.shape[0])
        point_count = int(self.context.quadrature_points.shape[0])
        primary_size = int(self.context.primary_space.dofmap.index_map.size_local)
        self.committed = CommittedState(
            primary=np.zeros(primary_size, dtype=np.float64),
            gamma_p=np.zeros((cell_count, point_count, 2), dtype=np.float64),
            alpha=np.zeros((cell_count, point_count), dtype=np.float64),
            accepted_index=0,
            accepted_load=0.0,
            accepted_version=0,
        )
        self.persistent = PersistentState(
            hidden_trial_cache=np.zeros((cell_count, point_count, 2), dtype=np.float64),
            mutation_count=0,
        )
        self.run_id = run_id
        if capture_ledger:
            from p4d_state import EventLedger

            self.events = EventLedger()
        else:
            self.events = NullEventLedger()
        self.production_trial_evaluations = 0
        self.production_residual_evaluations = 0
        self.production_tangent_evaluations = 0
        self.solution = fem.Function(self.context.primary_space, name="w")
        self.solution.x.array[:] = self.committed.primary
        self.solution.x.scatter_forward()
        self.tau_coefficient = fem.Function(self.context.stress_space, name="tau_trial")
        self.tangent_coefficient = fem.Function(self.context.tangent_space, name="C_alg_trial")
        self.test = ufl.TestFunction(self.context.primary_space)
        self.trial = ufl.TrialFunction(self.context.primary_space)
        measure = ufl.Measure("dx", domain=self.context.domain, metadata={"quadrature_degree": 2})
        self.residual_ufl = ufl.inner(self.tau_coefficient, ufl.grad(self.test)) * measure
        self.jacobian_ufl = ufl.inner(
            ufl.dot(self.tangent_coefficient, ufl.grad(self.trial)), ufl.grad(self.test)
        ) * measure
        self.bottom_bc = fem.dirichletbc(
            PETSc.ScalarType(0.0), self.context.bottom_dofs, self.context.primary_space
        )
        self.top_value = fem.Function(self.context.primary_space, name="top_value")
        self.top_bc = fem.dirichletbc(self.top_value, self.context.top_dofs)
        self.bcs = [self.bottom_bc, self.top_bc]
        self.target_load = 0.0
        self.relation = "EXACT_CURRENT"
        self.lag_primary = self.committed.primary.copy()
        self.current_attempt_id = "UNSET"
        self._packet_cache: dict[str, MaterialFieldPacket] = {}
        self._last_packet: MaterialFieldPacket | None = None
        self._residual_sequence: list[str] = []
        self._observer_keepalive = None
        initial_packet = self._evaluate_primary(self.committed.primary)
        self._activate_packet(initial_packet)
        options = dict(SNES_OPTIONS)
        self.problem = NonlinearProblem(
            self.residual_ufl,
            self.solution,
            bcs=self.bcs,
            J=self.jacobian_ufl,
            petsc_options_prefix="p5d_",
            petsc_options=options,
        )
        self.problem.solver.setFunction(self._assemble_residual, self.problem.b)
        self.problem.solver.setJacobian(
            self._assemble_jacobian, self.problem.A, self.problem.P_mat
        )
        self.problem.solver.setMonitor(
            lambda _s, _i, norm: self._residual_sequence.append(float(norm).hex())
        )
        self.observer_metadata = None

    def _evaluate_primary(self, primary: np.ndarray) -> MaterialFieldPacket:
        return evaluate_dynamic_material_field(
            self.context,
            primary,
            self.committed,
            self.persistent,
            self.target_load,
            self.relation,
            self.lag_primary if self.relation == "DECLARED_ACCEPTED_STATE_LAG" else None,
        )

    def _activate_packet(self, packet: MaterialFieldPacket) -> None:
        if not np.all(packet.tau == packet.tau[:, :1, :]):
            raise RuntimeError("P1 quadrature stress packets are nonidentical")
        if not np.all(packet.tangent == packet.tangent[:, :1, :, :]):
            raise RuntimeError("P1 quadrature tangent packets are nonidentical")
        assign_cellwise_vector(self.tau_coefficient, packet.tau[:, 0, :])
        assign_cellwise_tensor(self.tangent_coefficient, packet.tangent[:, 0, :, :])
        self._last_packet = packet

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
            self.production_trial_evaluations += 1
            if self.committed.full_hash != committed_before:
                raise RuntimeError("TrialEvaluate mutated committed state")
            self._packet_cache[key] = packet
            self.events.append(
                "TrialEvaluate",
                candidate_id=packet.candidate_id,
                committed_state_hash=packet.committed_hash,
                persistent_projection_hash=packet.persistent_hash,
                residual_version=packet.residual_version,
                tangent_version=packet.tangent_version,
                reachable_from_accepted_output=False,
            )
        self._activate_packet(packet)
        return packet

    def _assemble_residual(self, snes, x, b) -> None:
        self.production_residual_evaluations += 1
        super()._assemble_residual(snes, x, b)

    def _assemble_jacobian(self, snes, x, matrix, preconditioner) -> None:
        self.production_tangent_evaluations += 1
        super()._assemble_jacobian(snes, x, matrix, preconditioner)

    def solve_attempt(self) -> AttemptResult:
        committed_before = self.committed.full_hash
        self.problem.solve()
        reason = int(self.problem.solver.getConvergedReason())
        selected_primary = self.solution.x.array.copy()
        key = self._packet_key(selected_primary)
        packet = self._packet_cache.get(key)
        if packet is None:
            packet = self._evaluate_primary(selected_primary)
            self.production_trial_evaluations += 1
            self._packet_cache[key] = packet
            self._activate_packet(packet)
        metrics = self.mechanics_metrics(selected_primary, packet)
        committed_after = self.committed.full_hash
        self.events.append(
            "SolveCompleted",
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

