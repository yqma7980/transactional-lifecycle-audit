from __future__ import annotations

import math
from typing import Any

import numpy as np

from p4d_canonical import canonical_hash
from p4d_material import evaluate_material
from p4d_topology_state import zero_committed_state


def _cell_gradient(coordinates: np.ndarray, values: np.ndarray) -> np.ndarray:
    matrix = np.array(
        [coordinates[1, :2] - coordinates[0, :2], coordinates[2, :2] - coordinates[0, :2]],
        dtype=np.float64,
    )
    differences = np.array([values[1] - values[0], values[2] - values[0]], dtype=np.float64)
    return np.linalg.solve(matrix, differences)


def run_safe_increment_smoke() -> dict[str, Any]:
    from mpi4py import MPI
    import ufl
    from petsc4py import PETSc
    from dolfinx import fem, mesh
    from dolfinx.fem.petsc import NonlinearProblem

    domain = mesh.create_unit_square(
        MPI.COMM_WORLD,
        4,
        4,
        cell_type=mesh.CellType.triangle,
        diagonal=mesh.DiagonalType.right,
    )
    space = fem.functionspace(domain, ("Lagrange", 1))
    solution = fem.Function(space, name="w")
    test = ufl.TestFunction(space)
    trial = ufl.TrialFunction(space)
    shear_modulus = 10.0
    residual_form = shear_modulus * ufl.inner(ufl.grad(solution), ufl.grad(test)) * ufl.dx
    jacobian_form = ufl.derivative(residual_form, solution, trial)
    facet_dimension = domain.topology.dim - 1
    bottom_facets = mesh.locate_entities_boundary(domain, facet_dimension, lambda x: np.isclose(x[1], 0.0))
    top_facets = mesh.locate_entities_boundary(domain, facet_dimension, lambda x: np.isclose(x[1], 1.0))
    bottom_dofs = np.sort(fem.locate_dofs_topological(space, facet_dimension, bottom_facets))
    top_dofs = np.sort(fem.locate_dofs_topological(space, facet_dimension, top_facets))
    bottom_bc = fem.dirichletbc(PETSc.ScalarType(0.0), bottom_dofs, space)
    top_value = fem.Function(space)
    target_load = 0.04
    top_value.interpolate(lambda x: target_load * (1.0 + 0.2 * np.sin(math.pi * x[0])))
    top_bc = fem.dirichletbc(top_value, top_dofs)
    options = {
        "snes_type": "newtonls",
        "snes_linesearch_type": "bt",
        "snes_atol": 1.0e-11,
        "snes_rtol": 1.0e-10,
        "snes_stol": 1.0e-12,
        "snes_max_it": 25,
        "ksp_type": "preonly",
        "pc_type": "lu",
    }
    problem = NonlinearProblem(
        residual_form,
        solution,
        bcs=[bottom_bc, top_bc],
        J=jacobian_form,
        petsc_options_prefix="p4d1_safe_increment_",
        petsc_options=options,
    )
    residual_sequence: list[str] = []
    problem.solver.setMonitor(lambda _snes, _iteration, norm: residual_sequence.append(float(norm).hex()))
    committed = zero_committed_state()
    committed_before_hash = canonical_hash(committed)
    committed_gamma_before = committed.gamma_p.copy()
    committed_alpha_before = committed.alpha.copy()
    event_ledger = [{"ordinal": 1, "event": "BeginIncrement", "source_load": 0.0, "target_load": target_load}]
    problem.solve()
    snes_reason = int(problem.solver.getConvergedReason())
    solution_values = solution.x.array.copy()
    event_ledger.append({"ordinal": 2, "event": "SolveCompleted", "snes_reason": snes_reason})

    domain.topology.create_connectivity(domain.topology.dim, 0)
    connectivity = domain.topology.connectivity(domain.topology.dim, 0).array.reshape(-1, 3)
    candidates_gamma = np.empty_like(committed.gamma_p)
    candidates_alpha = np.empty_like(committed.alpha)
    maximum_tau_norm = 0.0
    branches = set()
    for cell in range(connectivity.shape[0]):
        dofs = space.dofmap.cell_dofs(cell)
        coordinates = domain.geometry.x[connectivity[cell]]
        gradient = _cell_gradient(coordinates, solution_values[dofs])
        for point in range(3):
            material = evaluate_material(gradient, committed.gamma_p[cell, point], committed.alpha[cell, point])
            candidates_gamma[cell, point] = material.candidate.gamma_p
            candidates_alpha[cell, point] = material.candidate.alpha
            maximum_tau_norm = max(maximum_tau_norm, float(np.linalg.norm(material.tau)))
            branches.add(material.branch)
    committed_immutable_pre_accept = bool(
        np.array_equal(committed.gamma_p, committed_gamma_before)
        and np.array_equal(committed.alpha, committed_alpha_before)
    )
    candidate_id = canonical_hash(
        {
            "source_committed_hash": committed_before_hash,
            "solution": solution_values,
            "gamma_p": candidates_gamma,
            "alpha": candidates_alpha,
            "residual_version": "P4D1-R-EXACT-CURRENT-V1",
            "tangent_version": "P4D1-J-EXACT-CURRENT-V1",
        }
    )
    event_ledger.append({"ordinal": 3, "event": "CandidateBuilt", "candidate_id": candidate_id})

    raw_residual = fem.assemble_vector(fem.form(residual_form)).array.copy()
    constrained = set(int(value) for value in np.concatenate((bottom_dofs, top_dofs)))
    free = np.array(sorted(set(range(raw_residual.size)).difference(constrained)), dtype=np.int32)
    free_residual_norm = float(np.linalg.norm(raw_residual[free])) if free.size else 0.0
    reaction_scale = max(float(np.sum(np.abs(raw_residual[list(constrained)]))), np.finfo(float).tiny)
    free_residual_relative = free_residual_norm / reaction_scale
    reaction_balance_relative = abs(float(np.sum(raw_residual))) / reaction_scale
    mechanics_gate = bool(
        snes_reason > 0
        and np.isfinite(solution_values).all()
        and np.isfinite(raw_residual).all()
        and np.all(candidates_alpha >= 0.0)
        and committed_immutable_pre_accept
        and free_residual_relative <= 1.0e-10
        and reaction_balance_relative <= 1.0e-10
        and branches == {"ELASTIC"}
    )
    if not mechanics_gate:
        raise RuntimeError(
            f"safe increment mechanics gate failed: reason={snes_reason}, free={free_residual_relative}, "
            f"reaction={reaction_balance_relative}, branches={branches}"
        )
    event_ledger.append({"ordinal": 4, "event": "MechanicsGatesPassed", "candidate_id": candidate_id})
    accepted_gamma = candidates_gamma.copy()
    accepted_alpha = candidates_alpha.copy()
    accepted_version = 1
    committed_after_hash = canonical_hash(
        {"gamma_p": accepted_gamma, "alpha": accepted_alpha, "accepted_version": accepted_version}
    )
    event_ledger.append({"ordinal": 5, "event": "AcceptCommit", "candidate_id": candidate_id, "accepted_version": accepted_version})
    accepted_output = {
        "source_event": "AcceptCommit",
        "source_candidate_id": candidate_id,
        "accepted_version": accepted_version,
        "committed_state_hash": committed_after_hash,
        "solution_hash": canonical_hash(solution_values),
        "target_load": target_load,
    }
    event_ledger.append({"ordinal": 6, "event": "OutputAcceptedState", "candidate_id": candidate_id})
    return {
        "schema_version": "CMAME-P4D1-SAFE-SMOKE-1.0",
        "preflight_id": "P4D1-SMOKE-01",
        "history": "H_DIRECT",
        "source_load": 0.0,
        "target_load": target_load,
        "accepted_increment_count": 1,
        "snes_reason": snes_reason,
        "snes_iterations": int(problem.solver.getIterationNumber()),
        "residual_sequence_hex": residual_sequence,
        "solution_hash": canonical_hash(solution_values),
        "committed_before_hash": committed_before_hash,
        "committed_after_hash": committed_after_hash,
        "committed_immutable_pre_accept": committed_immutable_pre_accept,
        "candidate_id": candidate_id,
        "accepted_output": accepted_output,
        "event_ledger": event_ledger,
        "accepted_output_after_commit": event_ledger[-1]["ordinal"] > event_ledger[-2]["ordinal"],
        "accepted_output_candidate_matches": accepted_output["source_candidate_id"] == candidate_id,
        "minimum_alpha_hex": float(np.min(accepted_alpha)).hex(),
        "maximum_alpha_hex": float(np.max(accepted_alpha)).hex(),
        "maximum_tau_norm_hex": maximum_tau_norm.hex(),
        "material_branches": sorted(branches),
        "free_dof_residual_relative_hex": free_residual_relative.hex(),
        "reaction_balance_relative_hex": reaction_balance_relative.hex(),
        "residual_version": "P4D1-R-EXACT-CURRENT-V1",
        "tangent_version": "P4D1-J-EXACT-CURRENT-V1",
        "operator_version_relation": "EXACT_CURRENT",
        "all_values_finite": bool(np.isfinite(solution_values).all() and np.isfinite(raw_residual).all()),
        "mechanics_gate_pass": mechanics_gate,
        "continued_to_next_load": False,
        "formal_case_run": False,
    }
