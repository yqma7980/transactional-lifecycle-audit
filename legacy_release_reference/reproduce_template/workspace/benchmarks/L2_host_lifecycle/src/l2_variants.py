"""Safe controls and the isolated unsafe L2-D1 negative control."""

from __future__ import annotations

from .l2_model import evaluate_material
from .l2_state import (
    CandidateState,
    CommittedState,
    MaterialData,
    canonical_hash,
)


def _commit(committed: CommittedState, candidate: CandidateState) -> CommittedState:
    return CommittedState(
        epsilon_p=candidate.epsilon_p,
        kappa=candidate.kappa,
        accepted_version=committed.accepted_version + 1,
    )


class SafeLocal:
    name = "safe_local"
    persistent_state_class = "none"

    def __init__(self, material: MaterialData) -> None:
        self.material = material
        self.committed = CommittedState()
        self._accepted_ids: set[str] = set()

    @property
    def persistent_hash(self) -> str:
        return "NA"

    def begin_attempt(self, attempt_id: str) -> None:
        del attempt_id

    def evaluate(
        self,
        epsilon: float,
        *,
        candidate_id: str,
        attempt_id: str,
        source_call_index: int,
    ):
        return evaluate_material(
            epsilon,
            self.committed,
            self.material,
            candidate_id=candidate_id,
            attempt_id=attempt_id,
            source_call_index=source_call_index,
        )

    def reject_attempt(self, attempt_id: str) -> tuple[str, ...]:
        del attempt_id
        return ()

    def accept(self, candidate: CandidateState) -> tuple[bool, str]:
        if candidate.candidate_id in self._accepted_ids:
            return False, "duplicate_accept_rejected"
        self.committed = _commit(self.committed, candidate)
        self._accepted_ids.add(candidate.candidate_id)
        return True, "accepted_once"

    def candidate_reachable(self, candidate_id: str) -> bool:
        del candidate_id
        return False


class SafeTransactional:
    name = "safe_transactional"
    persistent_state_class = "transaction_registry"

    def __init__(self, material: MaterialData) -> None:
        self.material = material
        self.committed = CommittedState()
        self._attempts: dict[str, set[str]] = {}
        self._candidates: dict[str, CandidateState] = {}
        self._accepted_ids: set[str] = set()

    @property
    def persistent_hash(self) -> str:
        return canonical_hash(
            {
                "attempts": {
                    key: sorted(value) for key, value in sorted(self._attempts.items())
                },
                "candidate_ids": sorted(self._candidates),
            }
        )

    def begin_attempt(self, attempt_id: str) -> None:
        if attempt_id in self._attempts:
            raise ValueError(f"Attempt already exists: {attempt_id}")
        self._attempts[attempt_id] = set()

    def evaluate(
        self,
        epsilon: float,
        *,
        candidate_id: str,
        attempt_id: str,
        source_call_index: int,
    ):
        if attempt_id not in self._attempts:
            raise ValueError(f"Attempt not begun: {attempt_id}")
        result = evaluate_material(
            epsilon,
            self.committed,
            self.material,
            candidate_id=candidate_id,
            attempt_id=attempt_id,
            source_call_index=source_call_index,
        )
        if candidate_id in self._candidates:
            raise ValueError(f"Candidate already exists: {candidate_id}")
        self._candidates[candidate_id] = result.candidate
        self._attempts[attempt_id].add(candidate_id)
        return result

    def reject_attempt(self, attempt_id: str) -> tuple[str, ...]:
        candidate_ids = tuple(sorted(self._attempts.pop(attempt_id, set())))
        for candidate_id in candidate_ids:
            self._candidates.pop(candidate_id, None)
        return candidate_ids

    def accept(self, candidate: CandidateState) -> tuple[bool, str]:
        if candidate.candidate_id in self._accepted_ids:
            return False, "duplicate_accept_rejected"
        registered = self._candidates.get(candidate.candidate_id)
        if registered is None:
            return False, "candidate_not_reachable"
        self.committed = _commit(self.committed, registered)
        self._accepted_ids.add(candidate.candidate_id)
        self.reject_attempt(candidate.attempt_id)
        return True, "accepted_once"

    def candidate_reachable(self, candidate_id: str) -> bool:
        return candidate_id in self._candidates


class UnsafeTrialCache:
    name = "unsafe_trial_cache"
    persistent_state_class = "deliberate_unprotected_physical_cache"

    def __init__(self, material: MaterialData) -> None:
        self.material = material
        self.committed = CommittedState()
        self._hidden = self.committed
        self._accepted_ids: set[str] = set()

    @property
    def persistent_hash(self) -> str:
        return canonical_hash(self._hidden)

    def begin_attempt(self, attempt_id: str) -> None:
        del attempt_id

    def evaluate(
        self,
        epsilon: float,
        *,
        candidate_id: str,
        attempt_id: str,
        source_call_index: int,
    ):
        result = evaluate_material(
            epsilon,
            self._hidden,
            self.material,
            candidate_id=candidate_id,
            attempt_id=attempt_id,
            source_call_index=source_call_index,
            state_version_override=f"hidden:{self.persistent_hash}",
        )
        self._hidden = CommittedState(
            epsilon_p=result.candidate.epsilon_p,
            kappa=result.candidate.kappa,
            accepted_version=self.committed.accepted_version,
        )
        return result

    def reject_attempt(self, attempt_id: str) -> tuple[str, ...]:
        del attempt_id
        return ()

    def accept(self, candidate: CandidateState) -> tuple[bool, str]:
        if candidate.candidate_id in self._accepted_ids:
            return False, "duplicate_accept_rejected"
        self.committed = _commit(self.committed, candidate)
        self._hidden = self.committed
        self._accepted_ids.add(candidate.candidate_id)
        return True, "accepted_once"

    def candidate_reachable(self, candidate_id: str) -> bool:
        del candidate_id
        return False


VARIANTS = {
    "safe_local": SafeLocal,
    "safe_transactional": SafeTransactional,
    "unsafe_trial_cache": UnsafeTrialCache,
}
