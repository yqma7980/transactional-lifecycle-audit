from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from p4d_canonical import canonical_hash
from p4d_material import evaluate_material


@dataclass(frozen=True)
class CommittedState:
    gamma_p: np.ndarray
    alpha: np.ndarray
    accepted_version: int


def zero_committed_state() -> CommittedState:
    return CommittedState(
        gamma_p=np.zeros((32, 3, 2), dtype=np.float64),
        alpha=np.zeros((32, 3), dtype=np.float64),
        accepted_version=0,
    )


def build_topology_packet() -> tuple[dict[str, Any], Any, Any]:
    from mpi4py import MPI
    import basix
    from dolfinx import fem, mesh

    domain = mesh.create_unit_square(
        MPI.COMM_WORLD,
        4,
        4,
        cell_type=mesh.CellType.triangle,
        diagonal=mesh.DiagonalType.right,
    )
    topology_dimension = domain.topology.dim
    domain.topology.create_connectivity(topology_dimension, 0)
    connectivity = domain.topology.connectivity(topology_dimension, 0)
    cell_vertices = connectivity.array.reshape(-1, 3).copy()
    coordinates = domain.geometry.x.copy()
    space = fem.functionspace(domain, ("Lagrange", 1))
    facet_dimension = topology_dimension - 1
    bottom_facets = mesh.locate_entities_boundary(domain, facet_dimension, lambda x: np.isclose(x[1], 0.0))
    top_facets = mesh.locate_entities_boundary(domain, facet_dimension, lambda x: np.isclose(x[1], 1.0))
    bottom_dofs = np.sort(fem.locate_dofs_topological(space, facet_dimension, bottom_facets))
    top_dofs = np.sort(fem.locate_dofs_topological(space, facet_dimension, top_facets))
    quadrature_points, quadrature_weights = basix.make_quadrature(basix.CellType.triangle, 2)
    committed = zero_committed_state()
    packet = {
        "schema_version": "CMAME-P4D1-TOPOLOGY-1.0",
        "preflight_id": "P4D1-TOPOLOGY-01",
        "coordinates": coordinates,
        "connectivity": cell_vertices,
        "cell_order": np.arange(cell_vertices.shape[0], dtype=np.int64),
        "bottom_dof_order": bottom_dofs,
        "top_dof_order": top_dofs,
        "quadrature_points": np.asarray(quadrature_points, dtype=np.float64),
        "quadrature_weights": np.asarray(quadrature_weights, dtype=np.float64),
        "committed_gamma_p": committed.gamma_p,
        "committed_alpha": committed.alpha,
        "accepted_version": committed.accepted_version,
        "material_parameters": {"G": 10.0, "tau_y0": 1.0, "H": 2.0},
    }
    hashes = {
        "coordinates_sha256": canonical_hash(coordinates),
        "connectivity_sha256": canonical_hash(cell_vertices),
        "cell_order_sha256": canonical_hash(packet["cell_order"]),
        "boundary_dof_order_sha256": canonical_hash({"bottom": bottom_dofs, "top": top_dofs}),
        "quadrature_sha256": canonical_hash({"points": packet["quadrature_points"], "weights": packet["quadrature_weights"]}),
        "material_packet_sha256": canonical_hash(packet["material_parameters"]),
        "committed_state_sha256": canonical_hash(committed),
    }
    packet["hashes"] = hashes
    packet["counts"] = {
        "cells": int(cell_vertices.shape[0]),
        "nodes": int(coordinates.shape[0]),
        "quadrature_points_per_cell": int(quadrature_points.shape[0]),
        "integration_points": int(cell_vertices.shape[0] * quadrature_points.shape[0]),
    }

    before_gamma = committed.gamma_p.copy()
    before_alpha = committed.alpha.copy()
    local_candidate = evaluate_material(np.array([0.2, 0.0]), committed.gamma_p[0, 0], committed.alpha[0, 0])
    packet["trial_candidate_local"] = {
        "gamma_p": local_candidate.candidate.gamma_p,
        "alpha": local_candidate.candidate.alpha,
        "branch": local_candidate.branch,
    }
    packet["committed_immutable_after_trial"] = bool(
        np.array_equal(committed.gamma_p, before_gamma) and np.array_equal(committed.alpha, before_alpha)
    )
    packet["topology_gate_pass"] = bool(
        cell_vertices.shape == (32, 3)
        and coordinates.shape[0] == 25
        and quadrature_points.shape == (3, 2)
        and committed.gamma_p.shape == (32, 3, 2)
        and committed.alpha.shape == (32, 3)
        and packet["committed_immutable_after_trial"]
    )
    return packet, domain, space
