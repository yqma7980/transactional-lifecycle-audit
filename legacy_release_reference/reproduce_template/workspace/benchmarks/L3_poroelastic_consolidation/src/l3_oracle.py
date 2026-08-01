"""Independent Fourier-series oracle for the constrained column."""

from __future__ import annotations

from dataclasses import dataclass
import math

from .l3_state import PoroModel


@dataclass(frozen=True)
class OracleValue:
    value: float
    terms: int
    tail_envelope: float


def _tail_bound(a: float, next_odd: int, coefficient: float) -> float:
    root_a = math.sqrt(a)
    gaussian = math.exp(-a * next_odd * next_odd)
    integral = (
        math.sqrt(math.pi)
        / (2.0 * root_a)
        * math.erfc(root_a * next_odd)
    )
    return coefficient * (gaussian + integral)


def pressure_at(
    model: PoroModel,
    x: float,
    time: float,
    *,
    tolerance: float = 1.0e-15,
    maximum_terms: int = 1000,
) -> OracleValue:
    if not 0.0 <= x <= model.H:
        raise ValueError("x outside domain")
    if time <= 0.0:
        raise ValueError("pointwise oracle requires positive time")
    a = math.pi * math.pi * model.diffusivity * time / (4.0 * model.H**2)
    total = 0.0
    tail = math.inf
    for m in range(maximum_terms):
        odd = 2 * m + 1
        lam = odd * math.pi / (2.0 * model.H)
        total += (
            4.0
            / (odd * math.pi)
            * math.sin(lam * x)
            * math.exp(-model.diffusivity * lam * lam * time)
        )
        tail = _tail_bound(a, odd + 2, 4.0 / math.pi)
        if tail <= tolerance:
            return OracleValue(model.p0 * total, m + 1, model.p0 * tail)
    raise RuntimeError("pressure oracle did not satisfy tail tolerance")


def mean_pressure(
    model: PoroModel,
    time: float,
    *,
    tolerance: float = 1.0e-15,
    maximum_terms: int = 1000,
) -> OracleValue:
    if time <= 0.0:
        raise ValueError("mean oracle requires positive time")
    a = math.pi * math.pi * model.diffusivity * time / (4.0 * model.H**2)
    total = 0.0
    tail = math.inf
    for m in range(maximum_terms):
        odd = 2 * m + 1
        total += (
            8.0
            / (odd * odd * math.pi * math.pi)
            * math.exp(-a * odd * odd)
        )
        tail = _tail_bound(a, odd + 2, 8.0 / (math.pi * math.pi))
        if tail <= tolerance:
            return OracleValue(model.p0 * total, m + 1, model.p0 * tail)
    raise RuntimeError("mean oracle did not satisfy tail tolerance")


def settlement_exact(model: PoroModel, time: float) -> OracleValue:
    mean = mean_pressure(model, time)
    value = model.H * (model.q - model.alpha * mean.value) / model.K_d
    return OracleValue(value, mean.terms, model.H * model.alpha / model.K_d * mean.tail_envelope)


def outflow_exact(model: PoroModel, time: float) -> OracleValue:
    mean = mean_pressure(model, time)
    value = model.H * model.storage_coefficient * (model.p0 - mean.value)
    return OracleValue(value, mean.terms, model.H * model.storage_coefficient * mean.tail_envelope)
