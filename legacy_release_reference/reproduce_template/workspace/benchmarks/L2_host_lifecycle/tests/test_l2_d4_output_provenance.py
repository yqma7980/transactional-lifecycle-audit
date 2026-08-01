"""Test definitions for L2-D4.0.

These tests are intentionally defined but were not executed during the
IMPLEMENTED_NOT_EXECUTED stage.
"""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path
import json
import math
import unittest

from oracle.l2_d4_fraction_oracle import derive_output_provenance_oracle
from src.l2_d4_output_provenance import (
    AUTHORITATIVE_ACCEPTED_OUTPUT_HASH,
    AUTHORITATIVE_COMMITTED_HASH,
    AUTHORIZED_CASES,
    EXPECTED_CLASSIFICATIONS,
    OutputSnapshot,
    execute_output_provenance_case,
    load_frozen_design,
)


BENCHMARK_ROOT = Path(__file__).resolve().parents[1]


class L2D4OutputProvenanceTests(unittest.TestCase):
    def test_freeze_and_matrix_identity(self) -> None:
        freeze, matrix = load_frozen_design(BENCHMARK_ROOT)
        self.assertEqual(freeze["design_version"], "L2-D4.0")
        self.assertEqual(tuple(row["case_id"] for row in matrix), AUTHORIZED_CASES)
        self.assertEqual(len(set(row["case_id"] for row in matrix)), 2)

    def test_frozen_callback_schedules(self) -> None:
        freeze, _ = load_frozen_design(BENCHMARK_ROOT)
        histories = freeze["frozen_histories"]
        self.assertEqual(
            tuple(item["event"] for item in histories["L2-OP-01"]["trial_then_output"]),
            (
                "BeginAttempt",
                "TrialEvaluate",
                "FormResidual",
                "FormTangent",
                "OutputRead",
                "RejectAttempt",
            ),
        )
        self.assertEqual(
            tuple(item["event"] for item in histories["L2-OP-02"]["insert_output_read"]),
            (
                "OutputRead",
                "BeginAttempt",
                "TrialEvaluate",
                "FormResidual",
                "FormTangent",
                "RejectAttempt",
            ),
        )

    def test_authoritative_output_fingerprint(self) -> None:
        snapshot = OutputSnapshot(
            accepted_version=0,
            epsilon_p=0.0,
            kappa=0.0,
            source_version="accepted:0",
            source_candidate_id="NA",
            source_committed_state_hash=AUTHORITATIVE_COMMITTED_HASH,
            output_accepted_flag=True,
        )
        self.assertTrue(snapshot.accepted_source_valid)
        self.assertEqual(snapshot.fingerprint, AUTHORITATIVE_ACCEPTED_OUTPUT_HASH)

    def test_op01_safe_exact_output_provenance(self) -> None:
        result = execute_output_provenance_case(
            BENCHMARK_ROOT, "L2-OP-01", "test_run"
        )
        comparison = result.comparison
        self.assertTrue(result.pass_flag)
        self.assertEqual(
            result.observed_classification,
            EXPECTED_CLASSIFICATIONS["L2-OP-01"],
        )
        self.assertTrue(comparison.output_snapshot_exact_equal)
        self.assertTrue(comparison.accepted_output_payload_exact)
        self.assertTrue(comparison.output_sources_valid)
        self.assertTrue(comparison.output_read_no_evaluation)
        self.assertTrue(comparison.live_trial_candidate_during_output)
        self.assertTrue(comparison.output_read_committed_unchanged)
        self.assertTrue(comparison.output_read_persistent_unchanged)
        self.assertTrue(comparison.trial_candidate_unreachable_after_reject)

    def test_op01_form_operators_reuse_one_trial_evaluation(self) -> None:
        result = execute_output_provenance_case(
            BENCHMARK_ROOT, "L2-OP-01", "test_run"
        )
        self.assertEqual(result.left_history.material_evaluation_count, 1)
        self.assertEqual(result.left_history.output_read_material_evaluation_count, 0)
        trial_rows = [
            row
            for row in result.event_log
            if row["history_id"] == "trial_then_output"
            and row["event"] in {"TrialEvaluate", "FormResidual", "FormTangent"}
        ]
        self.assertEqual(len(trial_rows), 3)
        self.assertEqual(len({row["residual"] for row in trial_rows}), 1)
        self.assertEqual(len({row["tangent"] for row in trial_rows}), 1)

    def test_op01_rejected_candidate_is_not_accepted_output(self) -> None:
        result = execute_output_provenance_case(
            BENCHMARK_ROOT, "L2-OP-01", "test_run"
        )
        snapshot = result.left_history.output_snapshot
        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertEqual(snapshot.source_candidate_id, "NA")
        self.assertTrue(snapshot.output_accepted_flag)
        self.assertTrue(result.left_history.candidate_unreachable_after_history)

    def test_op02_declared_equal_observed_different(self) -> None:
        result = execute_output_provenance_case(
            BENCHMARK_ROOT, "L2-OP-02", "test_run"
        )
        comparison = result.comparison
        self.assertTrue(result.pass_flag)
        self.assertTrue(comparison.declared_replay_fingerprint_equal)
        self.assertTrue(comparison.d1_declared_packet_equal)
        self.assertFalse(comparison.observed_replay_fingerprint_equal)
        self.assertTrue(comparison.seed_output_rejected_as_accepted)
        self.assertTrue(comparison.committed_states_unchanged)

    def test_op02_exact_fraction_drift(self) -> None:
        result = execute_output_provenance_case(
            BENCHMARK_ROOT, "L2-OP-02", "test_run"
        )
        comparison = result.comparison
        self.assertTrue(
            math.isclose(
                comparison.delta_sigma or 0.0,
                float(Fraction(-205, 121)),
                abs_tol=1.0e-12,
                rel_tol=1.0e-12,
            )
        )
        self.assertTrue(
            math.isclose(
                comparison.delta_residual or 0.0,
                float(Fraction(-205, 121)),
                abs_tol=1.0e-12,
                rel_tol=1.0e-12,
            )
        )
        self.assertTrue(
            math.isclose(
                comparison.delta_tangent or 0.0,
                float(Fraction(-1000, 11)),
                abs_tol=1.0e-12,
                rel_tol=1.0e-12,
            )
        )

    def test_op02_fraction_oracle_is_independent_and_complete(self) -> None:
        oracle = derive_output_provenance_oracle()
        op02 = oracle["L2-OP-02"]
        self.assertEqual(op02["output_seed"]["candidate_epsilon_p"], "1/55")
        self.assertEqual(op02["feedback_replay"]["sigma"], "-289/242")
        self.assertEqual(op02["feedback_replay"]["residual"], "-205/121")
        self.assertEqual(op02["feedback_replay"]["tangent"], "100/11")
        self.assertEqual(op02["feedback_replay"]["candidate_epsilon_p"], "41/2420")
        self.assertEqual(op02["feedback_replay"]["candidate_kappa"], "47/2420")
        self.assertEqual(op02["delta_residual"], "-205/121")
        self.assertEqual(op02["delta_tangent"], "-1000/11")

    def test_all_formal_values_are_finite_and_bounded(self) -> None:
        for case_id in AUTHORIZED_CASES:
            result = execute_output_provenance_case(
                BENCHMARK_ROOT, case_id, "test_run"
            )
            self.assertTrue(result.comparison.all_values_finite)
            for row in result.event_log:
                self.assertTrue(row["all_values_finite"])

    def test_committed_state_is_unchanged_in_both_cases(self) -> None:
        for case_id in AUTHORIZED_CASES:
            result = execute_output_provenance_case(
                BENCHMARK_ROOT, case_id, "test_run"
            )
            self.assertTrue(result.comparison.committed_states_unchanged)
            self.assertTrue(result.comparison.candidates_unreachable)

    def test_unauthorized_case_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            execute_output_provenance_case(
                BENCHMARK_ROOT, "L2-CP-01", "test_run"
            )

    def test_runner_has_double_authorization_contract(self) -> None:
        source = (BENCHMARK_ROOT / "run_l2_d4.py").read_text(encoding="utf-8")
        self.assertIn("--execute-authorized", source)
        self.assertIn("L2_D4_EXECUTION_AUTHORIZED", source)
        self.assertIn('if __name__ == "__main__"', source)

    def test_import_contract_does_not_create_result_root(self) -> None:
        self.assertFalse(
            (BENCHMARK_ROOT / "results" / "L2_D4_output_provenance").exists()
        )
        manifest = json.loads(
            (BENCHMARK_ROOT / "L2_D4_implementation_manifest.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertTrue(manifest["no_case_execution"])


if __name__ == "__main__":
    unittest.main()
