from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from p4d_canonical import canonical_hash
from p4d_config import RESIDUAL_VERSION, TANGENT_VERSION


def immutable_array(values: np.ndarray) -> np.ndarray:
    array = np.ascontiguousarray(values, dtype=np.float64).copy()
    array.flags.writeable = False
    return array


@dataclass(frozen=True)
class CommittedState:
    primary: np.ndarray
    gamma_p: np.ndarray
    alpha: np.ndarray
    accepted_index: int
    accepted_load: float
    accepted_version: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "primary", immutable_array(self.primary))
        object.__setattr__(self, "gamma_p", immutable_array(self.gamma_p))
        object.__setattr__(self, "alpha", immutable_array(self.alpha))

    @property
    def physical_hash(self) -> str:
        return canonical_hash({
            "gamma_p": self.gamma_p,
            "alpha": self.alpha,
            "accepted_load": self.accepted_load,
            "accepted_version": self.accepted_version,
        })

    @property
    def full_hash(self) -> str:
        return canonical_hash(self)


def initial_committed_state(primary_size: int = 25) -> CommittedState:
    return CommittedState(
        primary=np.zeros(primary_size, dtype=np.float64),
        gamma_p=np.zeros((32, 3, 2), dtype=np.float64),
        alpha=np.zeros((32, 3), dtype=np.float64),
        accepted_index=0,
        accepted_load=0.0,
        accepted_version=0,
    )


@dataclass
class PersistentState:
    hidden_trial_cache: np.ndarray = field(default_factory=lambda: np.zeros((32, 3, 2), dtype=np.float64))
    mutation_count: int = 0

    @property
    def projection_hash(self) -> str:
        return canonical_hash({"hidden_trial_cache": self.hidden_trial_cache, "mutation_count": self.mutation_count})

    def snapshot(self) -> dict[str, Any]:
        return {
            "hidden_trial_cache": self.hidden_trial_cache.copy(),
            "mutation_count": int(self.mutation_count),
            "projection_hash": self.projection_hash,
        }


@dataclass(frozen=True)
class MaterialFieldPacket:
    candidate_id: str
    primary_hash: str
    committed_hash: str
    persistent_hash: str
    target_load: float
    relation: str
    tau: np.ndarray
    tangent: np.ndarray
    gamma_p_candidate: np.ndarray
    alpha_candidate: np.ndarray
    branch: np.ndarray
    yield_function: np.ndarray
    delta_lambda: np.ndarray
    tangent_source_primary_hash: str
    residual_version: str = RESIDUAL_VERSION
    tangent_version: str = TANGENT_VERSION


@dataclass(frozen=True)
class OperatorVersionPacket:
    residual_version: str
    tangent_version: str
    relation: str
    residual_state_version: int
    tangent_state_version: int


@dataclass(frozen=True)
class VersionGuardResult:
    compatible: bool
    rejected_before_correction: bool
    reason: str


def validate_operator_versions(packet: OperatorVersionPacket) -> VersionGuardResult:
    if packet.relation == "EXACT_CURRENT":
        compatible = packet.residual_state_version == packet.tangent_state_version
    elif packet.relation == "DECLARED_ACCEPTED_STATE_LAG":
        compatible = packet.tangent_state_version <= packet.residual_state_version
    else:
        compatible = False
    return VersionGuardResult(
        compatible=compatible,
        rejected_before_correction=not compatible,
        reason="COMPATIBLE_DECLARED_RELATION" if compatible else "UNDECLARED_OPERATOR_VERSION_MISMATCH",
    )


class EventLedger:
    def __init__(self) -> None:
        self._records: list[dict[str, Any]] = []

    def append(self, event_kind: str, **fields: Any) -> dict[str, Any]:
        record = {"event_ordinal": len(self._records) + 1, "event_kind": event_kind, **fields}
        self._records.append(record)
        return record

    @property
    def records(self) -> list[dict[str, Any]]:
        return [dict(record) for record in self._records]

    def candidate_is_reachable(self, candidate_id: str) -> bool:
        return any(
            row.get("candidate_id") == candidate_id and row.get("reachable_from_accepted_output") is True
            for row in self._records
        )
