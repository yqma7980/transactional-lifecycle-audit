"""Immutable state packets, deterministic fingerprints, and transaction host."""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
import hashlib
import json
from typing import Any


DESIGN_VERSION = "L1-D1.0"


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
    tangent_kind: str = "consistent"

    @property
    def operator_fingerprint(self) -> str:
        return canonical_hash(
            {
                "sigma": self.sigma,
                "E_alg": self.E_alg,
                "residual_state_version": self.residual_state_version,
                "tangent_state_version": self.tangent_state_version,
                "tangent_kind": self.tangent_kind,
            }
        )


@dataclass(frozen=True)
class OutputSnapshot:
    accepted_version: int
    epsilon_p: float
    kappa: float
    source_version: str
    source_candidate_id: str = "NA"

    @property
    def fingerprint(self) -> str:
        return canonical_hash(self)


class TransactionHost:
    """Explicit candidate registry used only by the transactional safe control."""

    def __init__(self, committed: CommittedState | None = None) -> None:
        self.committed = committed or CommittedState()
        self._attempts: dict[str, set[str]] = {}
        self._candidates: dict[str, CandidateState] = {}
        self._accepted_candidate_ids: set[str] = set()

    def begin_attempt(self, attempt_id: str) -> None:
        if attempt_id in self._attempts:
            raise ValueError(f"Attempt already exists: {attempt_id}")
        self._attempts[attempt_id] = set()

    def register_candidate(self, candidate: CandidateState) -> None:
        if candidate.attempt_id not in self._attempts:
            self.begin_attempt(candidate.attempt_id)
        if candidate.candidate_id in self._candidates:
            raise ValueError(f"Candidate already exists: {candidate.candidate_id}")
        self._candidates[candidate.candidate_id] = candidate
        self._attempts[candidate.attempt_id].add(candidate.candidate_id)

    def candidate_reachable(self, candidate_id: str) -> bool:
        return candidate_id in self._candidates

    def reject_candidate(self, candidate_id: str) -> bool:
        candidate = self._candidates.pop(candidate_id, None)
        if candidate is None:
            return False
        ids = self._attempts.get(candidate.attempt_id)
        if ids is not None:
            ids.discard(candidate_id)
        return True

    def reject_attempt(self, attempt_id: str) -> tuple[str, ...]:
        candidate_ids = tuple(sorted(self._attempts.pop(attempt_id, set())))
        for candidate_id in candidate_ids:
            self._candidates.pop(candidate_id, None)
        return candidate_ids

    def accept_candidate(self, candidate_id: str) -> tuple[bool, str]:
        if candidate_id in self._accepted_candidate_ids:
            return False, "duplicate_accept_rejected"
        candidate = self._candidates.get(candidate_id)
        if candidate is None:
            return False, "candidate_not_reachable"
        self.committed = CommittedState(
            epsilon_p=candidate.epsilon_p,
            kappa=candidate.kappa,
            accepted_version=self.committed.accepted_version + 1,
        )
        self._accepted_candidate_ids.add(candidate_id)
        self.reject_attempt(candidate.attempt_id)
        return True, "accepted_once"

    def output_accepted(self) -> OutputSnapshot:
        return OutputSnapshot(
            accepted_version=self.committed.accepted_version,
            epsilon_p=self.committed.epsilon_p,
            kappa=self.committed.kappa,
            source_version=f"accepted:{self.committed.accepted_version}",
        )


def commit_local(
    committed: CommittedState,
    candidate: CandidateState,
) -> CommittedState:
    return CommittedState(
        epsilon_p=candidate.epsilon_p,
        kappa=candidate.kappa,
        accepted_version=committed.accepted_version + 1,
    )


def checkpoint_payload(
    committed: CommittedState,
    configuration_hash: str,
) -> dict[str, Any]:
    return {
        "design_version": DESIGN_VERSION,
        "configuration_hash": configuration_hash,
        "accepted_version": committed.accepted_version,
        "epsilon_p_hex": committed.epsilon_p.hex(),
        "kappa_hex": committed.kappa.hex(),
        "committed_state_hash": committed.fingerprint,
    }


def checkpoint_restore(
    payload: dict[str, Any],
    expected_configuration_hash: str,
) -> CommittedState:
    if payload.get("design_version") != DESIGN_VERSION:
        raise ValueError("Checkpoint design version mismatch")
    if payload.get("configuration_hash") != expected_configuration_hash:
        raise ValueError("Checkpoint configuration hash mismatch")
    restored = CommittedState(
        epsilon_p=float.fromhex(payload["epsilon_p_hex"]),
        kappa=float.fromhex(payload["kappa_hex"]),
        accepted_version=int(payload["accepted_version"]),
    )
    if restored.fingerprint != payload.get("committed_state_hash"):
        raise ValueError("Checkpoint committed-state hash mismatch")
    return restored

