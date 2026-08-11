"""Safe and seeded-unsafe retry lifecycle variants for L4-D1."""

from __future__ import annotations

from dataclasses import dataclass
import math

from .l4_fv import (
    accept_candidate,
    l2_drift,
    make_candidate,
    make_snapshot,
)
from .l4_state import (
    canonical_hash,
    CommittedState,
    TrialCandidate,
    TwoPhaseModel,
    initial_state,
)


class RetryVariant:
    name = "base"

    def __init__(self, model: TwoPhaseModel, cell_count: int) -> None:
        self.model = model
        self.committed = initial_state(cell_count)
        self._live: set[str] = set()

    @property
    def persistent_hash(self) -> str:
        raise NotImplementedError

    def previous_state(self) -> tuple[float, ...]:
        return self.committed.saturation_n

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


class UnsafePreviousSaturationCacheVariant(RetryVariant):
    name = "unsafe_previous_saturation_cache"

    def __init__(self, model: TwoPhaseModel, cell_count: int) -> None:
        super().__init__(model, cell_count)
        self.hidden_previous_saturation = self.committed.saturation_n

    @property
    def persistent_hash(self) -> str:
        return canonical_hash(
            {
                "kind": self.name,
                "hidden_previous_saturation": self.hidden_previous_saturation,
            }
        )

    def previous_state(self) -> tuple[float, ...]:
        return self.hidden_previous_saturation

    def after_evaluate(self, candidate: TrialCandidate) -> None:
        super().after_evaluate(candidate)
        self.hidden_previous_saturation = candidate.saturation_n


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
    accepted_saturation_exact: bool
    accepted_pressure_exact: bool
    accepted_displacement_exact: bool
    accepted_phase_masses_exact: bool
    accepted_state_fingerprint_exact: bool
    accepted_output_fingerprint_exact: bool
    observed_replay_fingerprint_equal: bool
    saturation_l2_drift: float
    pressure_l2_drift: float
    displacement_drift: float
    declared_phase_mass_defect: float
    all_values_finite: bool
    events: tuple[dict[str, object], ...]


def _declared_context(
    model: TwoPhaseModel, state: CommittedState, dt: float
) -> str:
    return canonical_hash(
        {
            "model": model.fingerprint,
            "committed": state.fingerprint,
            "dt": dt,
            "residual_version": "L4-FV-R1",
            "operator_version": "L4-FV-K1",
        }
    )


def _observed(candidate: TrialCandidate, persistent_hash: str) -> str:
    return canonical_hash(
        {
            "saturation_n": candidate.saturation_n,
            "declared_n_mass_defect": candidate.declared_n_mass_defect,
            "declared_w_mass_defect": candidate.declared_w_mass_defect,
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
    saturation = candidate.saturation_n if candidate else variant.committed.saturation_n
    if accepted:
        snapshot = make_snapshot(variant.model, variant.committed)
    else:
        pressure = make_snapshot(
            variant.model,
            CommittedState(
                time=candidate.time if candidate else variant.committed.time,
                saturation_n=saturation,
                cumulative_n_in=candidate.cumulative_n_in if candidate else variant.committed.cumulative_n_in,
                cumulative_n_out=candidate.cumulative_n_out if candidate else variant.committed.cumulative_n_out,
                cumulative_w_in=candidate.cumulative_w_in if candidate else variant.committed.cumulative_w_in,
                cumulative_w_out=candidate.cumulative_w_out if candidate else variant.committed.cumulative_w_out,
                accepted_version=variant.committed.accepted_version,
            ),
        )
        snapshot = pressure
    finite_values = (
        *(candidate.finite_values if candidate else saturation),
        *snapshot.pressure,
        snapshot.displacement,
        snapshot.phase_mass_n,
        snapshot.phase_mass_w,
    )
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
        "output_provenance_fingerprint": snapshot.physical_hash if accepted else "NA",
        "minimum_saturation_n": min(saturation),
        "maximum_saturation_n": max(saturation),
        "minimum_pressure": min(snapshot.pressure),
        "maximum_pressure": max(snapshot.pressure),
        "phase_mass_n": snapshot.phase_mass_n,
        "phase_mass_w": snapshot.phase_mass_w,
        "front_location": snapshot.front_location,
        "displacement": snapshot.displacement,
        "flux_n_in": candidate.flux_n_in if candidate else 0.0,
        "flux_n_out": candidate.flux_n_out if candidate else 0.0,
        "flux_w_in": candidate.flux_w_in if candidate else 0.0,
        "flux_w_out": candidate.flux_w_out if candidate else 0.0,
        "mass_defect_n": candidate.declared_n_mass_defect if candidate else 0.0,
        "mass_defect_w": candidate.declared_w_mass_defect if candidate else 0.0,
        "finite": all(
            math.isfinite(value) and abs(value) <= 1.0e100
            for value in finite_values
        ),
        "note": note,
    }


def compare_retry(
    model: TwoPhaseModel,
    cell_count: int,
    variant_class: type[RetryVariant],
    *,
    trial_dt: float = 0.01,
    replay_dt: float = 0.005,
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
    events.append(_event(ordinal=3, history_id="DIRECT", event="AcceptIncrement", attempt_id="DIRECT", variant=direct, candidate=direct_candidate, accepted=True, note="accepted_output_from_committed"))

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
    events.append(_event(ordinal=9, history_id="RETRY", event="AcceptIncrement", attempt_id="REPLAY", variant=retry, candidate=replay, accepted=True, note="accepted_output_from_committed"))

    direct_snapshot = make_snapshot(model, direct.committed)
    retry_snapshot = make_snapshot(model, retry.committed)
    direct_observed = _observed(direct_candidate, direct_persistent)
    retry_observed = _observed(replay, replay_persistent)
    saturation_drift = l2_drift(
        direct_snapshot.saturation_n, retry_snapshot.saturation_n, model.H
    )
    pressure_drift = l2_drift(
        direct_snapshot.pressure, retry_snapshot.pressure, model.H
    )
    displacement_drift = abs(
        direct_snapshot.displacement - retry_snapshot.displacement
    )
    declared_mass_defect = max(
        abs(replay.declared_n_mass_defect), abs(replay.declared_w_mass_defect)
    )
    finite_values = (
        *direct_candidate.finite_values,
        *rejected.finite_values,
        *replay.finite_values,
        *direct_snapshot.saturation_n,
        *direct_snapshot.pressure,
        *retry_snapshot.saturation_n,
        *retry_snapshot.pressure,
        direct_snapshot.displacement,
        retry_snapshot.displacement,
    )
    finite = all(
        math.isfinite(value) and abs(value) <= finite_limit
        for value in finite_values
    )
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
        accepted_saturation_exact=direct_snapshot.saturation_n == retry_snapshot.saturation_n,
        accepted_pressure_exact=direct_snapshot.pressure == retry_snapshot.pressure,
        accepted_displacement_exact=direct_snapshot.displacement == retry_snapshot.displacement,
        accepted_phase_masses_exact=(
            direct_snapshot.phase_mass_n == retry_snapshot.phase_mass_n
            and direct_snapshot.phase_mass_w == retry_snapshot.phase_mass_w
        ),
        accepted_state_fingerprint_exact=direct.committed.fingerprint == retry.committed.fingerprint,
        accepted_output_fingerprint_exact=direct_snapshot.physical_hash == retry_snapshot.physical_hash,
        observed_replay_fingerprint_equal=direct_observed == retry_observed,
        saturation_l2_drift=saturation_drift,
        pressure_l2_drift=pressure_drift,
        displacement_drift=displacement_drift,
        declared_phase_mass_defect=declared_mass_defect,
        all_values_finite=finite,
        events=tuple(events),
    )

