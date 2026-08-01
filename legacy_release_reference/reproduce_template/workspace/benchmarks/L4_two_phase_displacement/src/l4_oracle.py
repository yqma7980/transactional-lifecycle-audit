"""Independent Buckley-Leverett entropy and resistance oracle for L4-D1."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import math
from typing import Callable

from .l4_state import TwoPhaseModel


SHOCK_SATURATION = 1.0 / math.sqrt(2.0)
SHOCK_SPEED = (1.0 + math.sqrt(2.0)) / 2.0
BREAKTHROUGH_TIME = 1.0 / SHOCK_SPEED


@dataclass(frozen=True)
class OracleProfile:
    time: float
    cell_count: int
    saturation_n: tuple[float, ...]
    pressure: tuple[float, ...]
    displacement: float
    front_location: float
    maximum_root_residual: float
    maximum_quadrature_error: float


def _fractional_flow(saturation_n: float) -> float:
    numerator = saturation_n * saturation_n
    return numerator / (numerator + (1.0 - saturation_n) ** 2)


def _fractional_flow_derivative(saturation_n: float) -> float:
    denominator = saturation_n**2 + (1.0 - saturation_n) ** 2
    return 2.0 * saturation_n * (1.0 - saturation_n) / denominator**2


def entropy_saturation(x: float, time: float) -> tuple[float, float]:
    if time <= 0.0:
        return (0.0, 0.0)
    similarity = x / time
    if similarity >= SHOCK_SPEED:
        return (0.0, 0.0)
    if similarity <= 0.0:
        return (1.0, 0.0)
    lower = SHOCK_SATURATION
    upper = 1.0
    for _ in range(100):
        middle = 0.5 * (lower + upper)
        derivative = _fractional_flow_derivative(middle)
        if derivative > similarity:
            lower = middle
        else:
            upper = middle
    saturation = 0.5 * (lower + upper)
    return saturation, abs(_fractional_flow_derivative(saturation) - similarity)


def _simpson(function: Callable[[float], float], left: float, right: float) -> float:
    middle = 0.5 * (left + right)
    return (right - left) * (
        function(left) + 4.0 * function(middle) + function(right)
    ) / 6.0


def _adaptive(
    function: Callable[[float], float],
    left: float,
    right: float,
    whole: float,
    tolerance: float,
    depth: int,
) -> tuple[float, float]:
    middle = 0.5 * (left + right)
    left_value = _simpson(function, left, middle)
    right_value = _simpson(function, middle, right)
    difference = left_value + right_value - whole
    estimate = abs(difference) / 15.0
    if depth <= 0 or estimate <= tolerance:
        return left_value + right_value + difference / 15.0, estimate
    value_left, error_left = _adaptive(
        function, left, middle, left_value, 0.5 * tolerance, depth - 1
    )
    value_right, error_right = _adaptive(
        function, middle, right, right_value, 0.5 * tolerance, depth - 1
    )
    return value_left + value_right, error_left + error_right


def _integrate_interval(
    function: Callable[[float], float],
    left: float,
    right: float,
    tolerance: float = 1.0e-13,
) -> tuple[float, float]:
    if right <= left:
        return (0.0, 0.0)
    whole = _simpson(function, left, right)
    return _adaptive(function, left, right, whole, tolerance, 30)


def _integrate_split(
    function: Callable[[float], float],
    left: float,
    right: float,
    time: float,
    tolerance: float = 1.0e-13,
) -> tuple[float, float]:
    shock = SHOCK_SPEED * time
    if left < shock < right:
        left_limit = math.nextafter(shock, left)
        right_limit = math.nextafter(shock, right)
        value_left, error_left = _integrate_interval(
            function, left, left_limit, 0.5 * tolerance
        )
        value_right, error_right = _integrate_interval(
            function, right_limit, right, 0.5 * tolerance
        )
        return value_left + value_right, error_left + error_right
    return _integrate_interval(function, left, right, tolerance)


@lru_cache(maxsize=64)
def oracle_profile(cell_count: int, time: float) -> OracleProfile:
    if cell_count < 2:
        raise ValueError("cell_count must be at least two")
    if not 0.0 < time < BREAKTHROUGH_TIME:
        raise ValueError("oracle profile is frozen to positive pre-breakthrough time")
    model = TwoPhaseModel()
    dx = model.H / cell_count
    root_residuals: list[float] = []

    def saturation_value(x: float) -> float:
        value, residual = entropy_saturation(x, time)
        root_residuals.append(residual)
        return value

    def resistance(x: float) -> float:
        saturation, residual = entropy_saturation(x, time)
        root_residuals.append(residual)
        return model.q_total / (
            model.permeability * model.lambda_total(saturation)
        )

    saturation_averages: list[float] = []
    cell_resistances: list[float] = []
    quadrature_errors: list[float] = []
    for cell in range(cell_count):
        left = cell * dx
        right = (cell + 1) * dx
        saturation_integral, saturation_error = _integrate_split(
            saturation_value, left, right, time
        )
        resistance_integral, resistance_error = _integrate_split(
            resistance, left, right, time
        )
        saturation_averages.append(saturation_integral / dx)
        cell_resistances.append(resistance_integral)
        quadrature_errors.extend((saturation_error, resistance_error))

    pressure = [0.0] * cell_count
    tail = model.pressure_right
    for cell in range(cell_count - 1, -1, -1):
        middle = (cell + 0.5) * dx
        right = (cell + 1.0) * dx
        half_resistance, half_error = _integrate_split(
            resistance, middle, right, time
        )
        pressure[cell] = tail + half_resistance
        tail += cell_resistances[cell]
        quadrature_errors.append(half_error)

    displacement_integral, displacement_error = _integrate_split(
        lambda x: x * resistance(x), 0.0, model.H, time
    )
    quadrature_errors.append(displacement_error)
    return OracleProfile(
        time=time,
        cell_count=cell_count,
        saturation_n=tuple(saturation_averages),
        pressure=tuple(pressure),
        displacement=model.alpha / model.K_d * displacement_integral,
        front_location=SHOCK_SPEED * time,
        maximum_root_residual=max(root_residuals, default=0.0),
        maximum_quadrature_error=max(quadrature_errors, default=0.0),
    )


def analytical_identity() -> dict[str, float]:
    shock_residual = abs(
        _fractional_flow_derivative(SHOCK_SATURATION)
        - _fractional_flow(SHOCK_SATURATION) / SHOCK_SATURATION
    )
    return {
        "shock_saturation": SHOCK_SATURATION,
        "shock_speed": SHOCK_SPEED,
        "breakthrough_time": BREAKTHROUGH_TIME,
        "rankine_hugoniot_characteristic_residual": shock_residual,
    }

