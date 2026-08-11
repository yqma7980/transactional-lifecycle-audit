from __future__ import annotations

import numpy as np

from p5_fe_adapter import P5TransactionalFEHost
from p4d_mesh import assign_cellwise_tensor, assign_cellwise_vector


IMPLEMENTATION_REVISION = "CMAME-P5.2a-FE-GP-INTEGRATION"
HOST_REVISION = "P4D-DOLFINX-PETSC-HOST-1.0+P5-AUDIT-ADAPTER-1.0a"


def reduce_cell_quadrature(
    values: np.ndarray,
    weights: np.ndarray,
) -> tuple[np.ndarray, str]:
    array = np.asarray(values, dtype=np.float64)
    quadrature_weights = np.asarray(weights, dtype=np.float64)
    if array.ndim < 2:
        raise ValueError("quadrature values require cell and point axes")
    if quadrature_weights.ndim != 1 or array.shape[1] != quadrature_weights.size:
        raise ValueError("quadrature weight count does not match the point axis")
    if not np.isfinite(array).all() or not np.isfinite(quadrature_weights).all():
        raise ValueError("quadrature reduction requires finite values and weights")
    weight_sum = float(np.sum(quadrature_weights))
    if weight_sum <= 0.0:
        raise ValueError("quadrature weights must have a positive sum")

    first = array[:, :1, ...]
    if np.all(array == first):
        return array[:, 0, ...].copy(), "IDENTICAL_GP_FAST_PATH"

    normalized = quadrature_weights / weight_sum
    reduced = np.tensordot(array, normalized, axes=([1], [0]))
    # tensordot appends the surviving value axes after the cell axis.
    return np.asarray(reduced, dtype=np.float64), "WEIGHTED_GP_REDUCTION"


class P5QuadratureAwareFEHost(P5TransactionalFEHost):
    def _activate_packet(self, packet) -> None:
        tau, tau_mode = reduce_cell_quadrature(
            packet.tau,
            self.context.quadrature_weights,
        )
        tangent, tangent_mode = reduce_cell_quadrature(
            packet.tangent,
            self.context.quadrature_weights,
        )
        assign_cellwise_vector(self.tau_coefficient, tau)
        assign_cellwise_tensor(self.tangent_coefficient, tangent)
        self._last_packet = packet
        self._p5_quadrature_reduction_mode = {
            "tau": tau_mode,
            "tangent": tangent_mode,
        }
