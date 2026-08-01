"""L2-D1 material return mapping and one-element operator."""

from __future__ import annotations

import math

from .l2_state import (
    CandidateState,
    CommittedState,
    ElementData,
    ElementResult,
    MaterialData,
    MaterialResult,
    canonical_hash,
)


def evaluate_material(
    epsilon: float,
    committed: CommittedState,
    material: MaterialData,
    *,
    candidate_id: str,
    attempt_id: str,
    source_call_index: int,
    state_version_override: str | None = None,
) -> MaterialResult:
    sigma_trial = material.E * (epsilon - committed.epsilon_p)
    f_trial = abs(sigma_trial) - (material.sigma_y + material.H * committed.kappa)
    if f_trial <= 0.0:
        delta_gamma = 0.0
        sigma = sigma_trial
        E_alg = material.E
        epsilon_p = committed.epsilon_p
        kappa = committed.kappa
    else:
        delta_gamma = f_trial / (material.E + material.H)
        direction = 1.0 if sigma_trial >= 0.0 else -1.0
        sigma = sigma_trial - material.E * delta_gamma * direction
        E_alg = material.E * material.H / (material.E + material.H)
        epsilon_p = committed.epsilon_p + delta_gamma * direction
        kappa = committed.kappa + delta_gamma

    values = (sigma, E_alg, delta_gamma, epsilon_p, kappa)
    if not all(math.isfinite(value) for value in values):
        raise FloatingPointError("Non-finite material result")

    version = state_version_override or f"accepted:{committed.accepted_version}"
    candidate = CandidateState(
        epsilon_p=epsilon_p,
        kappa=kappa,
        candidate_id=candidate_id,
        attempt_id=attempt_id,
        source_call_index=source_call_index,
    )
    return MaterialResult(
        sigma=sigma,
        E_alg=E_alg,
        delta_gamma=delta_gamma,
        candidate=candidate,
        residual_state_version=version,
        tangent_state_version=version,
    )


def evaluate_element(
    variant: object,
    element: ElementData,
    *,
    case_id: str,
    history_id: str,
    configuration_hash: str,
    displacement: float,
    force: float,
    candidate_id: str,
    attempt_id: str,
    source_call_index: int,
) -> ElementResult:
    # Algorithmic history labels are excluded from the physical replay packet.
    del history_id
    if element.area <= 0.0 or element.length <= 0.0:
        raise ValueError("Element area and length must be positive")

    committed = variant.committed
    packet_hash = canonical_hash(
        {
            "design_version": "L2-D1.0",
            "case_id": case_id,
            "variant": variant.name,
            "configuration_hash": configuration_hash,
            "material_hash": variant.material.fingerprint,
            "element_hash": element.fingerprint,
            "committed_hash": committed.fingerprint,
            "accepted_version": committed.accepted_version,
            "displacement": displacement,
            "force": force,
        }
    )
    epsilon = (displacement - element.u1) / element.length
    material_result = variant.evaluate(
        epsilon,
        candidate_id=candidate_id,
        attempt_id=attempt_id,
        source_call_index=source_call_index,
    )
    residual = element.area * material_result.sigma - force
    tangent = element.area * material_result.E_alg / element.length
    result = ElementResult(
        u=displacement,
        force=force,
        epsilon=epsilon,
        residual=residual,
        tangent=tangent,
        material=material_result,
        declared_packet_hash=packet_hash,
    )
    if not all(math.isfinite(value) for value in result.finite_values):
        raise FloatingPointError("Non-finite element result")
    if not result.version_compatible:
        raise RuntimeError("Undeclared residual-tangent version mismatch")
    return result
