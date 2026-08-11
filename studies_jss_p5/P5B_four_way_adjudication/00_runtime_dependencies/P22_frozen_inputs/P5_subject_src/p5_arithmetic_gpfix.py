from __future__ import annotations

import numpy as np

from p5_arithmetic import ElementContributionPacket, _shape_gradients
from p5_quadrature_backend_erratum_v2 import reduce_cell_quadrature


def packet_cell_coefficients(context, packet) -> tuple[np.ndarray, np.ndarray]:
    tau = np.asarray(packet.tau, dtype=np.float64)
    tangent = np.asarray(packet.tangent, dtype=np.float64)
    if tau.shape != (32, 3, 2) or tangent.shape != (32, 3, 2, 2):
        raise ValueError(
            "P5 operator packet does not match the frozen 32-cell/3-point topology"
        )
    cell_tau, _ = reduce_cell_quadrature(
        tau,
        context.quadrature_weights,
    )
    cell_tangent, _ = reduce_cell_quadrature(
        tangent,
        context.quadrature_weights,
    )
    return cell_tau, cell_tangent


def build_element_contributions(context, packet) -> ElementContributionPacket:
    cell_tau, cell_tangent = packet_cell_coefficients(context, packet)
    dof_count = int(
        context.primary_space.dofmap.index_map.size_local
        * context.primary_space.dofmap.index_map_bs
    )
    residual_lists: list[list[float]] = [[] for _ in range(dof_count)]
    tangent_lists: list[list[list[float]]] = [
        [[] for _ in range(dof_count)] for _ in range(dof_count)
    ]
    for cell in range(32):
        vertices = np.asarray(context.connectivity[cell], dtype=np.int64)
        coordinates = np.asarray(
            context.coordinates[vertices, :2],
            dtype=np.float64,
        )
        gradients, area = _shape_gradients(coordinates)
        dofs = np.asarray(
            context.primary_space.dofmap.cell_dofs(cell),
            dtype=np.int64,
        )
        if dofs.shape != (3,):
            raise ValueError("P5 expects three scalar P1 dofs per triangle")
        for local_i, global_i in enumerate(dofs):
            residual_lists[int(global_i)].append(
                float(area * np.dot(cell_tau[cell], gradients[local_i]))
            )
            for local_j, global_j in enumerate(dofs):
                value = area * float(
                    gradients[local_i]
                    @ cell_tangent[cell]
                    @ gradients[local_j]
                )
                tangent_lists[int(global_i)][int(global_j)].append(value)
    return ElementContributionPacket(
        residual_terms=tuple(tuple(values) for values in residual_lists),
        tangent_terms=tuple(
            tuple(tuple(values) for values in row)
            for row in tangent_lists
        ),
        dof_count=dof_count,
        cell_count=32,
    )
