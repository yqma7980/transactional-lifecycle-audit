from __future__ import annotations

import unittest

from jss_p5b.adjudication import adjudicate
from jss_p5b.model import (
    AdjudicationRequest,
    CapabilityReport,
    LifecycleSignals,
    Outcome,
    PrecomparisonRelation,
    Verdict,
)

from helpers import base_packet


def request(
    *,
    expected: Verdict,
    capability: CapabilityReport | None = None,
    relation: PrecomparisonRelation = PrecomparisonRelation.COMPATIBLE,
    signals: LifecycleSignals | None = None,
    execution_error: str | None = None,
) -> AdjudicationRequest:
    packet = base_packet()
    return AdjudicationRequest(
        case_id="P5B-UNIT-01",
        run_id="unit_run_1",
        subject_id="JSS-S02",
        partition="PREFLIGHT_ONLY",
        expected_verdict=expected,
        capability=capability
        or CapabilityReport(
            observable=True,
            required_tokens=("UNIT",),
            available_tokens=("UNIT",),
        ),
        packet_a=packet,
        packet_b=packet,
        precomparison_relation=relation,
        lifecycle_signals=signals or LifecycleSignals(),
        execution_error=execution_error,
    )


class AdjudicationTests(unittest.TestCase):
    def test_pass_invariant(self) -> None:
        result = adjudicate(request(expected=Verdict.PASS_INVARIANT))
        self.assertEqual(result.verdict, Verdict.PASS_INVARIANT)
        self.assertTrue(result.pass_flag)
        self.assertTrue(result.lifecycle_evaluated)

    def test_execution_error_precedes_every_stage(self) -> None:
        unsupported = CapabilityReport(
            observable=False,
            required_tokens=("NATIVE",),
            missing_events=("NATIVE",),
        )
        result = adjudicate(
            request(
                expected=Verdict.NOT_SUPPORTED,
                capability=unsupported,
                relation=PrecomparisonRelation.INCOMPATIBLE,
                signals=LifecycleSignals(operator_replay_drift=True),
                execution_error="nonfinite_required_packet",
            )
        )
        self.assertEqual(result.outcome, Outcome.EXECUTION_ERROR)
        self.assertIsNone(result.verdict)
        self.assertFalse(result.applicability_evaluated)
        self.assertFalse(result.lifecycle_evaluated)
        self.assertEqual(result.active_signals, ())

    def test_not_supported_precedes_eligibility(self) -> None:
        capability = CapabilityReport(
            observable=False,
            required_tokens=("NATIVE_VERSION",),
            missing_fields=("NATIVE_VERSION",),
        )
        result = adjudicate(
            request(
                expected=Verdict.NOT_SUPPORTED,
                capability=capability,
                relation=PrecomparisonRelation.INCOMPATIBLE,
                signals=LifecycleSignals(within_history_version_violation=True),
            )
        )
        self.assertEqual(result.verdict, Verdict.NOT_SUPPORTED)
        self.assertFalse(result.eligibility_evaluated)
        self.assertFalse(result.lifecycle_evaluated)
        self.assertEqual(result.active_signals, ())

    def test_invalid_stops_before_drift(self) -> None:
        result = adjudicate(
            request(
                expected=Verdict.INVALID,
                relation=PrecomparisonRelation.INCOMPATIBLE,
                signals=LifecycleSignals(operator_replay_drift=True),
            )
        )
        self.assertEqual(result.verdict, Verdict.INVALID)
        self.assertFalse(result.lifecycle_evaluated)
        self.assertEqual(result.active_signals, ())

    def test_f08_precomparison_mismatch_is_invalid(self) -> None:
        result = adjudicate(
            request(
                expected=Verdict.INVALID,
                relation=PrecomparisonRelation.INCOMPATIBLE,
            )
        )
        self.assertEqual(result.verdict, Verdict.INVALID)

    def test_f08_within_history_violation_is_detect(self) -> None:
        result = adjudicate(
            request(
                expected=Verdict.DETECT_LIFECYCLE_DRIFT,
                signals=LifecycleSignals(within_history_version_violation=True),
            )
        )
        self.assertEqual(result.verdict, Verdict.DETECT_LIFECYCLE_DRIFT)
        self.assertEqual(result.active_signals, ("within_history_version_violation",))

    def test_f08_unavailable_metadata_is_not_supported(self) -> None:
        capability = CapabilityReport(
            observable=False,
            required_tokens=("VERSION_METADATA",),
            missing_fields=("VERSION_METADATA",),
        )
        result = adjudicate(
            request(expected=Verdict.NOT_SUPPORTED, capability=capability)
        )
        self.assertEqual(result.verdict, Verdict.NOT_SUPPORTED)

    def test_f08_declared_compatible_lag_is_pass(self) -> None:
        result = adjudicate(request(expected=Verdict.PASS_INVARIANT))
        self.assertEqual(result.verdict, Verdict.PASS_INVARIANT)

    def test_not_evaluated_relation_is_execution_error_when_observable(self) -> None:
        result = adjudicate(
            request(
                expected=Verdict.PASS_INVARIANT,
                relation=PrecomparisonRelation.NOT_EVALUATED,
            )
        )
        self.assertEqual(result.outcome, Outcome.EXECUTION_ERROR)
        self.assertIsNone(result.verdict)


if __name__ == "__main__":
    unittest.main()

