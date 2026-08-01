"""Independent binary state and fingerprint definitions for L5-D1."""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
import hashlib
import math
import struct
from typing import Any, Iterable


DESIGN_VERSION = "L5-D1.0"
HOST_VERSION = "L5-HOST-D1.0"


def _length(value: int) -> bytes:
    return struct.pack(">Q", value)


def _binary(value: Any) -> bytes:
    if is_dataclass(value):
        payload = [(field.name, getattr(value, field.name)) for field in fields(value)]
        return b"D" + _binary(value.__class__.__name__) + _binary(payload)
    if isinstance(value, bool):
        return b"B1" if value else b"B0"
    if value is None:
        return b"N"
    if isinstance(value, int):
        data = str(value).encode("ascii")
        return b"I" + _length(len(data)) + data
    if isinstance(value, float):
        return b"F" + struct.pack(">d", value)
    if isinstance(value, str):
        data = value.encode("utf-8")
        return b"S" + _length(len(data)) + data
    if isinstance(value, dict):
        items = sorted((str(key), item) for key, item in value.items())
        return b"M" + _length(len(items)) + b"".join(
            _binary(key) + _binary(item) for key, item in items
        )
    if isinstance(value, (list, tuple)):
        return b"L" + _length(len(value)) + b"".join(_binary(item) for item in value)
    raise TypeError(f"unsupported independent binary value: {type(value)!r}")


def binary_fingerprint(value: Any) -> str:
    return hashlib.sha256(_binary(value)).hexdigest()


@dataclass(frozen=True)
class IndependentModel:
    length: float = 1.0
    porosity: float = 1.0
    total_flux: float = 1.0
    permeability: float = 1.0
    viscosity_w: float = 1.0
    viscosity_n: float = 1.0
    pressure_right: float = 0.0
    drained_modulus: float = 4.0
    biot_alpha: float = 1.0

    def kr_n(self, saturation_n: float) -> float:
        return saturation_n * saturation_n

    def kr_w(self, saturation_n: float) -> float:
        return (1.0 - saturation_n) ** 2

    def mobility_n(self, saturation_n: float) -> float:
        return self.kr_n(saturation_n) / self.viscosity_n

    def mobility_w(self, saturation_n: float) -> float:
        return self.kr_w(saturation_n) / self.viscosity_w

    def mobility_total(self, saturation_n: float) -> float:
        return self.mobility_n(saturation_n) + self.mobility_w(saturation_n)

    def fractional_flow_n(self, saturation_n: float) -> float:
        return self.mobility_n(saturation_n) / self.mobility_total(saturation_n)

    def fractional_flow_derivative(self, saturation_n: float) -> float:
        denominator = saturation_n**2 + (1.0 - saturation_n) ** 2
        return 2.0 * saturation_n * (1.0 - saturation_n) / denominator**2

    @property
    def fingerprint(self) -> str:
        return binary_fingerprint(self)


@dataclass(frozen=True)
class IndependentCommitted:
    time: float
    saturation_n: tuple[float, ...]
    cumulative_n_in: float
    cumulative_n_out: float
    cumulative_w_in: float
    cumulative_w_out: float
    accepted_version: int

    @property
    def fingerprint(self) -> str:
        return binary_fingerprint(self)


@dataclass(frozen=True)
class IndependentCandidate:
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
    declared_committed_hash: str
    source_field_hash: str

    @property
    def fingerprint(self) -> str:
        return binary_fingerprint(self)

    @property
    def finite_values(self) -> tuple[float, ...]:
        return (
            self.dt, self.time, *self.saturation_n,
            self.flux_n_in, self.flux_n_out, self.flux_w_in, self.flux_w_out,
            self.cumulative_n_in, self.cumulative_n_out,
            self.cumulative_w_in, self.cumulative_w_out,
            self.internal_n_mass_defect, self.internal_w_mass_defect,
            self.declared_n_mass_defect, self.declared_w_mass_defect,
        )


@dataclass(frozen=True)
class IndependentSnapshot:
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
    def fingerprint(self) -> str:
        return binary_fingerprint(self)


def initial_committed(cell_count: int) -> IndependentCommitted:
    if cell_count < 4:
        raise ValueError("L5 cell_count must be at least four")
    return IndependentCommitted(
        time=0.0,
        saturation_n=tuple(0.0 for _ in range(cell_count)),
        cumulative_n_in=0.0,
        cumulative_n_out=0.0,
        cumulative_w_in=0.0,
        cumulative_w_out=0.0,
        accepted_version=0,
    )


def phase_mass_n(model: IndependentModel, saturation_n: Iterable[float]) -> float:
    values=tuple(saturation_n)
    return model.porosity * model.length * math.fsum(values) / len(values)


def phase_mass_w(model: IndependentModel, saturation_n: Iterable[float]) -> float:
    values=tuple(saturation_n)
    return model.porosity * model.length * math.fsum(1.0-value for value in values) / len(values)
