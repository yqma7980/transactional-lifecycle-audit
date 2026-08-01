from __future__ import annotations

from fractions import Fraction
from pathlib import Path
import unittest

from src.l1_e1_cases import E1Benchmark


ROOT = Path(__file__).resolve().parents[1]


class E1CaseMatrixTests(unittest.TestCase):
    def setUp(self) -> None:
        self.benchmark = E1Benchmark(ROOT, "1" * 64)
        self.rows, self.ledger, self.checkpoints = self.benchmark.run()

    def test_all_twenty_outcomes_pass(self) -> None:
        self.assertEqual(len(self.rows), 20)
        self.assertTrue(all(row["passed"] == "true" for row in self.rows))
        self.assertTrue(all(row["finite"] == "true" for row in self.rows))

    def test_primary_seed_matches_exact_element_residual_drift(self) -> None:
        row = next(
            row for row in self.rows
            if row["case_id"] == "E1-LC-01" and row["variant"] == "unsafe_trial_cache"
        )
        self.assertAlmostEqual(
            float(row["delta_residual"]), float(Fraction(-205, 121)), places=12
        )

    def test_call_order_seed_and_version_seed_are_detected(self) -> None:
        order = next(
            row for row in self.rows
            if row["case_id"] == "E1-LC-02" and row["variant"] == "unsafe_trial_cache"
        )
        mismatch = next(
            row for row in self.rows
            if row["case_id"] == "E1-OP-01"
            and row["variant"] == "seeded_version_mismatch"
        )
        self.assertGreater(abs(float(order["delta_residual"])), 1.0e-8)
        self.assertEqual(
            mismatch["observed_classification"],
            "REJECTED_SEEDED_VERSION_MISMATCH_BEFORE_LIFECYCLE_VERDICT",
        )

    def test_safe_replays_are_exact_and_outputs_are_accepted_only(self) -> None:
        safe = [
            row for row in self.rows
            if row["variant"] in {"safe_local", "safe_transactional"}
            and row["case_id"] in {"E1-LC-01", "E1-LC-02", "E1-LC-03"}
        ]
        self.assertTrue(all(float(row["delta_residual"]) == 0.0 for row in safe))
        provenance = [
            row for row in self.rows if row["case_id"] == "E1-LC-04"
        ]
        self.assertTrue(all(row["accepted_source_valid"] == "true" for row in provenance))

    def test_ledger_and_checkpoint_contract(self) -> None:
        self.assertGreater(len(self.ledger), 0)
        self.assertEqual({len(row) for row in self.ledger}, {40})
        self.assertEqual(len(self.checkpoints), 2)
        self.assertTrue(all(row["case_id"] == "E1-LC-05" for row in self.checkpoints))


if __name__ == "__main__":
    unittest.main()

