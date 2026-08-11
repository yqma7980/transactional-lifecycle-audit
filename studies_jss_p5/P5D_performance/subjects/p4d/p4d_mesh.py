from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from p4d_canonical import canonical_hash
from p4d_config import G, HARDENING, TAU_Y0


@dataclass(frozen=True)
class MeshContext:
    domain: Any
    primary_space: Any
    stress_space: Any
    tangent_space: Any
    coordinates: np.ndarray
    connectivity: np.ndarray
    bottom_dofs: np.ndarray
    top_dofs: np.ndarray
    quadrature_points: np.ndarray
    quadrature_weights: np.ndarray
    hashes: dict[str, str]


def build_mesh_context(nx: int = 4, ny: int = 4) -> MeshContext:
    from mpi4py import MPI
    import basix
    from dolfinx import fem, mesh

    domain = mesh.create_unit_square(
        MPI.COMM_WORLD,
        nx,
        ny,
        cell_type=mesh.CellType.triangle,
        diagonal=mesh.DiagonalType.right,
    )
    dimension = domain.topology.dim
    domain.topology.create_connectivity(dimension, 0)
    connectivity = domain.topology.connectivity(dimension, 0).array.reshape(-1, 3).copy()
    coordinates = domain.geometry.x.copy()
    primary_space = fem.functionspace(domain, ("Lagrange", 1))
    stress_space = fem.functionspace(domain, ("DG", 0, (2,)))
    tangent_space = fem.functionspace(domain, ("DG", 0, (2, 2)))
    facet_dimension = dimension - 1
    bottom_facets = mesh.locate_entities_boundary(domain, facet_dimension, lambda x: np.isclose(x[1], 0.0))
    top_facets = mesh.locate_entities_boundary(domain, facet_dimension, lambda x: np.isclose(x[1], 1.0))
    bottom_dofs = np.sort(fem.locate_dofs_topological(primary_space, facet_dimension, bottom_facets))
    top_dofs = np.sort(fem.locate_dofs_topological(primary_space, facet_dimension, top_facets))
    quadrature_points, quadrature_weights = basix.make_quadrature(basix.CellType.triangle, 2)
    q_points = np.asarray(quadrature_points, dtype=np.float64)
    q_weights = np.asarray(quadrature_weights, dtype=np.float64)
    hashes = {
        "coordinates": canonical_hash(coordinates),
        "connectivity": canonical_hash(connectivity),
        "cell_order": canonical_hash(np.arange(connectivity.shape[0], dtype=np.int64)),
        "boundary_dof_order": canonical_hash({"bottom": bottom_dofs, "top": top_dofs}),
        "quadrature_rule": canonical_hash({"points": q_points, "weights": q_weights}),
        "material": canonical_hash({"G": G, "tau_y0": TAU_Y0, "H": HARDENING}),
    }
    expected = (32, 25, 3, 96) if (nx, ny) == (4, 4) else None
    observed = (connectivity.shape[0], coordinates.shape[0], q_points.shape[0], connectivity.shape[0] * q_points.shape[0])
    if expected is not None and observed != expected:
        raise RuntimeError(f"frozen topology mismatch: expected {expected}, observed {observed}")
    return MeshContext(
        domain=domain,
        primary_space=primary_space,
        stress_space=stress_space,
        tangent_space=tangent_space,
        coordinates=coordinates,
        connectivity=connectivity,
        bottom_dofs=bottom_dofs,
        top_dofs=top_dofs,
        quadrature_points=q_points,
        quadrature_weights=q_weights,
        hashes=hashes,
    )


def cell_gradients(context: MeshContext, primary_values: np.ndarray) -> np.ndarray:
    gradients = np.empty((context.connectivity.shape[0], 2), dtype=np.float64)
    for cell in range(context.connectivity.shape[0]):
        vertices = context.connectivity[cell]
        coordinates = context.coordinates[vertices, :2]
        dofs = context.primary_space.dofmap.cell_dofs(cell)
        values = np.asarray(primary_values[dofs], dtype=np.float64)
        matrix = np.array(
            [coordinates[1] - coordinates[0], coordinates[2] - coordinates[0]],
            dtype=np.float64,
        )
        gradients[cell] = np.linalg.solve(matrix, np.array([values[1] - values[0], values[2] - values[0]]))
    return gradients


def assign_cellwise_vector(function, values: np.ndarray) -> None:
    block_size = int(function.function_space.dofmap.index_map_bs)
    if block_size != values.shape[1]:
        raise ValueError(f"vector block mismatch: {block_size} != {values.shape[1]}")
    for cell in range(values.shape[0]):
        dof = int(function.function_space.dofmap.cell_dofs(cell)[0])
        function.x.array[dof * block_size:(dof + 1) * block_size] = values[cell]
    function.x.scatter_forward()


def assign_cellwise_tensor(function, values: np.ndarray) -> None:
    block_size = int(function.function_space.dofmap.index_map_bs)
    flattened = values.reshape(values.shape[0], -1)
    if block_size != flattened.shape[1]:
        raise ValueError(f"tensor block mismatch: {block_size} != {flattened.shape[1]}")
    for cell in range(flattened.shape[0]):
        dof = int(function.function_space.dofmap.cell_dofs(cell)[0])
        function.x.array[dof * block_size:(dof + 1) * block_size] = flattened[cell]
    function.x.scatter_forward()
