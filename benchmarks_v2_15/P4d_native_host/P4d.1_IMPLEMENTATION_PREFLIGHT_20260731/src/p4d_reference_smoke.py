from __future__ import annotations

import math
from typing import Any

import numpy as np


def run_manufactured_reference_smoke() -> dict[str, Any]:
    from mpi4py import MPI
    import ufl
    from petsc4py import PETSc
    from dolfinx import fem, mesh
    from dolfinx.fem.petsc import LinearProblem

    n = 4
    shear_modulus = 10.0
    amplitude = 1.0e-3
    domain = mesh.create_unit_square(
        MPI.COMM_WORLD,
        n,
        n,
        cell_type=mesh.CellType.triangle,
        diagonal=mesh.DiagonalType.right,
    )
    space = fem.functionspace(domain, ("Lagrange", 1))
    trial = ufl.TrialFunction(space)
    test = ufl.TestFunction(space)
    x = ufl.SpatialCoordinate(domain)
    exact = amplitude * ufl.sin(ufl.pi * x[0]) * ufl.sin(ufl.pi * x[1])
    forcing = 2.0 * shear_modulus * ufl.pi**2 * exact
    bilinear = shear_modulus * ufl.inner(ufl.grad(trial), ufl.grad(test)) * ufl.dx
    linear = forcing * test * ufl.dx
    facets = mesh.locate_entities_boundary(
        domain,
        domain.topology.dim - 1,
        lambda points: np.full(points.shape[1], True, dtype=bool),
    )
    dofs = fem.locate_dofs_topological(space, domain.topology.dim - 1, facets)
    boundary = fem.dirichletbc(PETSc.ScalarType(0.0), dofs, space)
    problem = LinearProblem(
        bilinear,
        linear,
        bcs=[boundary],
        petsc_options_prefix="p4d1_manufactured_",
        petsc_options={"ksp_type": "preonly", "pc_type": "lu"},
    )
    numerical = problem.solve()
    l2_error_sq = fem.assemble_scalar(fem.form((numerical - exact) ** 2 * ufl.dx))
    l2_reference_sq = fem.assemble_scalar(fem.form(exact**2 * ufl.dx))
    h1_error_sq = fem.assemble_scalar(fem.form(ufl.inner(ufl.grad(numerical - exact), ufl.grad(numerical - exact)) * ufl.dx))
    h1_reference_sq = fem.assemble_scalar(fem.form(ufl.inner(ufl.grad(exact), ufl.grad(exact)) * ufl.dx))
    l2_error_sq = MPI.COMM_WORLD.allreduce(l2_error_sq, op=MPI.SUM)
    l2_reference_sq = MPI.COMM_WORLD.allreduce(l2_reference_sq, op=MPI.SUM)
    h1_error_sq = MPI.COMM_WORLD.allreduce(h1_error_sq, op=MPI.SUM)
    h1_reference_sq = MPI.COMM_WORLD.allreduce(h1_reference_sq, op=MPI.SUM)
    relative_l2 = math.sqrt(l2_error_sq / l2_reference_sq)
    relative_h1 = math.sqrt(h1_error_sq / h1_reference_sq)
    values = numerical.x.array.copy()
    return {
        "schema_version": "CMAME-P4D1-MANUFACTURED-1.0",
        "preflight_id": "P4D1-ORACLE-01",
        "mesh_level": n,
        "cells": int(domain.topology.index_map(domain.topology.dim).size_global),
        "nodes": int(domain.geometry.index_map().size_global),
        "relative_L2_error_hex": relative_l2.hex(),
        "relative_H1_error_hex": relative_h1.hex(),
        "solution_max_abs_hex": float(np.max(np.abs(values))).hex(),
        "all_values_finite": bool(np.isfinite(values).all() and math.isfinite(relative_l2) and math.isfinite(relative_h1)),
        "formal_convergence_sequence_run": False,
        "formal_threshold_applied": False,
    }
