from __future__ import annotations

import numpy as np

from p4d_canonical import canonical_hash
from p4d_material import evaluate_material
from p4d_mesh import MeshContext, cell_gradients
from p4d_state import CommittedState, MaterialFieldPacket, PersistentState


def evaluate_material_field(
    context: MeshContext,
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
    tau = np.empty((32, 3, 2), dtype=np.float64)
    tangent = np.empty((32, 3, 2, 2), dtype=np.float64)
    candidate_gamma_p = np.empty((32, 3, 2), dtype=np.float64)
    candidate_alpha = np.empty((32, 3), dtype=np.float64)
    branches = np.empty((32, 3), dtype="U7")
    yield_function = np.empty((32, 3), dtype=np.float64)
    delta_lambda = np.empty((32, 3), dtype=np.float64)
    effective_gamma_p = committed.gamma_p + persistent.hidden_trial_cache

    for cell in range(32):
        for point in range(3):
            current = evaluate_material(gradients[cell], effective_gamma_p[cell, point], committed.alpha[cell, point])
            tau[cell, point] = current.tau
            candidate_gamma_p[cell, point] = current.candidate.gamma_p
            candidate_alpha[cell, point] = current.candidate.alpha
            branches[cell, point] = current.branch
            yield_function[cell, point] = current.yield_function
            delta_lambda[cell, point] = current.delta_lambda
            if relation == "DECLARED_ACCEPTED_STATE_LAG":
                lagged = evaluate_material(lag_gradients[cell], effective_gamma_p[cell, point], committed.alpha[cell, point])
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


def representative_cell_coefficients(packet: MaterialFieldPacket) -> tuple[np.ndarray, np.ndarray]:
    if not np.all(packet.tau == packet.tau[:, :1, :]):
        raise RuntimeError("P1 cell quadrature stress packets are unexpectedly nonidentical")
    if not np.all(packet.tangent == packet.tangent[:, :1, :, :]):
        raise RuntimeError("P1 cell quadrature tangent packets are unexpectedly nonidentical")
    return packet.tau[:, 0, :].copy(), packet.tangent[:, 0, :, :].copy()
