"""Safe controls and deliberately isolated unsafe lifecycle seeds."""

from __future__ import annotations

from .l1_material import evaluate_material
from .l1_state import (
    CandidateState,
    CommittedState,
    MaterialData,
    MaterialResult,
    OutputSnapshot,
    TransactionHost,
    canonical_hash,
    commit_local,
)


class SafeLocal:
    name = "safe_local"

    def __init__(
        self,
        material: MaterialData,
        committed: CommittedState | None = None,
    ) -> None:
        self.material = material
        self.committed = committed or CommittedState()
        self._accepted_ids: set[str] = set()

    @property
    def operator_version(self) -> str:
        return "L1-MP-1.0:safe_local"

    @property
    def persistent_hash(self) -> str:
        return "NA"

    def evaluate(
        self,
        epsilon: float,
        *,
        candidate_id: str,
        attempt_id: str,
        source_call_index: int,
    ) -> MaterialResult:
        return evaluate_material(
            epsilon,
            self.committed,
            self.material,
            candidate_id=candidate_id,
            attempt_id=attempt_id,
            source_call_index=source_call_index,
        )

    def reject_attempt(self, attempt_id: str) -> tuple[str, ...]:
        return ()

    def accept(self, candidate: CandidateState) -> tuple[bool, str]:
        if candidate.candidate_id in self._accepted_ids:
            return False, "duplicate_accept_rejected"
        self.committed = commit_local(self.committed, candidate)
        self._accepted_ids.add(candidate.candidate_id)
        return True, "accepted_once"

    def candidate_reachable(self, candidate_id: str) -> bool:
        return False

    def terminal_read(self, trigger_epsilon: float) -> OutputSnapshot:
        del trigger_epsilon
        return OutputSnapshot(
            accepted_version=self.committed.accepted_version,
            epsilon_p=self.committed.epsilon_p,
            kappa=self.committed.kappa,
            source_version=f"accepted:{self.committed.accepted_version}",
        )


class SafeTransactional:
    name = "safe_transactional"

    def __init__(
        self,
        material: MaterialData,
        committed: CommittedState | None = None,
    ) -> None:
        self.material = material
        self.host = TransactionHost(committed)

    @property
    def committed(self) -> CommittedState:
        return self.host.committed

    @property
    def operator_version(self) -> str:
        return "L1-MP-1.0:safe_transactional"

    @property
    def persistent_hash(self) -> str:
        return "NA"

    def begin_attempt(self, attempt_id: str) -> None:
        self.host.begin_attempt(attempt_id)

    def evaluate(
        self,
        epsilon: float,
        *,
        candidate_id: str,
        attempt_id: str,
        source_call_index: int,
    ) -> MaterialResult:
        result = evaluate_material(
            epsilon,
            self.committed,
            self.material,
            candidate_id=candidate_id,
            attempt_id=attempt_id,
            source_call_index=source_call_index,
        )
        self.host.register_candidate(result.candidate)
        return result

    def reject_attempt(self, attempt_id: str) -> tuple[str, ...]:
        return self.host.reject_attempt(attempt_id)

    def accept(self, candidate: CandidateState) -> tuple[bool, str]:
        return self.host.accept_candidate(candidate.candidate_id)

    def candidate_reachable(self, candidate_id: str) -> bool:
        return self.host.candidate_reachable(candidate_id)

    def terminal_read(self, trigger_epsilon: float) -> OutputSnapshot:
        del trigger_epsilon
        return self.host.output_accepted()


class UnsafeTrialCache:
    """Deliberate negative control: disposable candidates become hidden history."""

    name = "unsafe_trial_cache"

    def __init__(
        self,
        material: MaterialData,
        committed: CommittedState | None = None,
    ) -> None:
        self.material = material
        self.committed = committed or CommittedState()
        self._hidden = self.committed

    @property
    def operator_version(self) -> str:
        return "L1-MP-1.0:unsafe_trial_cache"

    @property
    def persistent_hash(self) -> str:
        return canonical_hash(self._hidden)

    def evaluate(
        self,
        epsilon: float,
        *,
        candidate_id: str,
        attempt_id: str,
        source_call_index: int,
    ) -> MaterialResult:
        version = f"hidden:{self.persistent_hash}"
        result = evaluate_material(
            epsilon,
            self._hidden,
            self.material,
            candidate_id=candidate_id,
            attempt_id=attempt_id,
            source_call_index=source_call_index,
            state_version_override=version,
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

    def candidate_reachable(self, candidate_id: str) -> bool:
        del candidate_id
        return False


class UnsafeOutputFeedback:
    """Deliberate negative control: a terminal read overwrites physical mirror."""

    name = "unsafe_output_feedback"

    def __init__(
        self,
        material: MaterialData,
        committed: CommittedState | None = None,
    ) -> None:
        self.material = material
        self.committed = committed or CommittedState()
        self._mirror = self.committed

    @property
    def operator_version(self) -> str:
        return "L1-MP-1.0:unsafe_output_feedback"

    @property
    def persistent_hash(self) -> str:
        return canonical_hash(self._mirror)

    def evaluate(
        self,
        epsilon: float,
        *,
        candidate_id: str,
        attempt_id: str,
        source_call_index: int,
    ) -> MaterialResult:
        version = f"mirror:{self.persistent_hash}"
        return evaluate_material(
            epsilon,
            self._mirror,
            self.material,
            candidate_id=candidate_id,
            attempt_id=attempt_id,
            source_call_index=source_call_index,
            state_version_override=version,
        )

    def terminal_read(self, trigger_epsilon: float) -> OutputSnapshot:
        result = evaluate_material(
            trigger_epsilon,
            self.committed,
            self.material,
            candidate_id="terminal_hidden_candidate",
            attempt_id="terminal_hidden_attempt",
            source_call_index=0,
            state_version_override="terminal_trial",
        )
        self._mirror = CommittedState(
            epsilon_p=result.candidate.epsilon_p,
            kappa=result.candidate.kappa,
            accepted_version=self.committed.accepted_version,
        )
        return OutputSnapshot(
            accepted_version=self.committed.accepted_version,
            epsilon_p=self._mirror.epsilon_p,
            kappa=self._mirror.kappa,
            source_version="trial_hidden",
            source_candidate_id=result.candidate.candidate_id,
        )

    def reject_attempt(self, attempt_id: str) -> tuple[str, ...]:
        del attempt_id
        return ()

    def candidate_reachable(self, candidate_id: str) -> bool:
        del candidate_id
        return False


VARIANTS = {
    "safe_local": SafeLocal,
    "safe_transactional": SafeTransactional,
    "unsafe_trial_cache": UnsafeTrialCache,
    "unsafe_output_feedback": UnsafeOutputFeedback,
}
