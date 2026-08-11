"""Conservative finite-volume update and accepted observables for L4-D1."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

from .l4_oracle import OracleProfile
from .l4_state import (
    canonical_hash,
    AcceptedSnapshot,
    CommittedState,
    TrialCandidate,
    TwoPhaseModel,
    initial_state,
    phase_mass_n,
    phase_mass_w,
)


@dataclass(frozen=True)
class FieldMetrics:
    saturation_l1_absolute: float
    saturation_l2_absolute: float
    pressure_l2_relative: float
    pressure_linf_absolute: float
    displacement_absolute: float
    front_absolute: float
    oracle_root_residual: float
    oracle_quadrature_error: float


def pressure_from_saturation(
    model: TwoPhaseModel, saturation_n: Iterable[float]
) -> tuple[float, ...]:
    values = tuple(saturation_n)
    dx = model.H / len(values)
    resistance = tuple(
        model.q_total / (model.permeability * model.lambda_total(value))
        for value in values
    )
    pressure = [0.0] * len(values)
    tail = model.pressure_right
    for cell in range(len(values) - 1, -1, -1):
        pressure[cell] = tail + 0.5 * dx * resistance[cell]
        tail += dx * resistance[cell]
    return tuple(pressure)


def one_way_displacement(model: TwoPhaseModel, pressure: Iterable[float]) -> float:
    values = tuple(pressure)
    return model.alpha / model.K_d * model.H * sum(values) / len(values)


def front_location(saturation_n: Iterable[float], length: float = 1.0) -> float:
    values = tuple(saturation_n)
    threshold = 0.5 / math.sqrt(2.0)
    dx = length / len(values)
    for index in range(len(values) - 1):
        left = values[index]
        right = values[index + 1]
        if left >= threshold > right:
            x_left = (index + 0.5) * dx
            if left == right:
                return x_left
            return x_left + (threshold - left) * dx / (right - left)
    return 0.0 if values[0] < threshold else length


def make_snapshot(model: TwoPhaseModel, state: CommittedState) -> AcceptedSnapshot:
    pressure = pressure_from_saturation(model, state.saturation_n)
    return AcceptedSnapshot(
        time=state.time,
        saturation_n=state.saturation_n,
        pressure=pressure,
        displacement=one_way_displacement(model, pressure),
        phase_mass_n=phase_mass_n(model, state.saturation_n),
        phase_mass_w=phase_mass_w(model, state.saturation_n),
        front_location=front_location(state.saturation_n, model.H),
        accepted_version=state.accepted_version,
        committed_hash=state.fingerprint,
    )


def make_candidate(
    model: TwoPhaseModel,
    committed: CommittedState,
    dt: float,
    *,
    attempt_id: str,
    previous_override: tuple[float, ...] | None = None,
) -> TrialCandidate:
    if dt <= 0.0:
        raise ValueError("dt must be positive")
    source = previous_override if previous_override is not None else committed.saturation_n
    if len(source) != len(committed.saturation_n):
        raise ValueError("source and committed field sizes differ")
    dx = model.H / len(source)
    ratio = dt * model.q_total / (model.phi * dx)
    left_flux_n = 1.0
    updated: list[float] = []
    for value in source:
        right_flux_n = model.fractional_flow_n(value)
        updated.append(value - ratio * (right_flux_n - left_flux_n))
        left_flux_n = right_flux_n
    saturation = tuple(updated)
    flux_n_in = model.q_total
    flux_n_out = model.q_total * left_flux_n
    flux_w_in = 0.0
    flux_w_out = model.q_total * (1.0 - left_flux_n)

    source_n = phase_mass_n(model, source)
    source_w = phase_mass_w(model, source)
    declared_n = phase_mass_n(model, committed.saturation_n)
    declared_w = phase_mass_w(model, committed.saturation_n)
    updated_n = phase_mass_n(model, saturation)
    updated_w = phase_mass_w(model, saturation)
    expected_n = dt * (flux_n_in - flux_n_out)
    expected_w = dt * (flux_w_in - flux_w_out)
    return TrialCandidate(
        attempt_id=attempt_id,
        dt=dt,
        time=committed.time + dt,
        saturation_n=saturation,
        flux_n_in=flux_n_in,
        flux_n_out=flux_n_out,
        flux_w_in=flux_w_in,
        flux_w_out=flux_w_out,
        cumulative_n_in=committed.cumulative_n_in + dt * flux_n_in,
        cumulative_n_out=committed.cumulative_n_out + dt * flux_n_out,
        cumulative_w_in=committed.cumulative_w_in + dt * flux_w_in,
        cumulative_w_out=committed.cumulative_w_out + dt * flux_w_out,
        internal_n_mass_defect=(updated_n - source_n) - expected_n,
        internal_w_mass_defect=(updated_w - source_w) - expected_w,
        declared_n_mass_defect=(updated_n - declared_n) - expected_n,
        declared_w_mass_defect=(updated_w - declared_w) - expected_w,
        source_state_hash=canonical_hash(source),
        declared_committed_hash=committed.fingerprint,
    )


def accept_candidate(
    committed: CommittedState, candidate: TrialCandidate
) -> CommittedState:
    if candidate.declared_committed_hash != committed.fingerprint:
        raise ValueError("candidate was not evaluated from the declared committed state")
    return CommittedState(
        time=candidate.time,
        saturation_n=candidate.saturation_n,
        cumulative_n_in=candidate.cumulative_n_in,
        cumulative_n_out=candidate.cumulative_n_out,
        cumulative_w_in=candidate.cumulative_w_in,
        cumulative_w_out=candidate.cumulative_w_out,
        accepted_version=committed.accepted_version + 1,
    )


def run_to_checkpoints(
    model: TwoPhaseModel,
    cell_count: int,
    cfl: float,
    checkpoints: Iterable[float],
) -> tuple[dict[float, CommittedState], tuple[TrialCandidate, ...]]:
    targets = tuple(sorted(set(float(value) for value in checkpoints)))
    if not targets or targets[0] <= 0.0:
        raise ValueError("positive checkpoints are required")
    if not 0.0 < cfl <= 1.0:
        raise ValueError("CFL must be in (0,1]")
    state = initial_state(cell_count)
    dx = model.H / cell_count
    nominal_dt = cfl * dx / 2.0
    outputs: dict[float, CommittedState] = {}
    candidates: list[TrialCandidate] = []
    ordinal = 0
    for target in targets:
        while state.time < target - 1.0e-15:
            dt = min(nominal_dt, target - state.time)
            ordinal += 1
            candidate = make_candidate(
                model, state, dt, attempt_id=f"STEP_{ordinal:08d}"
            )
            state = accept_candidate(state, candidate)
            candidates.append(candidate)
        outputs[target] = state
    return outputs, tuple(candidates)


def field_metrics(
    model: TwoPhaseModel,
    snapshot: AcceptedSnapshot,
    oracle: OracleProfile,
) -> FieldMetrics:
    if len(snapshot.saturation_n) != len(oracle.saturation_n):
        raise ValueError("snapshot and oracle meshes differ")
    dx = model.H / len(snapshot.saturation_n)
    saturation_differences = tuple(
        left - right
        for left, right in zip(snapshot.saturation_n, oracle.saturation_n)
    )
    pressure_differences = tuple(
        left - right for left, right in zip(snapshot.pressure, oracle.pressure)
    )
    pressure_norm = math.sqrt(sum(value * value for value in oracle.pressure) * dx)
    return FieldMetrics(
        saturation_l1_absolute=sum(abs(value) for value in saturation_differences) * dx,
        saturation_l2_absolute=math.sqrt(
            sum(value * value for value in saturation_differences) * dx
        ),
        pressure_l2_relative=math.sqrt(
            sum(value * value for value in pressure_differences) * dx
        ) / pressure_norm,
        pressure_linf_absolute=max(abs(value) for value in pressure_differences),
        displacement_absolute=abs(snapshot.displacement - oracle.displacement),
        front_absolute=abs(snapshot.front_location - oracle.front_location),
        oracle_root_residual=oracle.maximum_root_residual,
        oracle_quadrature_error=oracle.maximum_quadrature_error,
    )


def normalized_defect(defect: float, *scales: float) -> float:
    return abs(defect) / max((1.0, *(abs(value) for value in scales)))


def cumulative_phase_defects(
    model: TwoPhaseModel, state: CommittedState
) -> tuple[float, float]:
    initial_n = 0.0
    initial_w = model.phi * model.H
    current_n = phase_mass_n(model, state.saturation_n)
    current_w = phase_mass_w(model, state.saturation_n)
    defect_n = (current_n - initial_n) - (
        state.cumulative_n_in - state.cumulative_n_out
    )
    defect_w = (current_w - initial_w) - (
        state.cumulative_w_in - state.cumulative_w_out
    )
    return defect_n, defect_w


def l2_drift(left: Iterable[float], right: Iterable[float], length: float = 1.0) -> float:
    left_values = tuple(left)
    right_values = tuple(right)
    if len(left_values) != len(right_values):
        raise ValueError("field sizes differ")
    dx = length / len(left_values)
    return math.sqrt(
        sum((a - b) ** 2 for a, b in zip(left_values, right_values)) * dx
    )


def all_finite(values: Iterable[float], limit: float = 1.0e100) -> bool:
    return all(math.isfinite(value) and abs(value) <= limit for value in values)

