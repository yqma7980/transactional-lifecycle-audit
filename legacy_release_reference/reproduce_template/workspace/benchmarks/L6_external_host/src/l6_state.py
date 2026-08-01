"""Immutable state packets for the L6 external-host lifecycle benchmark."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib.util
import math
from pathlib import Path
import sys
from typing import Iterable


_L2_STATE_PATH = (
    Path(__file__).resolve().parents[2]
    / "L2_host_lifecycle"
    / "src"
    / "l2_state.py"
)
_EXPECTED_L2_STATE_SHA256 = (
    "05c9684d1bfcf5cb8b0c446795f697ecff6860edef2649af16a4baf7db62e67d"
)
if hashlib.sha256(_L2_STATE_PATH.read_bytes()).hexdigest() != _EXPECTED_L2_STATE_SHA256:
    raise RuntimeError("Frozen L2 canonical serializer hash mismatch")
_spec = importlib.util.spec_from_file_location(
    "_l6_frozen_l2_state", _L2_STATE_PATH
)
if _spec is None or _spec.loader is None:
    raise RuntimeError("Unable to load frozen L2 canonical serializer")
_l2_state = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _l2_state
_spec.loader.exec_module(_l2_state)
canonical_hash = _l2_state.canonical_hash
canonical_json = _l2_state.canonical_json


DESIGN_VERSION = "L6-D1.0"
HOST_VERSION = "L6-SCIPY-TRF-1.17.1"
ADAPTER_VERSION = "L6-ADAPTER-D1.0"


@dataclass(frozen=True)
class CommittedState:
    history: float = 0.0
    accepted_version: int = 0

    @property
    def fingerprint(self) -> str:
        return canonical_hash(self)


@dataclass(frozen=True)
class TrialCandidate:
    x: float
    candidate_history: float
    source_event_id: str
    committed_fingerprint: str

    @property
    def fingerprint(self) -> str:
        return canonical_hash(self)


@dataclass(frozen=True)
class ResidualPacket:
    x: float
    residual: float
    residual_state_version: str
    candidate_fingerprint: str
    committed_fingerprint: str

    @property
    def fingerprint(self) -> str:
        return canonical_hash(self)


@dataclass(frozen=True)
class TangentPacket:
    x: float
    tangent: float
    tangent_state_version: str
    committed_fingerprint: str

    @property
    def fingerprint(self) -> str:
        return canonical_hash(self)


@dataclass(frozen=True)
class AcceptedOutput:
    x: float
    residual: float
    cost: float
    committed_fingerprint: str
    accepted_version: int
    source_event_id: str
    source: str = "HOST_RETURNED_ACCEPTED_STATE"

    @property
    def fingerprint(self) -> str:
        return canonical_hash(self)


@dataclass
class PersistentState:
    history: float = 0.0
    mutation_count: int = 0

    @property
    def fingerprint(self) -> str:
        return canonical_hash(
            {"history": self.history, "mutation_count": self.mutation_count}
        )


class OperatorVersionMismatch(RuntimeError):
    """Raised before an incompatible Jacobian packet reaches the host."""

    def __init__(
        self,
        residual_packet: ResidualPacket,
        tangent_packet: TangentPacket,
    ) -> None:
        super().__init__(
            "Residual/tangent state-version mismatch: "
            f"{residual_packet.residual_state_version} != "
            f"{tangent_packet.tangent_state_version}"
        )
        self.residual_packet = residual_packet
        self.tangent_packet = tangent_packet


def state_version(committed: CommittedState, x: float) -> str:
    return canonical_hash(
        {
            "committed_fingerprint": committed.fingerprint,
            "trial_x_hex": float(x).hex(),
            "operator_family": "L6-RJ-D1.0",
        }
    )


def stale_state_version(committed: CommittedState, x: float) -> str:
    return canonical_hash(
        {
            "committed_fingerprint": committed.fingerprint,
            "trial_x_hex": float(x).hex(),
            "operator_family": "L6-RJ-D1.0",
            "revision": "STALE_TANGENT_VERSION",
        }
    )


def all_finite(values: Iterable[float], absolute_limit: float = 1.0e100) -> bool:
    return all(math.isfinite(float(value)) and abs(float(value)) < absolute_limit for value in values)


__all__ = [
    "ADAPTER_VERSION",
    "AcceptedOutput",
    "CommittedState",
    "DESIGN_VERSION",
    "HOST_VERSION",
    "OperatorVersionMismatch",
    "PersistentState",
    "ResidualPacket",
    "TangentPacket",
    "TrialCandidate",
    "all_finite",
    "canonical_hash",
    "canonical_json",
    "stale_state_version",
    "state_version",
]
