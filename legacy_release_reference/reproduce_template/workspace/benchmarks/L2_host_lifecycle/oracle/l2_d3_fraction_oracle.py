"""Independent exact Fraction oracle for the frozen L2-D3 tangent paths.

This module imports no L2 implementation module and performs no work on import.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any


def _evaluate(u: Fraction, force: Fraction) -> dict[str, Fraction]:
    E = Fraction(100)
    sigma_y = Fraction(1)
    H = Fraction(10)
    sigma_trial = E * u
    yield_value = abs(sigma_trial) - sigma_y
    if yield_value <= 0:
        delta_gamma = Fraction(0)
        sigma = sigma_trial
        epsilon_p = Fraction(0)
        kappa = Fraction(0)
        tangent = E
    else:
        delta_gamma = yield_value / (E + H)
        direction = Fraction(1) if sigma_trial >= 0 else Fraction(-1)
        sigma = sigma_trial - E * delta_gamma * direction
        epsilon_p = delta_gamma * direction
        kappa = delta_gamma
        tangent = E * H / (E + H)
    return {
        "u": u,
        "force": force,
        "sigma": sigma,
        "epsilon_p": epsilon_p,
        "kappa": kappa,
        "residual": sigma - force,
        "current_tangent": tangent,
    }


def _path(contract: str) -> tuple[dict[str, Fraction | None], ...]:
    if contract not in {"EXACT_CURRENT", "DECLARED_ONE_ITERATION_LAG"}:
        raise ValueError("Unknown tangent contract")
    force = Fraction(11, 10)
    u = Fraction(0)
    previous_current_tangent = Fraction(100)
    packets: list[dict[str, Fraction | None]] = []
    for _ in range(12):
        evaluated = _evaluate(u, force)
        current = evaluated["current_tangent"]
        used = (
            current
            if contract == "EXACT_CURRENT"
            else previous_current_tangent
        )
        residual = evaluated["residual"]
        correction = None if residual == 0 else -residual / used
        packets.append(
            {
                **evaluated,
                "used_tangent": used,
                "correction": correction,
            }
        )
        if residual == 0:
            return tuple(packets)
        previous_current_tangent = current
        u += correction
    raise RuntimeError("Exact oracle path did not converge")


def _ratio(value: Fraction | None) -> str | None:
    if value is None:
        return None
    return f"{value.numerator}/{value.denominator}"


def _serialize_path(
    packets: tuple[dict[str, Fraction | None], ...],
) -> list[dict[str, str | None]]:
    return [
        {key: _ratio(value) for key, value in packet.items()}
        for packet in packets
    ]


def derive_tangent_path_oracle() -> dict[str, Any]:
    """Return the complete frozen oracle without touching benchmark state."""

    exact = _path("EXACT_CURRENT")
    lagged = _path("DECLARED_ONE_ITERATION_LAG")
    tg03 = _evaluate(Fraction(3, 100), Fraction(1, 2))

    exact_final = exact[-1]
    lagged_final = lagged[-1]
    accepted_equal = all(
        exact_final[key] == lagged_final[key]
        for key in ("u", "force", "sigma", "epsilon_p", "kappa", "residual")
    )
    return {
        "design_version": "L2-D3.0",
        "exact_path": _serialize_path(exact),
        "declared_lagged_path": _serialize_path(lagged),
        "exact_evaluation_count": len(exact),
        "declared_lagged_evaluation_count": len(lagged),
        "accepted_fields_equal": accepted_equal,
        "accepted_state": {
            key: _ratio(exact_final[key])
            for key in ("u", "force", "sigma", "epsilon_p", "kappa")
        },
        "tg03": {
            key: _ratio(tg03[key])
            for key in (
                "u",
                "force",
                "sigma",
                "epsilon_p",
                "kappa",
                "residual",
                "current_tangent",
            )
        },
        "tg03_matched_numeric_delta_residual": "0/1",
        "tg03_matched_numeric_delta_tangent": "0/1",
        "expected_classifications": {
            "L2-TG-01": "PASS_SAME_TRACK_REPEATABILITY",
            "L2-TG-02": "PASS_DECLARED_LAGGED_TANGENT_PARITY",
            "L2-TG-03": "REJECT_VERSION_MISMATCH_BEFORE_LIFECYCLE_VERDICT",
        },
    }
