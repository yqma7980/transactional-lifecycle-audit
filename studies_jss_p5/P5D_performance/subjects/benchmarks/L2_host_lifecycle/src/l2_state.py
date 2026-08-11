"""Immutable packets and deterministic fingerprints for L2-D1."""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
import hashlib
import json
from typing import Any


DESIGN_VERSION = "L2-D1.0"
HOST_VERSION = "L2-HOST-D1.0"


def _canonical(value: Any) -> Any:
    if is_dataclass(value):
        return _canonical(asdict(value))
    if isinstance(value, float):
        return {"__float_hex__": value.hex()}
    if isinstance(value, dict):
        return {str(key): _canonical(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    raise TypeError(f"Unsupported canonical value: {type(value)!r}")


def canonical_json(value: Any) -> str:
    return json.dumps(
        _canonical(value),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class MaterialData:
    E: float = 100.0
    sigma_y: float = 1.0
    H: float = 10.0

    @property
    def fingerprint(self) -> str:
        return canonical_hash(self)


@dataclass(frozen=True)
class ElementData:
    area: float = 1.0
    length: float = 1.0
    u1: float = 0.0

    @property
    def fingerprint(self) -> str:
        return canonical_hash(self)


@dataclass(frozen=True)
class CommittedState:
    epsilon_p: float = 0.0
    kappa: float = 0.0
    accepted_version: int = 0

    @property
    def fingerprint(self) -> str:
        return canonical_hash(self)


@dataclass(frozen=True)
class CandidateState:
    epsilon_p: float
    kappa: float
    candidate_id: str
    attempt_id: str
    source_call_index: int

    @property
    def fingerprint(self) -> str:
        return canonical_hash(self)


@dataclass(frozen=True)
class MaterialResult:
    sigma: float
    E_alg: float
    delta_gamma: float
    candidate: CandidateState
    residual_state_version: str
    tangent_state_version: str


@dataclass(frozen=True)
class ElementResult:
    u: float
    force: float
    epsilon: float
    residual: float
    tangent: float
    material: MaterialResult
    declared_packet_hash: str

    @property
    def candidate(self) -> CandidateState:
        return self.material.candidate

    @property
    def sigma(self) -> float:
        return self.material.sigma

    @property
    def finite_values(self) -> tuple[float, ...]:
        return (
            self.u,
            self.force,
            self.epsilon,
            self.residual,
            self.tangent,
            self.material.sigma,
            self.material.E_alg,
            self.material.delta_gamma,
            self.candidate.epsilon_p,
            self.candidate.kappa,
        )

    @property
    def version_compatible(self) -> bool:
        return (
            self.material.residual_state_version
            == self.material.tangent_state_version
        )

    @property
    def operator_hash(self) -> str:
        return canonical_hash(
            {
                "packet": self.declared_packet_hash,
                "residual": self.residual,
                "tangent": self.tangent,
                "residual_state_version": self.material.residual_state_version,
                "tangent_state_version": self.material.tangent_state_version,
            }
        )


@dataclass(frozen=True)
class AcceptedCheckpoint:
    force: float
    displacement: float
    reaction: float
    stress: float
    epsilon_p: float
    kappa: float
    accepted_version: int
    committed_state_hash: str

    @property
    def physical_hash(self) -> str:
        return canonical_hash(self)


def make_checkpoint(
    *,
    force: float,
    displacement: float,
    result: ElementResult,
    committed: CommittedState,
) -> AcceptedCheckpoint:
    return AcceptedCheckpoint(
        force=force,
        displacement=displacement,
        reaction=result.sigma,
        stress=result.sigma,
        epsilon_p=committed.epsilon_p,
        kappa=committed.kappa,
        accepted_version=committed.accepted_version,
        committed_state_hash=committed.fingerprint,
    )
