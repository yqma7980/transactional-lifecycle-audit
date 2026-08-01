"""Immutable packets and canonical fingerprints for L3-D1."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .l3_canonical import canonical_hash


DESIGN_VERSION = "L3-D1.0a"
HOST_VERSION = "L3-HOST-D1.0"


@dataclass(frozen=True)
class PoroModel:
    H: float = 1.0
    K_d: float = 4.0
    alpha: float = 1.0
    S: float = 0.25
    mobility: float = 0.5
    q: float = 1.0

    @property
    def storage_coefficient(self) -> float:
        return self.S + self.alpha * self.alpha / self.K_d

    @property
    def diffusivity(self) -> float:
        return self.mobility / self.storage_coefficient

    @property
    def p0(self) -> float:
        return self.alpha * self.q / (
            self.K_d * self.S + self.alpha * self.alpha
        )

    @property
    def fingerprint(self) -> str:
        return canonical_hash(self)


@dataclass(frozen=True)
class CommittedState:
    time: float
    pressure: tuple[float, ...]
    cumulative_outflow: float
    accepted_version: int

    @property
    def fingerprint(self) -> str:
        return canonical_hash(self)

    @property
    def mean_pressure(self) -> float:
        return sum(self.pressure) / len(self.pressure)


@dataclass(frozen=True)
class TrialCandidate:
    attempt_id: str
    dt: float
    time: float
    pressure: tuple[float, ...]
    boundary_flux: float
    outflow_increment: float
    cumulative_outflow: float
    storage_change_from_source: float
    internal_mass_defect: float
    declared_storage_change: float
    declared_mass_defect: float
    source_state_hash: str
    declared_committed_hash: str

    @property
    def fingerprint(self) -> str:
        return canonical_hash(self)

    @property
    def finite_values(self) -> tuple[float, ...]:
        return (
            self.dt,
            self.time,
            *self.pressure,
            self.boundary_flux,
            self.outflow_increment,
            self.cumulative_outflow,
            self.storage_change_from_source,
            self.internal_mass_defect,
            self.declared_storage_change,
            self.declared_mass_defect,
        )


@dataclass(frozen=True)
class AcceptedSnapshot:
    time: float
    pressure: tuple[float, ...]
    mean_pressure: float
    settlement: float
    cumulative_outflow: float
    accepted_version: int
    committed_hash: str

    @property
    def physical_hash(self) -> str:
        return canonical_hash(self)


def initial_state(model: PoroModel, cell_count: int) -> CommittedState:
    if cell_count < 2:
        raise ValueError("cell_count must be at least two")
    return CommittedState(
        time=0.0,
        pressure=tuple(model.p0 for _ in range(cell_count)),
        cumulative_outflow=0.0,
        accepted_version=0,
    )


def settlement(model: PoroModel, pressure: Iterable[float]) -> float:
    values = tuple(pressure)
    mean = sum(values) / len(values)
    return model.H * (model.q - model.alpha * mean) / model.K_d


def make_snapshot(model: PoroModel, state: CommittedState) -> AcceptedSnapshot:
    return AcceptedSnapshot(
        time=state.time,
        pressure=state.pressure,
        mean_pressure=state.mean_pressure,
        settlement=settlement(model, state.pressure),
        cumulative_outflow=state.cumulative_outflow,
        accepted_version=state.accepted_version,
        committed_hash=state.fingerprint,
    )
