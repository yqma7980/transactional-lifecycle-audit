"""Conservative cell-centred finite-volume solver for L3-D1."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

from .l3_canonical import canonical_hash

from .l3_oracle import mean_pressure, pressure_at, settlement_exact
from .l3_state import (
    CommittedState,
    PoroModel,
    TrialCandidate,
    initial_state,
    settlement,
)


@dataclass(frozen=True)
class FieldMetrics:
    pressure_l2_relative: float
    pressure_linf_absolute: float
    settlement_absolute: float
    oracle_tail_envelope: float


def cell_centres(model: PoroModel, cell_count: int) -> tuple[float, ...]:
    dx = model.H / cell_count
    return tuple((index + 0.5) * dx for index in range(cell_count))


def thomas_solve(
    lower: list[float],
    diagonal: list[float],
    upper: list[float],
    rhs: list[float],
) -> tuple[float, ...]:
    n = len(diagonal)
    if not (len(lower) == len(upper) == n - 1 and len(rhs) == n):
        raise ValueError("invalid tridiagonal dimensions")
    c = upper.copy()
    d = rhs.copy()
    b = diagonal.copy()
    for index in range(1, n):
        if abs(b[index - 1]) <= 1.0e-300:
            raise ArithmeticError("zero tridiagonal pivot")
        factor = lower[index - 1] / b[index - 1]
        b[index] -= factor * c[index - 1]
        d[index] -= factor * d[index - 1]
    result = [0.0] * n
    result[-1] = d[-1] / b[-1]
    for index in range(n - 2, -1, -1):
        result[index] = (d[index] - c[index] * result[index + 1]) / b[index]
    return tuple(result)


def solve_pressure_step(
    model: PoroModel,
    previous_pressure: tuple[float, ...],
    dt: float,
) -> tuple[float, ...]:
    if dt <= 0.0:
        raise ValueError("dt must be positive")
    n = len(previous_pressure)
    dx = model.H / n
    mass = model.storage_coefficient * dx / dt
    conductance = model.mobility / dx
    lower = [-conductance] * (n - 1)
    upper = [-conductance] * (n - 1)
    diagonal = [mass + 2.0 * conductance] * n
    diagonal[0] = mass + 3.0 * conductance
    diagonal[-1] = mass + conductance
    rhs = [mass * value for value in previous_pressure]
    return thomas_solve(lower, diagonal, upper, rhs)


def make_candidate(
    model: PoroModel,
    committed: CommittedState,
    dt: float,
    *,
    attempt_id: str,
    previous_override: tuple[float, ...] | None = None,
) -> TrialCandidate:
    previous = committed.pressure if previous_override is None else previous_override
    if len(previous) != len(committed.pressure):
        raise ValueError("previous-state size mismatch")
    pressure = solve_pressure_step(model, previous, dt)
    dx = model.H / len(pressure)
    flux = 2.0 * model.mobility * pressure[0] / dx
    outflow_increment = flux * dt
    source_change = model.storage_coefficient * dx * sum(
        new - old for new, old in zip(pressure, previous)
    )
    declared_change = model.storage_coefficient * dx * sum(
        new - old for new, old in zip(pressure, committed.pressure)
    )
    return TrialCandidate(
        attempt_id=attempt_id,
        dt=dt,
        time=committed.time + dt,
        pressure=pressure,
        boundary_flux=flux,
        outflow_increment=outflow_increment,
        cumulative_outflow=committed.cumulative_outflow + outflow_increment,
        storage_change_from_source=source_change,
        internal_mass_defect=source_change + outflow_increment,
        declared_storage_change=declared_change,
        declared_mass_defect=declared_change + outflow_increment,
        source_state_hash=canonical_hash(previous),
        declared_committed_hash=committed.fingerprint,
    )


def accept_candidate(
    committed: CommittedState,
    candidate: TrialCandidate,
) -> CommittedState:
    return CommittedState(
        time=candidate.time,
        pressure=candidate.pressure,
        cumulative_outflow=candidate.cumulative_outflow,
        accepted_version=committed.accepted_version + 1,
    )


def run_constant_step(
    model: PoroModel,
    cell_count: int,
    dt: float,
    end_time: float,
) -> tuple[CommittedState, tuple[TrialCandidate, ...]]:
    state = initial_state(model, cell_count)
    candidates: list[TrialCandidate] = []
    tolerance = 1.0e-13 * max(1.0, end_time)
    while state.time < end_time - tolerance:
        step = min(dt, end_time - state.time)
        candidate = make_candidate(
            model,
            state,
            step,
            attempt_id=f"step-{state.accepted_version + 1}",
        )
        state = accept_candidate(state, candidate)
        candidates.append(candidate)
    return state, tuple(candidates)


def field_metrics(model: PoroModel, state: CommittedState) -> FieldMetrics:
    exact = [pressure_at(model, x, state.time) for x in cell_centres(model, len(state.pressure))]
    differences = [value - oracle.value for value, oracle in zip(state.pressure, exact)]
    numerator = math.sqrt(sum(value * value for value in differences))
    denominator = math.sqrt(sum(oracle.value * oracle.value for oracle in exact))
    numerical_settlement = settlement(model, state.pressure)
    exact_settlement = settlement_exact(model, state.time)
    return FieldMetrics(
        pressure_l2_relative=numerator / denominator,
        pressure_linf_absolute=max(abs(value) for value in differences),
        settlement_absolute=abs(numerical_settlement - exact_settlement.value),
        oracle_tail_envelope=max(
            max(oracle.tail_envelope for oracle in exact),
            exact_settlement.tail_envelope,
        ),
    )


def cumulative_mass_defect(model: PoroModel, state: CommittedState) -> float:
    dx = model.H / len(state.pressure)
    storage_release = model.storage_coefficient * dx * sum(
        model.p0 - value for value in state.pressure
    )
    return state.cumulative_outflow - storage_release


def normalized(value: float, *scales: float) -> float:
    return abs(value) / max(1.0e-30, *(abs(item) for item in scales))


def pressure_l2_drift(left: Iterable[float], right: Iterable[float]) -> float:
    pairs = tuple(zip(left, right))
    return math.sqrt(sum((a - b) ** 2 for a, b in pairs) / len(pairs))


def all_finite(limit: float, *groups: Iterable[float]) -> bool:
    return all(
        math.isfinite(value) and abs(value) <= limit
        for group in groups
        for value in group
    )
