"""Retry-state variants and equal-declared-state comparison for L3."""

from __future__ import annotations

from dataclasses import dataclass
import math

from .l3_canonical import canonical_hash
from .l3_fv import accept_candidate, make_candidate, pressure_l2_drift
from .l3_state import CommittedState, PoroModel, TrialCandidate, initial_state, settlement


class RetryVariant:
    name = "base"

    def __init__(self, model: PoroModel, cell_count: int) -> None:
        self.model = model
        self.committed = initial_state(model, cell_count)
        self._live: set[str] = set()

    @property
    def persistent_hash(self) -> str:
        raise NotImplementedError

    def previous_state(self) -> tuple[float, ...]:
        return self.committed.pressure

    def after_evaluate(self, candidate: TrialCandidate) -> None:
        self._live.add(candidate.attempt_id)

    def evaluate(self, attempt_id: str, dt: float) -> TrialCandidate:
        candidate = make_candidate(
            self.model,
            self.committed,
            dt,
            attempt_id=attempt_id,
            previous_override=self.previous_state(),
        )
        self.after_evaluate(candidate)
        return candidate

    def reject(self, candidate: TrialCandidate) -> None:
        self._live.discard(candidate.attempt_id)

    def accept(self, candidate: TrialCandidate) -> None:
        self.committed = accept_candidate(self.committed, candidate)
        self._live.discard(candidate.attempt_id)

    def candidate_reachable(self, candidate: TrialCandidate) -> bool:
        return candidate.attempt_id in self._live


class SafeTransactionalVariant(RetryVariant):
    name = "safe_transactional"

    @property
    def persistent_hash(self) -> str:
        return canonical_hash({"kind": "no_physical_persistent_state"})


class UnsafePreviousStateCacheVariant(RetryVariant):
    name = "unsafe_previous_state_cache"

    def __init__(self, model: PoroModel, cell_count: int) -> None:
        super().__init__(model, cell_count)
        self.hidden_previous_pressure = self.committed.pressure

    @property
    def persistent_hash(self) -> str:
        return canonical_hash(
            {
                "kind": self.name,
                "hidden_previous_pressure": self.hidden_previous_pressure,
            }
        )

    def previous_state(self) -> tuple[float, ...]:
        return self.hidden_previous_pressure

    def after_evaluate(self, candidate: TrialCandidate) -> None:
        super().after_evaluate(candidate)
        self.hidden_previous_pressure = candidate.pressure


@dataclass(frozen=True)
class RetryComparison:
    variant: str
    direct_state: CommittedState
    retry_state: CommittedState
    direct_candidate: TrialCandidate
    rejected_candidate: TrialCandidate
    replay_candidate: TrialCandidate
    declared_context_equal: bool
    committed_before_replay_unchanged: bool
    rejected_candidate_unreachable: bool
    accepted_pressure_exact: bool
    accepted_state_fingerprint_exact: bool
    observed_replay_fingerprint_equal: bool
    pressure_l2_drift: float
    settlement_drift: float
    declared_mass_defect: float
    all_values_finite: bool
    events: tuple[dict[str, object], ...]


def _declared_context(model: PoroModel, state: CommittedState, dt: float) -> str:
    return canonical_hash(
        {
            "model": model.fingerprint,
            "committed": state.fingerprint,
            "dt": dt,
            "residual_version": "L3-FV-R1",
            "operator_version": "L3-FV-K1",
        }
    )


def _observed(candidate: TrialCandidate, persistent_hash: str) -> str:
    return canonical_hash(
        {
            "pressure": candidate.pressure,
            "boundary_flux": candidate.boundary_flux,
            "declared_mass_defect": candidate.declared_mass_defect,
            "persistent": persistent_hash,
        }
    )


def _event(
    *,
    ordinal: int,
    history_id: str,
    event: str,
    attempt_id: str,
    variant: RetryVariant,
    candidate: TrialCandidate | None = None,
    accepted: bool = False,
    note: str,
) -> dict[str, object]:
    pressure = candidate.pressure if candidate else variant.committed.pressure
    finite_values = candidate.finite_values if candidate else pressure
    return {
        "ordinal": ordinal,
        "history_id": history_id,
        "event": event,
        "attempt_id": attempt_id,
        "variant": variant.name,
        "accepted": accepted,
        "time": candidate.time if candidate else variant.committed.time,
        "dt": candidate.dt if candidate else 0.0,
        "committed_fingerprint": variant.committed.fingerprint,
        "candidate_fingerprint": candidate.fingerprint if candidate else "NA",
        "persistent_fingerprint": variant.persistent_hash,
        "candidate_reachable": variant.candidate_reachable(candidate) if candidate else False,
        "mean_pressure": sum(pressure) / len(pressure),
        "minimum_pressure": min(pressure),
        "maximum_pressure": max(pressure),
        "settlement": settlement(variant.model, pressure),
        "cumulative_outflow": candidate.cumulative_outflow if candidate else variant.committed.cumulative_outflow,
        "boundary_flux": candidate.boundary_flux if candidate else 0.0,
        "storage_change": candidate.declared_storage_change if candidate else 0.0,
        "mass_defect": candidate.declared_mass_defect if candidate else 0.0,
        "finite": all(math.isfinite(value) and abs(value) <= 1.0e100 for value in finite_values),
        "note": note,
    }


def compare_retry(
    model: PoroModel,
    cell_count: int,
    variant_class: type[RetryVariant],
    *,
    trial_dt: float = 0.02,
    replay_dt: float = 0.01,
    finite_limit: float = 1.0e100,
) -> RetryComparison:
    direct = variant_class(model, cell_count)
    retry = variant_class(model, cell_count)
    events: list[dict[str, object]] = []

    direct_declared = _declared_context(model, direct.committed, replay_dt)
    events.append(_event(ordinal=1, history_id="DIRECT", event="BeginAttempt", attempt_id="DIRECT", variant=direct, note="declared_direct"))
    direct_candidate = direct.evaluate("DIRECT", replay_dt)
    direct_persistent = direct.persistent_hash
    events.append(_event(ordinal=2, history_id="DIRECT", event="TrialEvaluate", attempt_id="DIRECT", variant=direct, candidate=direct_candidate, note="direct_candidate"))
    direct.accept(direct_candidate)
    events.append(_event(ordinal=3, history_id="DIRECT", event="AcceptIncrement", attempt_id="DIRECT", variant=direct, candidate=direct_candidate, accepted=True, note="direct_accept"))

    initial_retry_hash = retry.committed.fingerprint
    events.append(_event(ordinal=4, history_id="RETRY", event="BeginAttempt", attempt_id="REJECTED_TRIAL", variant=retry, note="begin_rejected_trial"))
    rejected = retry.evaluate("REJECTED_TRIAL", trial_dt)
    events.append(_event(ordinal=5, history_id="RETRY", event="TrialEvaluate", attempt_id="REJECTED_TRIAL", variant=retry, candidate=rejected, note="candidate_will_be_rejected"))
    retry.reject(rejected)
    events.append(_event(ordinal=6, history_id="RETRY", event="RejectAttempt", attempt_id="REJECTED_TRIAL", variant=retry, candidate=rejected, note="candidate_unreachable"))
    committed_unchanged = retry.committed.fingerprint == initial_retry_hash
    unreachable = not retry.candidate_reachable(rejected)

    replay_declared = _declared_context(model, retry.committed, replay_dt)
    events.append(_event(ordinal=7, history_id="RETRY", event="BeginAttempt", attempt_id="REPLAY", variant=retry, note="equal_declared_replay"))
    replay = retry.evaluate("REPLAY", replay_dt)
    replay_persistent = retry.persistent_hash
    events.append(_event(ordinal=8, history_id="RETRY", event="TrialEvaluate", attempt_id="REPLAY", variant=retry, candidate=replay, note="replay_candidate"))
    retry.accept(replay)
    events.append(_event(ordinal=9, history_id="RETRY", event="AcceptIncrement", attempt_id="REPLAY", variant=retry, candidate=replay, accepted=True, note="replay_accept"))

    direct_observed = _observed(direct_candidate, direct_persistent)
    replay_observed = _observed(replay, replay_persistent)
    drift = pressure_l2_drift(direct.committed.pressure, retry.committed.pressure)
    settlement_drift = abs(settlement(model, direct.committed.pressure) - settlement(model, retry.committed.pressure))
    finite_values = (
        *direct_candidate.finite_values,
        *rejected.finite_values,
        *replay.finite_values,
        *direct.committed.pressure,
        *retry.committed.pressure,
    )
    finite = all(math.isfinite(value) and abs(value) <= finite_limit for value in finite_values)
    return RetryComparison(
        variant=direct.name,
        direct_state=direct.committed,
        retry_state=retry.committed,
        direct_candidate=direct_candidate,
        rejected_candidate=rejected,
        replay_candidate=replay,
        declared_context_equal=direct_declared == replay_declared,
        committed_before_replay_unchanged=committed_unchanged,
        rejected_candidate_unreachable=unreachable,
        accepted_pressure_exact=direct.committed.pressure == retry.committed.pressure,
        accepted_state_fingerprint_exact=direct.committed.fingerprint == retry.committed.fingerprint,
        observed_replay_fingerprint_equal=direct_observed == replay_observed,
        pressure_l2_drift=drift,
        settlement_drift=settlement_drift,
        declared_mass_defect=abs(replay.declared_mass_defect),
        all_values_finite=finite,
        events=tuple(events),
    )
