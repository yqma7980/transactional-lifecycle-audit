from __future__ import annotations

from fractions import Fraction


def derive_binary_grid() -> list[dict[str, object]]:
    return [
        {"index": index, "exponent": exponent, "eta": Fraction(1, 2 ** (-exponent))}
        for index, exponent in enumerate(range(-48, -5, 3))
    ]


def expected_development_deltas() -> dict[str, list[Fraction]]:
    grid = derive_binary_grid()
    return {
        "F01": [row["eta"] * Fraction(1, 10) for row in grid],
        "F02": [row["eta"] * Fraction(1, 10) for row in grid],
        "F05": [row["eta"] for row in grid],
        "F07": [row["eta"] for row in grid],
    }


def process_budget() -> dict[str, int]:
    return {
        "null_exact_calibration": 6,
        "null_arithmetic_calibration": 6,
        "null_confirmation": 2,
        "per_scaled_family": 15 + 2 + 2,
        "scaled_families": 4,
        "total": 6 + 6 + 2 + 4 * (15 + 2 + 2),
    }
