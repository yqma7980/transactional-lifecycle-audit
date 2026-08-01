"""Directed preflight tests for frozen L6-D1."""

from __future__ import annotations

import math
from pathlib import Path
import unittest

from benchmarks.L6_external_host.oracle.l6_stationary_oracle import (
    derive_stationary_oracle,
)
from benchmarks.L6_external_host.src.l6_cases import (
    EXPECTED_CASES,
    execute_l6_case,
    load_frozen_design,
    validate_frozen_design,
)


ROOT = Path(__file__).resolve().parents[3]
RESULT_ROOT = (
    ROOT
    / "benchmarks"
    / "L6_external_host"
    / "results"
    / "L6_D1_external_host"
)


class L6D1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if RESULT_ROOT.exists():
            raise RuntimeError("Formal L6 result root must not exist in preflight")

    @classmethod
    def tearDownClass(cls) -> None:
        if RESULT_ROOT.exists():
            raise RuntimeError("In-memory tests created a formal result root")

    def test_freeze_and_matrix(self) -> None:
        validate_frozen_design(ROOT)
        freeze, matrix = load_frozen_design(ROOT)
        self.assertEqual(freeze["design_version"], "L6-D1.0")
        self.assertEqual([row["case_id"] for row in matrix], list(EXPECTED_CASES))

    def test_stationary_oracle(self) -> None:
        oracle = derive_stationary_oracle()
        x = float(oracle["x_star"])
        self.assertAlmostEqual(x, math.sqrt(2.0 / 3.0), places=15)
        self.assertAlmostEqual(3.0 * x * x - 2.0, 0.0, places=14)
        self.assertGreater(float(oracle["residual_star"]), 0.0)
        self.assertGreater(float(oracle["cost_star"]), 0.0)

    def test_safe_retry(self) -> None:
        artifacts = execute_l6_case(ROOT, "L6-EH-RT-01", "preflight")
        result = artifacts.case_result
        self.assertTrue(result["pass_flag"])
        self.assertEqual(
            result["observed_classification"],
            "PASS_SAFE_EXTERNAL_HOST_RETRY",
        )
        execution = result["executions"][0]
        self.assertGreaterEqual(execution["nonaccepted_residual_count"], 1)
        self.assertTrue(execution["committed_transition_valid"])
        self.assertTrue(execution["rejected_candidates_unreachable"])

    def test_output_provenance(self) -> None:
        result = execute_l6_case(
            ROOT, "L6-EH-OP-01", "preflight"
        ).case_result
        self.assertTrue(result["pass_flag"])
        self.assertTrue(result["gates"]["output_after_host_return_and_commit"])
        self.assertTrue(result["gates"]["output_source_is_accepted_residual"])

    def test_callback_order(self) -> None:
        result = execute_l6_case(
            ROOT, "L6-EH-CO-01", "preflight"
        ).case_result
        self.assertTrue(result["pass_flag"])
        self.assertEqual(
            result["observed_classification"],
            "PASS_EXTERNAL_HOST_CALLBACK_ORDER_PARITY",
        )
        self.assertGreater(
            result["details"]["finite_difference_residual_event_count"],
            result["details"]["analytic_residual_event_count"],
        )

    def test_unsafe_negative_control(self) -> None:
        result = execute_l6_case(
            ROOT, "L6-EH-RT-02", "preflight"
        ).case_result
        self.assertTrue(result["pass_flag"])
        self.assertEqual(
            result["observed_classification"],
            "DETECT_EXTERNAL_HOST_FINITE_DRIFT",
        )
        self.assertGreaterEqual(
            result["details"]["unsafe_nonaccepted_mutation_count"], 1
        )
        self.assertGreaterEqual(
            result["details"]["accepted_x_absolute_drift"], 1.0e-8
        )

    def test_version_mismatch(self) -> None:
        artifacts = execute_l6_case(
            ROOT, "L6-EH-TV-01", "preflight"
        )
        result = artifacts.case_result
        self.assertTrue(result["pass_flag"])
        self.assertEqual(
            result["observed_classification"],
            "REJECT_VERSION_MISMATCH_BEFORE_HOST_CORRECTION",
        )
        self.assertEqual(len(artifacts.accepted_output_rows), 0)
        self.assertTrue(result["gates"]["no_commit"])
        self.assertTrue(result["gates"]["no_accepted_callback"])

    def test_unauthorized_case(self) -> None:
        with self.assertRaises(ValueError):
            execute_l6_case(ROOT, "L6-NOT-A-CASE", "preflight")


if __name__ == "__main__":
    unittest.main()
