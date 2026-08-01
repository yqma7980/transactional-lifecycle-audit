"""Future execution tests for L2-D2.0a; not run during implementation freeze."""

from __future__ import annotations

from fractions import Fraction
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

from oracle.l2_d2_fraction_oracle import derive_callback_order_oracle
from src.l2_d2_callback_order import (
    AUTHORITATIVE_COMMITTED_HASH,
    AUTHORIZED_CASES,
    FORBIDDEN_EVENTS,
    build_direct_history,
    build_extra_history,
    execute_callback_order_case,
    load_frozen_design,
)
from src.l2_state import CommittedState, canonical_json


ROOT = Path(__file__).resolve().parents[1]


class CallbackOrderStaticContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.freeze, self.matrix = load_frozen_design(ROOT)

    def test_freeze_and_matrix_versions_match(self) -> None:
        self.assertEqual(self.freeze["design_version"], "L2-D2.0a")
        self.assertEqual(self.freeze["design_status"], "FROZEN_NOT_IMPLEMENTED")
        self.assertFalse(self.freeze["execution_authorized"])
        self.assertFalse(self.freeze["abaqus_used"])
        self.assertFalse(self.freeze["results_exist"])

    def test_two_case_ids_are_unique_and_exact(self) -> None:
        case_ids = tuple(row["case_id"] for row in self.matrix)
        self.assertEqual(case_ids, AUTHORIZED_CASES)
        self.assertEqual(len(case_ids), len(set(case_ids)))

    def test_direct_callback_schedule_is_exact(self) -> None:
        history = build_direct_history(self.freeze)
        self.assertEqual(
            tuple(packet.event for packet in history.packets),
            (
                "BeginAttempt",
                "TrialEvaluate",
                "FormResidual",
                "FormTangent",
                "RejectAttempt",
            ),
        )
        self.assertEqual(history.packets[1].u, Fraction(1, 200))
        self.assertEqual(history.packets[1].force, Fraction(1, 2))

    def test_extra_callback_schedule_is_exact(self) -> None:
        history = build_extra_history(self.freeze)
        self.assertEqual(
            tuple(packet.event for packet in history.packets),
            (
                "BeginAttempt",
                "TrialEvaluate",
                "FormResidual",
                "TrialEvaluate",
                "FormResidual",
                "RejectAttempt",
                "BeginAttempt",
                "TrialEvaluate",
                "FormResidual",
                "FormTangent",
                "RejectAttempt",
            ),
        )
        self.assertEqual(history.packets[1].u, Fraction(3, 100))
        self.assertEqual(history.packets[3].u, Fraction(-3, 100))
        self.assertEqual(history.packets[7].u, Fraction(1, 200))

    def test_forbidden_events_are_absent(self) -> None:
        events = {
            packet.event
            for history in (
                build_direct_history(self.freeze),
                build_extra_history(self.freeze),
            )
            for packet in history.packets
        }
        self.assertTrue(events.isdisjoint(FORBIDDEN_EVENTS))

    def test_trial_evaluate_counts_are_frozen(self) -> None:
        direct = build_direct_history(self.freeze)
        extra = build_extra_history(self.freeze)
        self.assertEqual(
            sum(packet.event == "TrialEvaluate" for packet in direct.packets),
            1,
        )
        self.assertEqual(
            sum(packet.event == "TrialEvaluate" for packet in extra.packets),
            3,
        )

    def test_d1_fingerprint_serializer_is_authoritative(self) -> None:
        committed = CommittedState()
        self.assertEqual(
            canonical_json(committed),
            self.freeze["declared_committed_state"]["canonical_payload_utf8"],
        )
        self.assertEqual(committed.fingerprint, AUTHORITATIVE_COMMITTED_HASH)


class CallbackOrderFractionOracleTests(unittest.TestCase):
    def test_safe_oracle_is_exact_zero(self) -> None:
        oracle = derive_callback_order_oracle()["safe_transactional"]
        self.assertEqual(oracle["delta_residual"], Fraction(0))
        self.assertEqual(oracle["delta_tangent"], Fraction(0))

    def test_unsafe_oracle_matches_frozen_intermediates(self) -> None:
        oracle = derive_callback_order_oracle()["unsafe_trial_cache"]
        positive = oracle["positive_callback"]
        negative = oracle["negative_callback"]
        hidden = oracle["hidden_after_extra"]
        replay = oracle["extra_replay"]
        self.assertEqual(positive["sigma"], Fraction(13, 11))
        self.assertEqual(negative["delta_gamma"], Fraction(4, 121))
        self.assertEqual(negative["sigma"], Fraction(-183, 121))
        self.assertEqual(hidden["epsilon_p"], Fraction(-9, 605))
        self.assertEqual(hidden["kappa"], Fraction(31, 605))
        self.assertEqual(replay["sigma"], Fraction(4141, 2662))
        self.assertEqual(replay["candidate_epsilon_p"], Fraction(-281, 26620))
        self.assertEqual(replay["candidate_kappa"], Fraction(1479, 26620))
        self.assertEqual(oracle["delta_residual"], Fraction(1405, 1331))
        self.assertEqual(oracle["delta_tangent"], Fraction(-1000, 11))


class CallbackOrderExecutionContractTests(unittest.TestCase):
    def test_co01_safe_exact_zero_replay_parity(self) -> None:
        result = execute_callback_order_case(ROOT, "L2-CO-01", "TEST-CO01")
        self.assertTrue(result.pass_flag)
        self.assertEqual(result.observed_classification, "PASS_CALLBACK_INVARIANCE")
        self.assertEqual(result.comparison["delta_residual"], 0.0)
        self.assertEqual(result.comparison["delta_tangent"], 0.0)
        self.assertTrue(result.comparison["observed_replay_fingerprint_equal"])

    def test_co01_committed_state_and_candidates_are_safe(self) -> None:
        result = execute_callback_order_case(ROOT, "L2-CO-01", "TEST-CO01-STATE")
        self.assertTrue(result.comparison["committed_state_unchanged"])
        self.assertTrue(result.comparison["rejected_candidates_unreachable"])
        self.assertTrue(result.comparison["accepted_output_unreachable"])

    def test_form_events_do_not_add_trial_evaluations(self) -> None:
        result = execute_callback_order_case(ROOT, "L2-CO-01", "TEST-EVAL-COUNT")
        self.assertEqual(result.direct.trial_evaluation_count, 1)
        self.assertEqual(result.extra.trial_evaluation_count, 3)
        self.assertEqual(
            sum(row["event"] == "TrialEvaluate" for row in result.direct.event_log),
            1,
        )
        self.assertEqual(
            sum(row["event"] == "TrialEvaluate" for row in result.extra.event_log),
            3,
        )

    def test_co02_declared_context_equal_but_finite_drift_detected(self) -> None:
        result = execute_callback_order_case(ROOT, "L2-CO-02", "TEST-CO02")
        comparison = result.comparison
        self.assertTrue(result.pass_flag)
        self.assertEqual(
            result.observed_classification,
            "DETECT_CALLBACK_HISTORY_DRIFT",
        )
        self.assertTrue(comparison["declared_replay_context_equal"])
        self.assertFalse(comparison["observed_replay_fingerprint_equal"])
        self.assertTrue(comparison["all_values_finite"])
        self.assertGreaterEqual(abs(comparison["delta_residual"]), 1e-8)
        self.assertLess(max(abs(comparison["delta_residual"]), abs(comparison["delta_tangent"])), 1e100)

    def test_co02_runtime_drift_matches_fraction_oracle(self) -> None:
        result = execute_callback_order_case(ROOT, "L2-CO-02", "TEST-CO02-ORACLE")
        oracle = derive_callback_order_oracle()["unsafe_trial_cache"]
        self.assertAlmostEqual(
            result.comparison["delta_residual"],
            float(oracle["delta_residual"]),
            delta=1e-12,
        )
        self.assertAlmostEqual(
            result.comparison["delta_tangent"],
            float(oracle["delta_tangent"]),
            delta=1e-12,
        )

    def test_unauthorized_case_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            execute_callback_order_case(ROOT, "L2-CO-99", "TEST-DENY")

    def test_import_has_no_filesystem_or_execution_side_effect(self) -> None:
        code = (
            "import json, pathlib; "
            "before=sorted(str(p.relative_to(pathlib.Path.cwd())) for p in pathlib.Path.cwd().rglob('*')); "
            "import src.l2_d2_callback_order; "
            "after=sorted(str(p.relative_to(pathlib.Path.cwd())) for p in pathlib.Path.cwd().rglob('*')); "
            "print(json.dumps({'same': before == after}))"
        )
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        completed = subprocess.run(
            [sys.executable, "-c", code],
            cwd=ROOT,
            env=environment,
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertEqual(json.loads(completed.stdout), {"same": True})
        self.assertEqual(completed.stderr, "")


if __name__ == "__main__":
    unittest.main()
