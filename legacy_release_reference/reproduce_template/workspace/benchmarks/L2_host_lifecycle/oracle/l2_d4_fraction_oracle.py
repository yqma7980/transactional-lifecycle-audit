"""Independent exact-rational oracle for the frozen L2-D4.0 cases.

This module uses only :class:`fractions.Fraction` and does not import the
benchmark implementation. Importing it does not derive or execute a case.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any


def _material_update(
    epsilon: Fraction,
    epsilon_p: Fraction,
    kappa: Fraction,
) -> dict[str, Fraction]:
    elastic_modulus = Fraction(100, 1)
    yield_stress = Fraction(1, 1)
    hardening = Fraction(10, 1)
    trial_sigma = elastic_modulus * (epsilon - epsilon_p)
    yield_function = abs(trial_sigma) - (yield_stress + hardening * kappa)
    if yield_function <= 0:
        delta_gamma = Fraction(0, 1)
        sigma = trial_sigma
        tangent = elastic_modulus
        candidate_epsilon_p = epsilon_p
        candidate_kappa = kappa
    else:
        delta_gamma = yield_function / (elastic_modulus + hardening)
        direction = Fraction(1, 1) if trial_sigma >= 0 else Fraction(-1, 1)
        sigma = trial_sigma - elastic_modulus * delta_gamma * direction
        tangent = elastic_modulus * hardening / (elastic_modulus + hardening)
        candidate_epsilon_p = epsilon_p + delta_gamma * direction
        candidate_kappa = kappa + delta_gamma
    return {
        "sigma_trial": trial_sigma,
        "yield_function": yield_function,
        "delta_gamma": delta_gamma,
        "sigma": sigma,
        "tangent": tangent,
        "candidate_epsilon_p": candidate_epsilon_p,
        "candidate_kappa": candidate_kappa,
    }


def _text(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def derive_output_provenance_oracle() -> dict[str, Any]:
    """Return the complete exact oracle without touching benchmark state."""

    force = Fraction(1, 2)
    committed_zero = Fraction(0, 1)
    output_seed = _material_update(
        Fraction(3, 100),
        committed_zero,
        committed_zero,
    )
    feedback = _material_update(
        Fraction(1, 200),
        output_seed["candidate_epsilon_p"],
        output_seed["candidate_kappa"],
    )
    direct = _material_update(
        Fraction(1, 200),
        committed_zero,
        committed_zero,
    )
    feedback_residual = feedback["sigma"] - force
    direct_residual = direct["sigma"] - force
    delta_sigma = feedback["sigma"] - direct["sigma"]
    delta_residual = feedback_residual - direct_residual
    delta_tangent = feedback["tangent"] - direct["tangent"]

    return {
        "design_version": "L2-D4.0",
        "L2-OP-01": {
            "trial_candidate_epsilon_p": _text(
                output_seed["candidate_epsilon_p"]
            ),
            "trial_candidate_kappa": _text(output_seed["candidate_kappa"]),
            "output_snapshot_delta": "0/1",
            "committed_state_delta": "0/1",
            "expected_classification": "PASS_ACCEPTED_OUTPUT_PROVENANCE",
        },
        "L2-OP-02": {
            "output_seed": {
                key: _text(value) for key, value in output_seed.items()
            },
            "feedback_replay": {
                **{key: _text(value) for key, value in feedback.items()},
                "residual": _text(feedback_residual),
            },
            "direct_replay": {
                **{key: _text(value) for key, value in direct.items()},
                "residual": _text(direct_residual),
            },
            "delta_sigma": _text(delta_sigma),
            "delta_residual": _text(delta_residual),
            "delta_tangent": _text(delta_tangent),
            "committed_state_delta": "0/1",
            "expected_classification": "DETECT_OUTPUT_FEEDBACK_DRIFT",
        },
    }


__all__ = ["derive_output_provenance_oracle"]
