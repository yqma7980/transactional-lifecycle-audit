from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class MaterialParameters:
    shear_modulus: float = 10.0
    yield_stress: float = 1.0
    hardening_modulus: float = 2.0


@dataclass(frozen=True)
class MaterialCandidate:
    gamma_p: np.ndarray
    alpha: float


@dataclass(frozen=True)
class MaterialPacket:
    tau: np.ndarray
    tangent: np.ndarray
    candidate: MaterialCandidate
    yield_function: float
    delta_lambda: float
    branch: str


def evaluate_material(gamma: np.ndarray, committed_gamma_p: np.ndarray,
                      committed_alpha: float,
                      parameters: MaterialParameters = MaterialParameters()) -> MaterialPacket:
    gamma = np.asarray(gamma, dtype=np.float64)
    gamma_p = np.asarray(committed_gamma_p, dtype=np.float64)
    trial_tau = parameters.shear_modulus * (gamma - gamma_p)
    trial_norm = float(np.linalg.norm(trial_tau))
    yield_function = trial_norm - (parameters.yield_stress + parameters.hardening_modulus * committed_alpha)
    if yield_function <= 0.0 or trial_norm == 0.0:
        return MaterialPacket(
            tau=trial_tau.copy(),
            tangent=parameters.shear_modulus * np.eye(2),
            candidate=MaterialCandidate(gamma_p.copy(), float(committed_alpha)),
            yield_function=yield_function,
            delta_lambda=0.0,
            branch="ELASTIC",
        )
    direction = trial_tau / trial_norm
    delta_lambda = yield_function / (parameters.shear_modulus + parameters.hardening_modulus)
    candidate_gamma_p = gamma_p + delta_lambda * direction
    candidate_alpha = float(committed_alpha + delta_lambda)
    tau = parameters.shear_modulus * (gamma - candidate_gamma_p)
    tangent = (
        parameters.shear_modulus * np.eye(2)
        - parameters.shear_modulus**2 / (parameters.shear_modulus + parameters.hardening_modulus)
        * np.outer(direction, direction)
        - parameters.shear_modulus**2 * delta_lambda / trial_norm
        * (np.eye(2) - np.outer(direction, direction))
    )
    return MaterialPacket(
        tau=tau,
        tangent=tangent,
        candidate=MaterialCandidate(candidate_gamma_p, candidate_alpha),
        yield_function=yield_function,
        delta_lambda=float(delta_lambda),
        branch="PLASTIC",
    )


def stress_only(gamma: np.ndarray, committed_gamma_p: np.ndarray,
                committed_alpha: float,
                parameters: MaterialParameters = MaterialParameters()) -> np.ndarray:
    return evaluate_material(gamma, committed_gamma_p, committed_alpha, parameters).tau
