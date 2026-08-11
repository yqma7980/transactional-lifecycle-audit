"""Immutable physical, trial and accepted-output packets for L4-D1."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import runpy
from typing import Iterable


# Load the authoritative L2 serializer directly without importing the L2 package,
# whose legacy package initializer imports benchmark execution modules.
_L2_STATE = runpy.run_path(
    str(Path(__file__).resolve().parents[2] / "L2_host_lifecycle" / "src" / "l2_state.py")
)
canonical_hash = _L2_STATE["canonical_hash"]


DESIGN_VERSION = "L4-D1.0"
HOST_VERSION = "L4-HOST-D1.0"


@dataclass(frozen=True)
class TwoPhaseModel:
    H: float = 1.0
    phi: float = 1.0
    q_total: float = 1.0
    permeability: float = 1.0
    mu_w: float = 1.0
    mu_n: float = 1.0
    pressure_right: float = 0.0
    K_d: float = 4.0
    alpha: float = 1.0

    def kr_n(self, saturation_n: float) -> float:
        return saturation_n * saturation_n

    def kr_w(self, saturation_n: float) -> float:
        saturation_w = 1.0 - saturation_n
        return saturation_w * saturation_w

    def lambda_n(self, saturation_n: float) -> float:
        return self.kr_n(saturation_n) / self.mu_n

    def lambda_w(self, saturation_n: float) -> float:
        return self.kr_w(saturation_n) / self.mu_w

    def lambda_total(self, saturation_n: float) -> float:
        return self.lambda_n(saturation_n) + self.lambda_w(saturation_n)

    def fractional_flow_n(self, saturation_n: float) -> float:
        return self.lambda_n(saturation_n) / self.lambda_total(saturation_n)

    def fractional_flow_derivative(self, saturation_n: float) -> float:
        denominator = saturation_n**2 + (1.0 - saturation_n) ** 2
        return 2.0 * saturation_n * (1.0 - saturation_n) / denominator**2

    @property
    def fingerprint(self) -> str:
        return canonical_hash(self)


@dataclass(frozen=True)
class CommittedState:
    time: float
    saturation_n: tuple[float, ...]
    cumulative_n_in: float
    cumulative_n_out: float
    cumulative_w_in: float
    cumulative_w_out: float
    accepted_version: int

    @property
    def fingerprint(self) -> str:
        return canonical_hash(self)


@dataclass(frozen=True)
class TrialCandidate:
    attempt_id: str
    dt: float
    time: float
    saturation_n: tuple[float, ...]
    flux_n_in: float
    flux_n_out: float
    flux_w_in: float
    flux_w_out: float
    cumulative_n_in: float
    cumulative_n_out: float
    cumulative_w_in: float
    cumulative_w_out: float
    internal_n_mass_defect: float
    internal_w_mass_defect: float
    declared_n_mass_defect: float
    declared_w_mass_defect: float
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
            *self.saturation_n,
            self.flux_n_in,
            self.flux_n_out,
            self.flux_w_in,
            self.flux_w_out,
            self.cumulative_n_in,
            self.cumulative_n_out,
            self.cumulative_w_in,
            self.cumulative_w_out,
            self.internal_n_mass_defect,
            self.internal_w_mass_defect,
            self.declared_n_mass_defect,
            self.declared_w_mass_defect,
        )


@dataclass(frozen=True)
class AcceptedSnapshot:
    time: float
    saturation_n: tuple[float, ...]
    pressure: tuple[float, ...]
    displacement: float
    phase_mass_n: float
    phase_mass_w: float
    front_location: float
    accepted_version: int
    committed_hash: str

    @property
    def physical_hash(self) -> str:
        return canonical_hash(self)


def initial_state(cell_count: int) -> CommittedState:
    if cell_count < 2:
        raise ValueError("cell_count must be at least two")
    return CommittedState(
        time=0.0,
        saturation_n=tuple(0.0 for _ in range(cell_count)),
        cumulative_n_in=0.0,
        cumulative_n_out=0.0,
        cumulative_w_in=0.0,
        cumulative_w_out=0.0,
        accepted_version=0,
    )


def phase_mass_n(model: TwoPhaseModel, saturation_n: Iterable[float]) -> float:
    values = tuple(saturation_n)
    return model.phi * model.H * sum(values) / len(values)


def phase_mass_w(model: TwoPhaseModel, saturation_n: Iterable[float]) -> float:
    values = tuple(saturation_n)
    return model.phi * model.H * sum(1.0 - value for value in values) / len(values)

