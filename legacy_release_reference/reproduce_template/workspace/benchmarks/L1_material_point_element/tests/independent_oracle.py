"""Fraction-only oracle independent of the runtime return-mapping module."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class OracleState:
    epsilon_p: Fraction = Fraction(0)
    kappa: Fraction = Fraction(0)


@dataclass(frozen=True)
class OracleResult:
    sigma: Fraction
    E_alg: Fraction
    delta_gamma: Fraction
    state: OracleState
    plastic_dissipation: Fraction


def update(epsilon: Fraction, state: OracleState) -> OracleResult:
    E = Fraction(100)
    H = Fraction(10)
    sigma_y = Fraction(1)
    sigma_trial = E * (epsilon - state.epsilon_p)
    f_trial = abs(sigma_trial) - (sigma_y + H * state.kappa)
    if f_trial <= 0:
        return OracleResult(
            sigma=sigma_trial,
            E_alg=E,
            delta_gamma=Fraction(0),
            state=state,
            plastic_dissipation=Fraction(0),
        )
    delta_gamma = f_trial / (E + H)
    direction = Fraction(1) if sigma_trial >= 0 else Fraction(-1)
    next_state = OracleState(
        epsilon_p=state.epsilon_p + delta_gamma * direction,
        kappa=state.kappa + delta_gamma,
    )
    sigma = sigma_trial - E * delta_gamma * direction
    mean_yield = sigma_y + H * (state.kappa + next_state.kappa) / 2
    return OracleResult(
        sigma=sigma,
        E_alg=E * H / (E + H),
        delta_gamma=delta_gamma,
        state=next_state,
        plastic_dissipation=mean_yield * delta_gamma,
    )


def accepted_path(strains: list[Fraction]) -> list[OracleResult]:
    state = OracleState()
    results: list[OracleResult] = []
    for epsilon in strains:
        result = update(epsilon, state)
        results.append(result)
        state = result.state
    return results

