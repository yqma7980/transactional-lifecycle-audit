from __future__ import annotations

from .model import (
    AdjudicationRequest,
    AdjudicationResult,
    Outcome,
    PrecomparisonRelation,
    Verdict,
)


SCHEMA_VERSION = "JSS-P5B-CASE-RESULT-1.0"
IMPLEMENTATION_VERSION = "JSS-P5B-IMPL-1.0"


def _result(
    request: AdjudicationRequest,
    *,
    verdict: Verdict | None,
    outcome: Outcome,
    stage: str,
    applicability_evaluated: bool,
    eligibility_evaluated: bool,
    lifecycle_evaluated: bool,
    mismatch_fields: tuple[str, ...],
    reasons: tuple[str, ...],
) -> AdjudicationResult:
    return AdjudicationResult(
        schema_version=SCHEMA_VERSION,
        implementation_version=IMPLEMENTATION_VERSION,
        case_id=request.case_id,
        run_id=request.run_id,
        subject_id=request.subject_id,
        partition=request.partition,
        expected_verdict=request.expected_verdict,
        verdict=verdict,
        outcome=outcome,
        stage=stage,
        pass_flag=verdict is not None and verdict is request.expected_verdict,
        applicability_evaluated=applicability_evaluated,
        eligibility_evaluated=eligibility_evaluated,
        lifecycle_evaluated=lifecycle_evaluated,
        capability=request.capability,
        packet_a_fingerprint=request.packet_a.fingerprint,
        packet_b_fingerprint=request.packet_b.fingerprint,
        mismatch_fields=mismatch_fields,
        active_signals=(
            request.lifecycle_signals.active_names if lifecycle_evaluated else ()
        ),
        reasons=reasons,
    )


def adjudicate(request: AdjudicationRequest) -> AdjudicationResult:
    if request.execution_error is not None:
        return _result(
            request,
            verdict=None,
            outcome=Outcome.EXECUTION_ERROR,
            stage="EXECUTION",
            applicability_evaluated=False,
            eligibility_evaluated=False,
            lifecycle_evaluated=False,
            mismatch_fields=(),
            reasons=(request.execution_error,),
        )

    if not request.capability.observable:
        missing = request.capability.missing_fields + request.capability.missing_events
        return _result(
            request,
            verdict=Verdict.NOT_SUPPORTED,
            outcome=Outcome.NOT_SUPPORTED,
            stage="APPLICABILITY",
            applicability_evaluated=True,
            eligibility_evaluated=False,
            lifecycle_evaluated=False,
            mismatch_fields=(),
            reasons=tuple(f"missing:{item}" for item in missing),
        )

    mismatch_fields = request.packet_a.differing_fields(request.packet_b)
    if request.precomparison_relation is PrecomparisonRelation.NOT_EVALUATED:
        return _result(
            request,
            verdict=None,
            outcome=Outcome.EXECUTION_ERROR,
            stage="ELIGIBILITY",
            applicability_evaluated=True,
            eligibility_evaluated=True,
            lifecycle_evaluated=False,
            mismatch_fields=mismatch_fields,
            reasons=("eligibility_relation_not_evaluated",),
        )

    if request.precomparison_relation is PrecomparisonRelation.INCOMPATIBLE:
        return _result(
            request,
            verdict=Verdict.INVALID,
            outcome=Outcome.INVALID,
            stage="ELIGIBILITY",
            applicability_evaluated=True,
            eligibility_evaluated=True,
            lifecycle_evaluated=False,
            mismatch_fields=mismatch_fields,
            reasons=("precomparison_relation_incompatible",),
        )

    if request.lifecycle_signals.detected:
        return _result(
            request,
            verdict=Verdict.DETECT_LIFECYCLE_DRIFT,
            outcome=Outcome.DETECT_LIFECYCLE_DRIFT,
            stage="LIFECYCLE",
            applicability_evaluated=True,
            eligibility_evaluated=True,
            lifecycle_evaluated=True,
            mismatch_fields=mismatch_fields,
            reasons=tuple(f"signal:{name}" for name in request.lifecycle_signals.active_names),
        )

    return _result(
        request,
        verdict=Verdict.PASS_INVARIANT,
        outcome=Outcome.PASS_INVARIANT,
        stage="LIFECYCLE",
        applicability_evaluated=True,
        eligibility_evaluated=True,
        lifecycle_evaluated=True,
        mismatch_fields=mismatch_fields,
        reasons=("eligible_history_invariant",),
    )
