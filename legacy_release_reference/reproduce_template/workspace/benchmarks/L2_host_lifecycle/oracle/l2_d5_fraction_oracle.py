"""Independent exact-rational oracle for L2-D5.0a.

The oracle deliberately does not import the benchmark implementation. It
defines the analytical accepted states; byte-level runtime fingerprints are a
separate IEEE-754 contract verified by the implementation tests.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any


def _text(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def _evaluate(
    displacement: Fraction,
    force: Fraction,
    epsilon_p_before: Fraction,
    kappa_before: Fraction,
) -> dict[str, Fraction]:
    elastic_modulus = Fraction(100, 1)
    yield_stress = Fraction(1, 1)
    hardening = Fraction(10, 1)
    trial_sigma = elastic_modulus * (displacement - epsilon_p_before)
    yield_function = abs(trial_sigma) - (yield_stress + hardening * kappa_before)
    if yield_function <= 0:
        sigma = trial_sigma
        tangent = elastic_modulus
        epsilon_p_after = epsilon_p_before
        kappa_after = kappa_before
    else:
        delta_gamma = yield_function / (elastic_modulus + hardening)
        direction = Fraction(1, 1) if trial_sigma >= 0 else Fraction(-1, 1)
        sigma = trial_sigma - elastic_modulus * delta_gamma * direction
        tangent = elastic_modulus * hardening / (elastic_modulus + hardening)
        epsilon_p_after = epsilon_p_before + delta_gamma * direction
        kappa_after = kappa_before + delta_gamma
    return {
        "force": force,
        "displacement": displacement,
        "reaction": sigma,
        "stress": sigma,
        "epsilon_p": epsilon_p_after,
        "kappa": kappa_after,
        "residual": sigma - force,
        "tangent": tangent,
    }


def _accepted_state(
    force: Fraction,
    epsilon_p_before: Fraction,
    kappa_before: Fraction,
) -> dict[str, Fraction]:
    displacement = Fraction(0, 1)
    for _ in range(12):
        packet = _evaluate(
            displacement,
            force,
            epsilon_p_before,
            kappa_before,
        )
        if packet["residual"] == 0:
            return packet
        displacement -= packet["residual"] / packet["tangent"]
    raise RuntimeError("Exact checkpoint oracle did not converge")


def derive_checkpoint_provenance_oracle() -> dict[str, Any]:
    """Return exact checkpoint and continuation values without host execution."""

    checkpoint = _accepted_state(
        Fraction(11, 10), Fraction(0, 1), Fraction(0, 1)
    )
    continuation = _accepted_state(
        Fraction(6, 5), checkpoint["epsilon_p"], checkpoint["kappa"]
    )
    state_fields = (
        "force",
        "displacement",
        "reaction",
        "stress",
        "epsilon_p",
        "kappa",
    )
    return {
        "design_version": "L2-D5.0a",
        "case_id": "L2-CP-01",
        "checkpoint": {
            key: _text(checkpoint[key]) for key in state_fields
        },
        "continuation": {
            key: _text(continuation[key]) for key in state_fields
        },
        "expected_deltas": {
            "displacement": "0/1",
            "reaction": "0/1",
            "stress": "0/1",
            "epsilon_p": "0/1",
            "kappa": "0/1",
        },
        "expected_versions": {"checkpoint": 1, "continuation": 2},
        "expected_classification": "PASS_CHECKPOINT_ROUND_TRIP",
        "claim_boundary": (
            "Exact analytical state only; runtime IEEE-754 fingerprints and "
            "checkpoint bytes are implementation evidence, not Fraction results."
        ),
    }


__all__ = ["derive_checkpoint_provenance_oracle"]
