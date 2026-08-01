from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from typing import Any


def fingerprint(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CallRecord:
    variant: str
    call_index: int
    event: str
    candidate_id: str
    x_trial: float | None
    committed_c: float
    residual: float | None
    committed_hash_before: str
    committed_hash_after: str
    persistent_hash_before: str
    persistent_hash_after: str
    persistent_value_before: float | None
    persistent_value_after: float | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ScalarEvaluator:
    variant = "base"

    def __init__(self, committed_c: float, alpha: float) -> None:
        if not math.isfinite(committed_c) or not math.isfinite(alpha):
            raise ValueError("committed_c and alpha must be finite")
        self.committed_c = committed_c
        self.alpha = alpha
        self.records: list[CallRecord] = []
        self._call_index = 0

    def committed_state(self) -> dict[str, float]:
        return {"committed_c": self.committed_c}

    def persistent_state(self) -> dict[str, float] | None:
        return None

    def persistent_value(self) -> float | None:
        state = self.persistent_state()
        if state is None:
            return None
        return next(iter(state.values()))

    def evaluate(self, x_trial: float, event: str, candidate_id: str) -> float:
        raise NotImplementedError

    def reject(self, candidate_id: str) -> None:
        self._record(event="reject", candidate_id=candidate_id)

    def _record(
        self,
        event: str,
        candidate_id: str,
        x_trial: float | None = None,
        residual: float | None = None,
        committed_before: dict[str, float] | None = None,
        persistent_before: dict[str, float] | None = None,
    ) -> None:
        self._call_index += 1
        committed_before = committed_before if committed_before is not None else self.committed_state()
        persistent_before = persistent_before if persistent_before is not None else self.persistent_state()
        persistent_after = self.persistent_state()
        self.records.append(
            CallRecord(
                variant=self.variant,
                call_index=self._call_index,
                event=event,
                candidate_id=candidate_id,
                x_trial=x_trial,
                committed_c=self.committed_c,
                residual=residual,
                committed_hash_before=fingerprint(committed_before),
                committed_hash_after=fingerprint(self.committed_state()),
                persistent_hash_before=fingerprint(persistent_before),
                persistent_hash_after=fingerprint(persistent_after),
                persistent_value_before=(None if persistent_before is None else next(iter(persistent_before.values()))),
                persistent_value_after=(None if persistent_after is None else next(iter(persistent_after.values()))),
            )
        )


class UnsafePersistentEvaluator(ScalarEvaluator):
    """Seeded defect: every evaluation writes trial x into unprotected persistent state."""

    variant = "unsafe_persistent"

    def __init__(self, committed_c: float, alpha: float) -> None:
        super().__init__(committed_c, alpha)
        self.p = 0.0

    def persistent_state(self) -> dict[str, float]:
        return {"p": self.p}

    def evaluate(self, x_trial: float, event: str, candidate_id: str) -> float:
        committed_before = self.committed_state()
        persistent_before = self.persistent_state()
        residual = x_trial - self.committed_c + self.alpha * self.p
        self.p = x_trial
        self._record(
            event=event,
            candidate_id=candidate_id,
            x_trial=x_trial,
            residual=residual,
            committed_before=committed_before,
            persistent_before=persistent_before,
        )
        return residual


class SafeLocalEvaluator(ScalarEvaluator):
    variant = "safe_local"

    def evaluate(self, x_trial: float, event: str, candidate_id: str) -> float:
        committed_before = self.committed_state()
        residual = x_trial - self.committed_c
        self._record(
            event=event,
            candidate_id=candidate_id,
            x_trial=x_trial,
            residual=residual,
            committed_before=committed_before,
        )
        return residual


class SafeTransactionalEvaluator(ScalarEvaluator):
    variant = "safe_transactional"

    def __init__(self, committed_c: float, alpha: float) -> None:
        super().__init__(committed_c, alpha)
        self.committed_p = 0.0
        self.candidates: dict[str, float] = {}

    def committed_state(self) -> dict[str, float]:
        return {"committed_c": self.committed_c, "committed_p": self.committed_p}

    def persistent_state(self) -> dict[str, float]:
        return {"committed_p": self.committed_p}

    def evaluate(self, x_trial: float, event: str, candidate_id: str) -> float:
        committed_before = self.committed_state()
        persistent_before = self.persistent_state()
        residual = x_trial - self.committed_c + self.alpha * self.committed_p
        if event not in {"terminal", "output"}:
            self.candidates[candidate_id] = x_trial
        self._record(
            event=event,
            candidate_id=candidate_id,
            x_trial=x_trial,
            residual=residual,
            committed_before=committed_before,
            persistent_before=persistent_before,
        )
        return residual

    def reject(self, candidate_id: str) -> None:
        committed_before = self.committed_state()
        persistent_before = self.persistent_state()
        self.candidates.pop(candidate_id, None)
        self._record(
            event="reject",
            candidate_id=candidate_id,
            committed_before=committed_before,
            persistent_before=persistent_before,
        )

    def accept(self, candidate_id: str) -> None:
        if candidate_id not in self.candidates:
            raise KeyError(f"unknown candidate: {candidate_id}")
        committed_before = self.committed_state()
        persistent_before = self.persistent_state()
        self.committed_p = self.candidates.pop(candidate_id)
        self._record(
            event="accept",
            candidate_id=candidate_id,
            committed_before=committed_before,
            persistent_before=persistent_before,
        )


VARIANTS = {
    UnsafePersistentEvaluator.variant: UnsafePersistentEvaluator,
    SafeLocalEvaluator.variant: SafeLocalEvaluator,
    SafeTransactionalEvaluator.variant: SafeTransactionalEvaluator,
}
