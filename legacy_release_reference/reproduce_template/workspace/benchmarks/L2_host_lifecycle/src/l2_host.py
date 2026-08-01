"""Deterministic single-threaded Newton host for L2-D1."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

from .l2_model import evaluate_element
from .l2_schema import EVENT_COLUMNS
from .l2_state import (
    DESIGN_VERSION,
    HOST_VERSION,
    AcceptedCheckpoint,
    ElementData,
    ElementResult,
    canonical_hash,
    make_checkpoint,
)


class HostFailure(RuntimeError):
    """Raised when a frozen host hard gate is violated."""


@dataclass(frozen=True)
class HostControls:
    maximum_iterations: int = 12
    residual_tolerance: float = 1.0e-12
    correction_reporting_tolerance: float = 1.0e-12
    tangent_floor: float = 1.0e-14
    finite_limit: float = 1.0e100
    thread_count: int = 1


@dataclass(frozen=True)
class ProbeResult:
    result: ElementResult
    committed_unchanged: bool
    candidate_unreachable: bool


class NewtonHost:
    def __init__(
        self,
        *,
        run_id: str,
        case_id: str,
        history_id: str,
        variant: Any,
        configuration_hash: str,
        controls: HostControls | None = None,
    ) -> None:
        self.run_id = run_id
        self.case_id = case_id
        self.history_id = history_id
        self.variant = variant
        self.configuration_hash = configuration_hash
        self.controls = controls or HostControls()
        self.element = ElementData()
        self.events: list[dict[str, Any]] = []
        self.checkpoints: list[AcceptedCheckpoint] = []
        self.call_index = 0
        self.increment_id = 0
        self.accepted_displacement = 0.0

    def _blank_event(self) -> dict[str, Any]:
        return {column: "NA" for column in EVENT_COLUMNS}

    def _append_event(self, **values: Any) -> None:
        row = self._blank_event()
        row.update(
            {
                "design_version": DESIGN_VERSION,
                "host_version": HOST_VERSION,
                "run_id": self.run_id,
                "case_id": self.case_id,
                "history_id": self.history_id,
                "variant": self.variant.name,
                "thread_count": self.controls.thread_count,
            }
        )
        unknown = set(values) - set(row)
        if unknown:
            raise KeyError(f"Unknown event columns: {sorted(unknown)}")
        row.update(values)
        self.events.append(row)

    def _begin_attempt(
        self,
        attempt_id: str,
        *,
        target_force: float,
        increment_id: int,
        retry_parent_id: str = "NA",
    ) -> None:
        before = self.variant.committed
        persistent = self.variant.persistent_hash
        self.variant.begin_attempt(attempt_id)
        self._append_event(
            increment_id=increment_id,
            attempt_id=attempt_id,
            iteration_id=0,
            call_index=self.call_index,
            event="BeginAttempt",
            accepted_flag=False,
            cutback_flag=retry_parent_id != "NA",
            retry_parent_id=retry_parent_id,
            target_force=target_force,
            requested_dtime_factor=0.5 if retry_parent_id != "NA" else 1.0,
            committed_version_before=before.accepted_version,
            committed_version_after=self.variant.committed.accepted_version,
            committed_state_hash_before=before.fingerprint,
            committed_state_hash_after=self.variant.committed.fingerprint,
            persistent_state_hash_before=persistent,
            persistent_state_hash_after=self.variant.persistent_hash,
            persistent_state_class=self.variant.persistent_state_class,
            finite=True,
            event_valid=before.fingerprint == self.variant.committed.fingerprint,
            note="attempt_opened",
        )

    def _evaluate(
        self,
        *,
        displacement: float,
        force: float,
        attempt_id: str,
        increment_id: int,
        iteration_id: int,
    ) -> ElementResult:
        before = self.variant.committed
        persistent_before = self.variant.persistent_hash
        candidate_id = f"{attempt_id}:candidate:{self.call_index}"
        result = evaluate_element(
            self.variant,
            self.element,
            case_id=self.case_id,
            history_id=self.history_id,
            configuration_hash=self.configuration_hash,
            displacement=displacement,
            force=force,
            candidate_id=candidate_id,
            attempt_id=attempt_id,
            source_call_index=self.call_index,
        )
        finite = all(
            math.isfinite(value) and abs(value) <= self.controls.finite_limit
            for value in result.finite_values
        )
        self._append_event(
            increment_id=increment_id,
            attempt_id=attempt_id,
            iteration_id=iteration_id,
            call_index=self.call_index,
            event="TrialEvaluate",
            accepted_flag=False,
            cutback_flag=False,
            target_force=force,
            requested_dtime_factor=1.0,
            displacement=displacement,
            reaction=result.sigma,
            residual=result.residual,
            tangent=result.tangent,
            correction="NA",
            declared_packet_hash=result.declared_packet_hash,
            primary_state_hash=canonical_hash(
                {"displacement": displacement, "force": force}
            ),
            committed_version_before=before.accepted_version,
            committed_version_after=self.variant.committed.accepted_version,
            committed_state_hash_before=before.fingerprint,
            committed_state_hash_after=self.variant.committed.fingerprint,
            candidate_id=result.candidate.candidate_id,
            candidate_state_hash=result.candidate.fingerprint,
            candidate_reachable_after=self.variant.candidate_reachable(
                result.candidate.candidate_id
            ),
            persistent_state_hash_before=persistent_before,
            persistent_state_hash_after=self.variant.persistent_hash,
            persistent_state_class=self.variant.persistent_state_class,
            residual_state_version=result.material.residual_state_version,
            tangent_state_version=result.material.tangent_state_version,
            operator_hash=result.operator_hash,
            finite=finite,
            event_valid=finite and result.version_compatible,
            note="candidate_formed",
        )
        self.call_index += 1
        if not finite:
            raise HostFailure("Non-finite or over-limit trial operator")
        return result

    def _reject_attempt(
        self,
        attempt_id: str,
        *,
        increment_id: int,
        reason: str,
        candidate_ids: tuple[str, ...],
        retry_parent_id: str = "NA",
    ) -> tuple[bool, bool]:
        before = self.variant.committed
        persistent_before = self.variant.persistent_hash
        self.variant.reject_attempt(attempt_id)
        committed_unchanged = before.fingerprint == self.variant.committed.fingerprint
        candidate_unreachable = all(
            not self.variant.candidate_reachable(value) for value in candidate_ids
        )
        self._append_event(
            increment_id=increment_id,
            attempt_id=attempt_id,
            iteration_id="NA",
            call_index=self.call_index,
            event="RejectAttempt",
            accepted_flag=False,
            reject_reason=reason,
            cutback_flag=True,
            retry_parent_id=retry_parent_id,
            requested_dtime_factor=0.5,
            committed_version_before=before.accepted_version,
            committed_version_after=self.variant.committed.accepted_version,
            committed_state_hash_before=before.fingerprint,
            committed_state_hash_after=self.variant.committed.fingerprint,
            candidate_id=";".join(candidate_ids) if candidate_ids else "NA",
            candidate_reachable_after=not candidate_unreachable,
            persistent_state_hash_before=persistent_before,
            persistent_state_hash_after=self.variant.persistent_hash,
            persistent_state_class=self.variant.persistent_state_class,
            finite=True,
            event_valid=committed_unchanged and candidate_unreachable,
            note="attempt_rejected",
        )
        return committed_unchanged, candidate_unreachable

    def replay_probe(
        self,
        *,
        attempt_id: str,
        displacement: float,
        force: float,
    ) -> ProbeResult:
        self._begin_attempt(
            attempt_id,
            target_force=force,
            increment_id=0,
        )
        result = self._evaluate(
            displacement=displacement,
            force=force,
            attempt_id=attempt_id,
            increment_id=0,
            iteration_id=1,
        )
        committed_unchanged, candidate_unreachable = self._reject_attempt(
            attempt_id,
            increment_id=0,
            reason="READ_ONLY_REPLAY_PROBE",
            candidate_ids=(result.candidate.candidate_id,),
        )
        return ProbeResult(
            result=result,
            committed_unchanged=committed_unchanged,
            candidate_unreachable=candidate_unreachable,
        )

    def inject_forced_retry(
        self,
        *,
        attempt_id: str,
        displacement: float,
        force: float,
    ) -> ProbeResult:
        self._begin_attempt(
            attempt_id,
            target_force=force,
            increment_id=0,
        )
        result = self._evaluate(
            displacement=displacement,
            force=force,
            attempt_id=attempt_id,
            increment_id=0,
            iteration_id=1,
        )
        committed_unchanged, candidate_unreachable = self._reject_attempt(
            attempt_id,
            increment_id=0,
            reason="INJECTED_AFTER_CANDIDATE_FORMATION",
            candidate_ids=(result.candidate.candidate_id,),
            retry_parent_id=attempt_id,
        )
        return ProbeResult(
            result=result,
            committed_unchanged=committed_unchanged,
            candidate_unreachable=candidate_unreachable,
        )

    def solve_increment(
        self,
        *,
        target_force: float,
        attempt_id: str,
        retry_parent_id: str = "NA",
    ) -> AcceptedCheckpoint:
        self.increment_id += 1
        increment_id = self.increment_id
        self._begin_attempt(
            attempt_id,
            target_force=target_force,
            increment_id=increment_id,
            retry_parent_id=retry_parent_id,
        )
        displacement = self.accepted_displacement
        candidate_ids: list[str] = []
        for iteration_id in range(1, self.controls.maximum_iterations + 1):
            result = self._evaluate(
                displacement=displacement,
                force=target_force,
                attempt_id=attempt_id,
                increment_id=increment_id,
                iteration_id=iteration_id,
            )
            candidate_ids.append(result.candidate.candidate_id)
            if abs(result.residual) <= self.controls.residual_tolerance:
                before = self.variant.committed
                persistent_before = self.variant.persistent_hash
                accepted, reason = self.variant.accept(result.candidate)
                if not accepted:
                    raise HostFailure(f"Candidate acceptance failed: {reason}")
                after = self.variant.committed
                checkpoint = make_checkpoint(
                    force=target_force,
                    displacement=displacement,
                    result=result,
                    committed=after,
                )
                self.accepted_displacement = displacement
                self.checkpoints.append(checkpoint)
                self._append_event(
                    increment_id=increment_id,
                    attempt_id=attempt_id,
                    iteration_id=iteration_id,
                    call_index=self.call_index,
                    event="AcceptIncrement",
                    accepted_flag=True,
                    cutback_flag=retry_parent_id != "NA",
                    retry_parent_id=retry_parent_id,
                    target_force=target_force,
                    requested_dtime_factor=(
                        0.5 if retry_parent_id != "NA" else 1.0
                    ),
                    displacement=displacement,
                    reaction=result.sigma,
                    residual=result.residual,
                    tangent=result.tangent,
                    correction=0.0,
                    declared_packet_hash=result.declared_packet_hash,
                    primary_state_hash=canonical_hash(
                        {"displacement": displacement, "force": target_force}
                    ),
                    committed_version_before=before.accepted_version,
                    committed_version_after=after.accepted_version,
                    committed_state_hash_before=before.fingerprint,
                    committed_state_hash_after=after.fingerprint,
                    candidate_id=result.candidate.candidate_id,
                    candidate_state_hash=result.candidate.fingerprint,
                    candidate_reachable_after=self.variant.candidate_reachable(
                        result.candidate.candidate_id
                    ),
                    persistent_state_hash_before=persistent_before,
                    persistent_state_hash_after=self.variant.persistent_hash,
                    persistent_state_class=self.variant.persistent_state_class,
                    residual_state_version=result.material.residual_state_version,
                    tangent_state_version=result.material.tangent_state_version,
                    operator_hash=result.operator_hash,
                    finite=True,
                    event_valid=True,
                    note=reason,
                )
                return checkpoint

            if abs(result.tangent) < self.controls.tangent_floor:
                self._reject_attempt(
                    attempt_id,
                    increment_id=increment_id,
                    reason="TANGENT_BELOW_FLOOR",
                    candidate_ids=tuple(candidate_ids),
                )
                raise HostFailure("Tangent below frozen floor")

            correction = -result.residual / result.tangent
            self.events[-1]["correction"] = correction
            if not math.isfinite(correction):
                raise HostFailure("Non-finite Newton correction")
            displacement += correction

        self._reject_attempt(
            attempt_id,
            increment_id=increment_id,
            reason="MAXIMUM_ITERATIONS",
            candidate_ids=tuple(candidate_ids),
        )
        raise HostFailure("Maximum Newton iterations reached")
