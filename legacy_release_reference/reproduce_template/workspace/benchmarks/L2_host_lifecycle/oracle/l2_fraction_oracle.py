"""Fraction-only equilibrium oracle independent of the runtime implementation."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class OracleCheckpoint:
    force: Fraction
    displacement: Fraction
    stress: Fraction
    epsilon_p: Fraction
    kappa: Fraction


def equilibrium(force: Fraction) -> OracleCheckpoint:
    if force < 0:
        raise ValueError("The frozen D1 oracle covers monotonic tensile loading only")

    E = Fraction(100)
    H = Fraction(10)
    sigma_y = Fraction(1)
    if force <= sigma_y:
        epsilon_p = Fraction(0)
        kappa = Fraction(0)
    else:
        kappa = (force - sigma_y) / H
        epsilon_p = kappa
    displacement = force / E + epsilon_p
    return OracleCheckpoint(
        force=force,
        displacement=displacement,
        stress=force,
        epsilon_p=epsilon_p,
        kappa=kappa,
    )
