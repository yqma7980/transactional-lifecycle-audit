"""Pure runtime return mapping for the L1 material point."""

from __future__ import annotations

import math

from .l1_state import CandidateState, CommittedState, MaterialData, MaterialResult


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
        epsilon_p = committed.epsilon_p + delta_gamma * direction
        kappa = committed.kappa + delta_gamma
        E_alg = material.E * material.H / (material.E + material.H)

    values = (sigma, E_alg, delta_gamma, epsilon_p, kappa)
    if not all(math.isfinite(value) for value in values):
        raise FloatingPointError("Non-finite constitutive output")

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


def incremental_plastic_dissipation(
    committed: CommittedState,
    candidate: CandidateState,
    material: MaterialData,
) -> float:
    delta_kappa = candidate.kappa - committed.kappa
    if delta_kappa <= 0.0:
        return 0.0
    mean_yield = material.sigma_y + 0.5 * material.H * (
        committed.kappa + candidate.kappa
    )
    return mean_yield * delta_kappa

