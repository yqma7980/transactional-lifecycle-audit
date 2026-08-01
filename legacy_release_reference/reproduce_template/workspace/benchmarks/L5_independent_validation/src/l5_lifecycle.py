"""Independent accepted-output and retry lifecycle controls for L5-D1."""

from __future__ import annotations

from dataclasses import dataclass
import math

from .l5_solver import commit, evaluate_candidate, snapshot
from .l5_state import (
    IndependentCandidate,
    IndependentCommitted,
    IndependentModel,
    IndependentSnapshot,
    binary_fingerprint,
    initial_committed,
)


class IndependentVariant:
    name="base"

    def __init__(self,model: IndependentModel,cell_count: int) -> None:
        self.model=model
        self.committed=initial_committed(cell_count)
        self._live=set()

    @property
    def persistent_fingerprint(self) -> str:
        raise NotImplementedError

    def source(self) -> tuple[float,...]:
        return self.committed.saturation_n

    def evaluate(self,attempt_id: str,dt: float) -> IndependentCandidate:
        candidate=evaluate_candidate(
            self.model,self.committed,dt,
            attempt_id=attempt_id,source_override=self.source(),
        )
        self._live.add(candidate.fingerprint)
        self.after_evaluate(candidate)
        return candidate

    def after_evaluate(self,candidate: IndependentCandidate) -> None:
        return None

    def accept(self,candidate: IndependentCandidate) -> None:
        if candidate.fingerprint not in self._live:
            raise RuntimeError("candidate is not live")
        self.committed=commit(self.committed,candidate)
        self._live.clear()

    def reject(self,candidate: IndependentCandidate) -> None:
        self._live.discard(candidate.fingerprint)

    def reachable(self,candidate: IndependentCandidate) -> bool:
        return candidate.fingerprint in self._live

    def accepted_output(self) -> IndependentSnapshot:
        return snapshot(self.model,self.committed)


class IndependentSafeVariant(IndependentVariant):
    name="independent_safe_transactional"

    @property
    def persistent_fingerprint(self) -> str:
        return binary_fingerprint(("no_mutable_physical_cache",))


class IndependentUnsafeVariant(IndependentVariant):
    name="independent_unsafe_previous_saturation"

    def __init__(self,model: IndependentModel,cell_count: int) -> None:
        super().__init__(model,cell_count)
        self._previous=self.committed.saturation_n

    @property
    def persistent_fingerprint(self) -> str:
        return binary_fingerprint(self._previous)

    def source(self) -> tuple[float,...]:
        return self._previous

    def after_evaluate(self,candidate: IndependentCandidate) -> None:
        self._previous=candidate.saturation_n


@dataclass(frozen=True)
class IndependentRetryResult:
    variant: str
    direct: IndependentSnapshot
    retry: IndependentSnapshot
    declared_context_equal: bool
    committed_unchanged_at_reject: bool
    rejected_candidate_unreachable: bool
    exact_saturation: bool
    exact_pressure: bool
    exact_displacement: bool
    exact_phase_masses: bool
    exact_committed_fingerprint: bool
    exact_output_fingerprint: bool
    observed_fingerprint_equal: bool
    saturation_l2_drift: float
    pressure_l2_drift: float
    displacement_drift: float
    declared_phase_mass_defect: float
    all_values_finite: bool
    events: tuple[dict[str,object],...]


def _declared(model: IndependentModel,state: IndependentCommitted,dt: float) -> str:
    return binary_fingerprint((model.fingerprint,state.fingerprint,dt,"L5-R1","L5-K1"))


def _observed(candidate: IndependentCandidate,persistent: str) -> str:
    return binary_fingerprint((candidate.saturation_n,candidate.declared_n_mass_defect,persistent))


def _l2(left: tuple[float,...],right: tuple[float,...],length: float=1.0) -> float:
    dx=length/len(left)
    return math.sqrt(math.fsum((a-b)**2 for a,b in zip(left,right))*dx)


def retry_comparison(
    variant_type: type[IndependentVariant],
    *,
    cell_count: int=32,
    trial_dt: float=0.01,
    replay_dt: float=0.0025,
) -> IndependentRetryResult:
    model=IndependentModel()
    direct=variant_type(model,cell_count)
    retry=variant_type(model,cell_count)
    events=[]

    direct_declared=_declared(model,direct.committed,replay_dt)
    direct_candidate=direct.evaluate("DIRECT",replay_dt)
    direct_persistent=direct.persistent_fingerprint
    events.append({"ordinal":1,"history":"DIRECT","event":"TrialEvaluate","accepted":False,"candidate":direct_candidate.fingerprint,"persistent":direct_persistent,"committed":direct.committed.fingerprint})
    direct.accept(direct_candidate)
    direct_output=direct.accepted_output()
    events.append({"ordinal":2,"history":"DIRECT","event":"AcceptIncrement","accepted":True,"candidate":direct_candidate.fingerprint,"persistent":direct.persistent_fingerprint,"committed":direct.committed.fingerprint,"output":direct_output.fingerprint})

    before=retry.committed.fingerprint
    rejected=retry.evaluate("REJECTED",trial_dt)
    events.append({"ordinal":3,"history":"RETRY","event":"TrialEvaluate","accepted":False,"candidate":rejected.fingerprint,"persistent":retry.persistent_fingerprint,"committed":retry.committed.fingerprint})
    retry.reject(rejected)
    unchanged=retry.committed.fingerprint==before
    unreachable=not retry.reachable(rejected)
    events.append({"ordinal":4,"history":"RETRY","event":"RejectAttempt","accepted":False,"candidate":rejected.fingerprint,"persistent":retry.persistent_fingerprint,"committed":retry.committed.fingerprint})

    replay_declared=_declared(model,retry.committed,replay_dt)
    replay=retry.evaluate("REPLAY",replay_dt)
    replay_persistent=retry.persistent_fingerprint
    events.append({"ordinal":5,"history":"RETRY","event":"TrialEvaluate","accepted":False,"candidate":replay.fingerprint,"persistent":replay_persistent,"committed":retry.committed.fingerprint})
    retry.accept(replay)
    retry_output=retry.accepted_output()
    events.append({"ordinal":6,"history":"RETRY","event":"AcceptIncrement","accepted":True,"candidate":replay.fingerprint,"persistent":retry.persistent_fingerprint,"committed":retry.committed.fingerprint,"output":retry_output.fingerprint})

    sat=_l2(direct_output.saturation_n,retry_output.saturation_n)
    pressure=_l2(direct_output.pressure,retry_output.pressure)
    displacement=abs(direct_output.displacement-retry_output.displacement)
    mass_defect=max(abs(replay.declared_n_mass_defect),abs(replay.declared_w_mass_defect))
    finite_values=(
        *direct_candidate.finite_values,*rejected.finite_values,*replay.finite_values,
        *direct_output.saturation_n,*direct_output.pressure,
        *retry_output.saturation_n,*retry_output.pressure,
        direct_output.displacement,retry_output.displacement,
    )
    return IndependentRetryResult(
        variant=direct.name,
        direct=direct_output,
        retry=retry_output,
        declared_context_equal=direct_declared==replay_declared,
        committed_unchanged_at_reject=unchanged,
        rejected_candidate_unreachable=unreachable,
        exact_saturation=direct_output.saturation_n==retry_output.saturation_n,
        exact_pressure=direct_output.pressure==retry_output.pressure,
        exact_displacement=direct_output.displacement==retry_output.displacement,
        exact_phase_masses=(direct_output.phase_mass_n==retry_output.phase_mass_n and direct_output.phase_mass_w==retry_output.phase_mass_w),
        exact_committed_fingerprint=direct.committed.fingerprint==retry.committed.fingerprint,
        exact_output_fingerprint=direct_output.fingerprint==retry_output.fingerprint,
        observed_fingerprint_equal=_observed(direct_candidate,direct_persistent)==_observed(replay,replay_persistent),
        saturation_l2_drift=sat,
        pressure_l2_drift=pressure,
        displacement_drift=displacement,
        declared_phase_mass_defect=mass_defect,
        all_values_finite=all(math.isfinite(v) and abs(v)<=1.0e100 for v in finite_values),
        events=tuple(events),
    )


def accepted_output_probe(cell_count: int=32,trial_dt: float=0.005) -> dict[str,object]:
    model=IndependentModel()
    host=IndependentSafeVariant(model,cell_count)
    before=host.accepted_output()
    committed_before=host.committed.fingerprint
    candidate=host.evaluate("LIVE_UNACCEPTED",trial_dt)
    reachable_while_live=host.reachable(candidate)
    during=host.accepted_output()
    host.reject(candidate)
    return {
        "committed_before":committed_before,
        "committed_after":host.committed.fingerprint,
        "candidate_fingerprint":candidate.fingerprint,
        "candidate_reachable_while_output":reachable_while_live,
        "candidate_unreachable_after_reject":not host.reachable(candidate),
        "output_before_fingerprint":before.fingerprint,
        "output_during_fingerprint":during.fingerprint,
        "output_exact":before==during,
        "committed_unchanged":committed_before==host.committed.fingerprint,
        "all_values_finite":all(math.isfinite(v) for v in (*during.saturation_n,*during.pressure,during.displacement)),
        "events":(
            {"ordinal":1,"event":"TrialEvaluate","candidate":candidate.fingerprint,"candidate_reachable":True,"committed":committed_before,"output":"NA"},
            {"ordinal":2,"event":"OutputAcceptedState","candidate":candidate.fingerprint,"candidate_reachable":True,"committed":host.committed.fingerprint,"output":during.fingerprint},
            {"ordinal":3,"event":"RejectAttempt","candidate":candidate.fingerprint,"candidate_reachable":False,"committed":host.committed.fingerprint,"output":"NA"},
        ),
    }
