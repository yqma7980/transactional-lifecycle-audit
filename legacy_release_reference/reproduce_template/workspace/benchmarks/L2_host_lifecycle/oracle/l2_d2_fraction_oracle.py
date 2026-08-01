"""Independent Fraction oracle for the frozen L2-D2 callback histories.

This module derives the expected callback-order observations without importing
the runtime implementation. Importing it performs no derivation or I/O.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any


def _return_map(
    displacement: Fraction,
    epsilon_p: Fraction,
    kappa: Fraction,
) -> dict[str, Fraction]:
    """Evaluate the frozen one-dimensional return map using exact arithmetic."""

    elastic_modulus = Fraction(100)
    hardening_modulus = Fraction(10)
    yield_stress = Fraction(1)
    sigma_trial = elastic_modulus * (displacement - epsilon_p)
    yield_excess = abs(sigma_trial) - (
        yield_stress + hardening_modulus * kappa
    )
    if yield_excess <= 0:
        delta_gamma = Fraction(0)
        sigma = sigma_trial
        tangent = elastic_modulus
        candidate_epsilon_p = epsilon_p
        candidate_kappa = kappa
    else:
        delta_gamma = yield_excess / (elastic_modulus + hardening_modulus)
        direction = Fraction(1) if sigma_trial >= 0 else Fraction(-1)
        sigma = sigma_trial - elastic_modulus * delta_gamma * direction
        tangent = (
            elastic_modulus
            * hardening_modulus
            / (elastic_modulus + hardening_modulus)
        )
        candidate_epsilon_p = epsilon_p + delta_gamma * direction
        candidate_kappa = kappa + delta_gamma
    return {
        "sigma_trial": sigma_trial,
        "yield_excess": yield_excess,
        "delta_gamma": delta_gamma,
        "sigma": sigma,
        "tangent": tangent,
        "candidate_epsilon_p": candidate_epsilon_p,
        "candidate_kappa": candidate_kappa,
    }


def _residual(packet: dict[str, Fraction], force: Fraction) -> Fraction:
    return packet["sigma"] - force


def derive_callback_order_oracle() -> dict[str, Any]:
    """Return exact expectations for CO-01 and CO-02.

    The direct and replay displacement is 1/200, the two inserted trial
    displacements are +3/100 and -3/100, and the external force is 1/2.
    """

    zero = Fraction(0)
    force = Fraction(1, 2)
    replay_u = Fraction(1, 200)
    positive_u = Fraction(3, 100)
    negative_u = Fraction(-3, 100)

    direct = _return_map(replay_u, zero, zero)
    safe_positive = _return_map(positive_u, zero, zero)
    safe_negative = _return_map(negative_u, zero, zero)
    safe_extra_replay = _return_map(replay_u, zero, zero)

    unsafe_positive = _return_map(positive_u, zero, zero)
    unsafe_negative = _return_map(
        negative_u,
        unsafe_positive["candidate_epsilon_p"],
        unsafe_positive["candidate_kappa"],
    )
    unsafe_replay = _return_map(
        replay_u,
        unsafe_negative["candidate_epsilon_p"],
        unsafe_negative["candidate_kappa"],
    )

    direct_residual = _residual(direct, force)
    safe_extra_residual = _residual(safe_extra_replay, force)
    unsafe_extra_residual = _residual(unsafe_replay, force)

    return {
        "inputs": {
            "force": force,
            "replay_u": replay_u,
            "positive_callback_u": positive_u,
            "negative_callback_u": negative_u,
        },
        "direct_replay": {
            **direct,
            "residual": direct_residual,
        },
        "safe_transactional": {
            "positive_callback": safe_positive,
            "negative_callback": safe_negative,
            "extra_replay": {
                **safe_extra_replay,
                "residual": safe_extra_residual,
            },
            "delta_residual": safe_extra_residual - direct_residual,
            "delta_tangent": safe_extra_replay["tangent"] - direct["tangent"],
        },
        "unsafe_trial_cache": {
            "positive_callback": unsafe_positive,
            "negative_callback": unsafe_negative,
            "hidden_after_extra": {
                "epsilon_p": unsafe_negative["candidate_epsilon_p"],
                "kappa": unsafe_negative["candidate_kappa"],
            },
            "extra_replay": {
                **unsafe_replay,
                "residual": unsafe_extra_residual,
            },
            "delta_residual": unsafe_extra_residual - direct_residual,
            "delta_tangent": unsafe_replay["tangent"] - direct["tangent"],
        },
    }

