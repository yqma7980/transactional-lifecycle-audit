from __future__ import annotations

import json
import math
import pathlib
from typing import Any

import numpy as np

from p4d_bridge import attach_observer


def _hex_array(values) -> list[str]:
    return [float(value).hex() for value in np.asarray(values, dtype=np.float64).ravel(order="C")]


def run_dolfinx_owned_zero_case(*, observer_enabled: bool, run_id: str,
                                library_path: pathlib.Path | None = None,
                                ledger_path: pathlib.Path | None = None,
                                observer_build_hash: str | None = None) -> dict[str, Any]:
    from mpi4py import MPI
    import ufl
    from petsc4py import PETSc
    from dolfinx import fem, mesh
    from dolfinx.fem.petsc import NonlinearProblem

    domain = mesh.create_unit_interval(MPI.COMM_WORLD, 1)
    space = fem.functionspace(domain, ("Lagrange", 1))
    solution = fem.Function(space, name="p4d1_zero_solution")
    test = ufl.TestFunction(space)
    trial = ufl.TrialFunction(space)
    residual_form = (solution * solution - 1.0) * test * ufl.dx
    jacobian_form = ufl.derivative(residual_form, solution, trial)

    left_entities = mesh.locate_entities_boundary(domain, 0, lambda x: np.isclose(x[0], 0.0))
    left_dofs = fem.locate_dofs_topological(space, 0, left_entities)
    boundary = fem.dirichletbc(PETSc.ScalarType(0.0), left_dofs, space)
    solution.x.array[:] = 0.1
    solution.x.array[left_dofs] = 0.0
    solution.x.scatter_forward()

    options = {
        "snes_type": "newtonls",
        "snes_linesearch_type": "bt",
        "snes_atol": 1.0e-12,
        "snes_rtol": 1.0e-12,
        "snes_stol": 1.0e-12,
        "snes_max_it": 20,
        "ksp_type": "preonly",
        "pc_type": "lu",
    }
    problem = NonlinearProblem(
        residual_form,
        solution,
        bcs=[boundary],
        J=jacobian_form,
        petsc_options_prefix=f"p4d1_zero_{run_id}_",
        petsc_options=options,
    )
    snes = problem.solver
    residual_norms: list[str] = []

    def python_monitor(_snes, _iteration, norm):
        residual_norms.append(float(norm).hex())

    snes.setMonitor(python_monitor)
    bridge_metadata = None
    bridge_keepalive = None
    if observer_enabled:
        if library_path is None or ledger_path is None or observer_build_hash is None:
            raise ValueError("observer paths and build hash are required")
        bridge_metadata = attach_observer(
            snes,
            library_path,
            ledger_path,
            "CMAME-P4D1-C-LEDGER-1.0",
            observer_build_hash,
            f"P4D1BRIDGE-{run_id}",
        )
        bridge_keepalive = bridge_metadata.pop("library_keepalive")

    problem.solve()
    reason = int(snes.getConvergedReason())
    iterations = int(snes.getIterationNumber())
    function_evaluations = int(snes.getFunctionEvaluations())
    final_values = solution.x.array.copy()
    free_dofs = sorted(set(range(final_values.size)).difference(int(x) for x in left_dofs))
    if len(free_dofs) != 1:
        raise RuntimeError(f"zero case expected one free dof, observed {free_dofs}")
    final_free_value = float(final_values[free_dofs[0]])
    result = {
        "schema_version": "CMAME-P4D1-ZERO-CASE-1.0",
        "preflight_id": "P4D1-BRIDGE-01",
        "run_id": run_id,
        "problem_classification": "NONPHYSICAL_DOLFINX_OWNED_ONE_FREE_DOF_GLOBALIZATION_PROBE",
        "equation": "integral((u^2-1)*v*dx) on one interval with u(0)=0",
        "newton_free_dof_equivalent_equation": "q^2-2=0",
        "observer_enabled": observer_enabled,
        "snes_handle": int(snes.handle),
        "solution_hex": _hex_array(final_values),
        "free_dof_value_hex": final_free_value.hex(),
        "sqrt2_absolute_error_hex": abs(final_free_value - math.sqrt(2.0)).hex(),
        "snes_reason": reason,
        "iteration_count": iterations,
        "function_evaluation_count": function_evaluations,
        "residual_sequence_hex": residual_norms,
        "bridge_metadata": bridge_metadata,
        "all_values_finite": bool(np.isfinite(final_values).all()),
        "mesh_dimension": 1,
        "mesh_cells": 1,
        "finite_element_problem_created": True,
        "physical_result_claimed": False,
    }
    del bridge_keepalive
    return result


def read_c_ledger(path: pathlib.Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def classify_native_nonaccepting_candidate(events: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = [event for event in events if event.get("callback_kind") == "LINE_SEARCH_CANDIDATE"]
    selected = [event for event in events if event.get("callback_kind") == "LINE_SEARCH_SELECTED"]
    unmatched: list[dict[str, Any]] = []
    for candidate in candidates:
        matching = [
            event for event in selected
            if event.get("nonlinear_iteration") == candidate.get("nonlinear_iteration")
        ]
        if matching and all(event.get("W_hex_values") != candidate.get("W_hex_values") for event in matching):
            unmatched.append(candidate)
    return {
        "candidate_event_count": len(candidates),
        "selected_event_count": len(selected),
        "structured_unselected_candidate_count": len(unmatched),
        "structured_unselected_candidate_present": bool(unmatched),
        "first_unselected_candidate": unmatched[0] if unmatched else None,
    }
