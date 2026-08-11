from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np


PATH_IDS = (
    "ARITH_A_REFERENCE",
    "ARITH_B_CALIBRATION",
    "ARITH_C_CONFIRMATION",
    "ARITH_D_P6_BENIGN",
)


@dataclass(frozen=True)
class ElementContributionPacket:
    residual_terms: tuple[tuple[float, ...], ...]
    tangent_terms: tuple[tuple[tuple[float, ...], ...], ...]
    dof_count: int
    cell_count: int


@dataclass(frozen=True)
class ReducedOperator:
    path_id: str
    residual: np.ndarray
    tangent: np.ndarray


def _balanced(values: list[float]) -> float:
    work = list(values)
    while len(work) > 1:
        work = [work[i] + work[i + 1] for i in range(0, len(work) - 1, 2)] + ([work[-1]] if len(work) % 2 else [])
    return work[0]


def reduce_values(values: Iterable[float], path_id: str) -> float:
    data = [float(item) for item in values]
    if not data:
        return 0.0
    if path_id == "ARITH_A_REFERENCE":
        total = 0.0
        for item in data:
            total += item
        return total
    if path_id == "ARITH_B_CALIBRATION":
        blocks = [data[index:index + 8] for index in range(0, len(data), 8)]
        total = 0.0
        for block in blocks:
            subtotal = 0.0
            for item in reversed(block):
                subtotal += item
            total += subtotal
        return total
    if path_id == "ARITH_C_CONFIRMATION":
        return _balanced(data)
    if path_id == "ARITH_D_P6_BENIGN":
        return _balanced(data[1::2] + data[0::2])
    raise ValueError(f"unknown arithmetic path {path_id}")


def _shape_gradients(coordinates: np.ndarray) -> tuple[np.ndarray, float]:
    matrix = np.asarray(
        [coordinates[1, :2] - coordinates[0, :2], coordinates[2, :2] - coordinates[0, :2]],
        dtype=np.float64,
    )
    determinant = float(np.linalg.det(matrix))
    area = abs(determinant) / 2.0
    if not np.isfinite(area) or area <= 0.0:
        raise ValueError("degenerate triangle in P5 element contribution packet")
    gradients = np.empty((3, 2), dtype=np.float64)
    for local in range(3):
        values = np.zeros(3, dtype=np.float64)
        values[local] = 1.0
        gradients[local] = np.linalg.solve(matrix, np.array([values[1] - values[0], values[2] - values[0]]))
    return gradients, area


def build_element_contributions(context, packet) -> ElementContributionPacket:
    tau = np.asarray(packet.tau, dtype=np.float64)
    tangent = np.asarray(packet.tangent, dtype=np.float64)
    if tau.shape != (32, 3, 2) or tangent.shape != (32, 3, 2, 2):
        raise ValueError("P5 operator packet does not match the frozen 32-cell/3-point topology")
    if not np.all(tau == tau[:, :1, :]) or not np.all(tangent == tangent[:, :1, :, :]):
        raise ValueError("P1 cell quadrature packets must be cellwise constant")
    dof_count = int(context.primary_space.dofmap.index_map.size_local * context.primary_space.dofmap.index_map_bs)
    residual_lists: list[list[float]] = [[] for _ in range(dof_count)]
    tangent_lists: list[list[list[float]]] = [[[] for _ in range(dof_count)] for _ in range(dof_count)]
    for cell in range(32):
        vertices = np.asarray(context.connectivity[cell], dtype=np.int64)
        coordinates = np.asarray(context.coordinates[vertices, :2], dtype=np.float64)
        gradients, area = _shape_gradients(coordinates)
        dofs = np.asarray(context.primary_space.dofmap.cell_dofs(cell), dtype=np.int64)
        if dofs.shape != (3,):
            raise ValueError("P5 expects three scalar P1 dofs per triangle")
        cell_tau = tau[cell, 0]
        cell_tangent = tangent[cell, 0]
        for local_i, global_i in enumerate(dofs):
            residual_lists[int(global_i)].append(float(area * np.dot(cell_tau, gradients[local_i])))
            for local_j, global_j in enumerate(dofs):
                value = area * float(gradients[local_i] @ cell_tangent @ gradients[local_j])
                tangent_lists[int(global_i)][int(global_j)].append(value)
    return ElementContributionPacket(
        residual_terms=tuple(tuple(values) for values in residual_lists),
        tangent_terms=tuple(tuple(tuple(values) for values in row) for row in tangent_lists),
        dof_count=dof_count,
        cell_count=32,
    )


def reduce_operator(contributions: ElementContributionPacket, path_id: str) -> ReducedOperator:
    if path_id not in PATH_IDS:
        raise ValueError(f"unknown arithmetic path {path_id}")
    residual = np.array([reduce_values(values, path_id) for values in contributions.residual_terms], dtype=np.float64)
    tangent = np.array(
        [[reduce_values(values, path_id) for values in row] for row in contributions.tangent_terms],
        dtype=np.float64,
    )
    if not np.isfinite(residual).all() or not np.isfinite(tangent).all():
        raise ValueError("non-finite P5 reduced operator")
    return ReducedOperator(path_id, residual, tangent)


def synthetic_triangle_packet() -> ElementContributionPacket:
    residual = (
        (1.0e16, 1.0, -1.0e16, 3.0),
        (-2.0, 2.0),
        (0.5,),
    )
    tangent = tuple(
        tuple((float(i + j + 1), -float(i + j + 1), 1.0e-16) for j in range(3))
        for i in range(3)
    )
    return ElementContributionPacket(residual, tangent, 3, 1)
