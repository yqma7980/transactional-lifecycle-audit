from __future__ import annotations

import math
from typing import Any

import numpy as np

from p4d_config import G, SNES_OPTIONS


def run_reference_level(cells_per_side: int) -> dict[str, Any]:
    from mpi4py import MPI
    import ufl
    from petsc4py import PETSc
    from dolfinx import fem, mesh
    from dolfinx.fem.petsc import NonlinearProblem

    domain = mesh.create_unit_square(
        MPI.COMM_WORLD,
        cells_per_side,
        cells_per_side,
        cell_type=mesh.CellType.triangle,
        diagonal=mesh.DiagonalType.right,
    )
    space = fem.functionspace(domain, ("Lagrange", 1))
    solution = fem.Function(space, name="w_reference")
    test = ufl.TestFunction(space)
    trial = ufl.TrialFunction(space)
    coordinate = ufl.SpatialCoordinate(domain)
    exact = 1.0e-3 * ufl.sin(ufl.pi * coordinate[0]) * ufl.sin(ufl.pi * coordinate[1])
    forcing = 2.0 * G * ufl.pi**2 * exact
    residual = (G * ufl.inner(ufl.grad(solution), ufl.grad(test)) - forcing * test) * ufl.dx
    jacobian = ufl.derivative(residual, solution, trial)
    facet_dimension = domain.topology.dim - 1
    boundary_facets = mesh.locate_entities_boundary(
        domain,
        facet_dimension,
        lambda x: np.ones(x.shape[1], dtype=bool),
    )
    boundary_dofs = np.sort(fem.locate_dofs_topological(space, facet_dimension, boundary_facets))
    exact_function = fem.Function(space)
    exact_function.interpolate(lambda x: 1.0e-3 * np.sin(math.pi * x[0]) * np.sin(math.pi * x[1]))
    boundary = fem.dirichletbc(exact_function, boundary_dofs)
    options = dict(SNES_OPTIONS)
    problem = NonlinearProblem(
        residual,
        solution,
        bcs=[boundary],
        J=jacobian,
        petsc_options_prefix=f"p4d2_ref_{cells_per_side}_",
        petsc_options=options,
    )
    residual_sequence: list[str] = []
    problem.solver.setMonitor(lambda _s, _i, norm: residual_sequence.append(float(norm).hex()))
    problem.solve()
    reason = int(problem.solver.getConvergedReason())
    error = solution - exact
    exact_l2_sq = fem.assemble_scalar(fem.form(exact**2 * ufl.dx))
    error_l2_sq = fem.assemble_scalar(fem.form(error**2 * ufl.dx))
    exact_h1_sq = fem.assemble_scalar(fem.form(ufl.inner(ufl.grad(exact), ufl.grad(exact)) * ufl.dx))
    error_h1_sq = fem.assemble_scalar(fem.form(ufl.inner(ufl.grad(error), ufl.grad(error)) * ufl.dx))
    relative_l2 = math.sqrt(float(error_l2_sq) / float(exact_l2_sq))
    relative_h1 = math.sqrt(float(error_h1_sq) / float(exact_h1_sq))
    values = solution.x.array.copy()
    return {
        "cells_per_side": cells_per_side,
        "cell_count": 2 * cells_per_side * cells_per_side,
        "dof_count": int(values.size),
        "h": 1.0 / cells_per_side,
        "snes_reason": reason,
        "nonlinear_iterations": int(problem.solver.getIterationNumber()),
        "residual_sequence_hex": residual_sequence,
        "relative_l2_error": relative_l2,
        "relative_h1_error": relative_h1,
        "all_values_finite": bool(np.isfinite(values).all()),
        "pass_positive_reason": reason > 0,
    }


def classify_reference(levels: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(levels, key=lambda item: item["cells_per_side"])
    h = np.array([item["h"] for item in ordered], dtype=np.float64)
    l2 = np.array([item["relative_l2_error"] for item in ordered], dtype=np.float64)
    h1 = np.array([item["relative_h1_error"] for item in ordered], dtype=np.float64)
    l2_order = float(np.polyfit(np.log(h), np.log(l2), 1)[0])
    h1_order = float(np.polyfit(np.log(h), np.log(h1), 1)[0])
    monotone_l2 = bool(np.all(np.diff(l2) < 0.0))
    monotone_h1 = bool(np.all(np.diff(h1) < 0.0))
    pass_flag = bool(
        all(item["pass_positive_reason"] and item["all_values_finite"] for item in ordered)
        and monotone_l2
        and monotone_h1
        and l2_order >= 1.70
        and h1_order >= 0.80
        and l2[-1] <= 5.0e-2
        and h1[-1] <= 2.0e-1
    )
    return {
        "levels": ordered,
        "fitted_relative_l2_order": l2_order,
        "fitted_relative_h1_order": h1_order,
        "monotone_relative_l2": monotone_l2,
        "monotone_relative_h1": monotone_h1,
        "finest_relative_l2_error": float(l2[-1]),
        "finest_relative_h1_error": float(h1[-1]),
        "primary_verdict": "REFERENCE_GATE_PASS" if pass_flag else "REFERENCE_GATE_FAIL",
        "pass_flag": pass_flag,
    }


def execute_reference_case() -> dict[str, Any]:
    return classify_reference([run_reference_level(level) for level in (4, 8, 16)])
