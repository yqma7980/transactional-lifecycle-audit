from __future__ import annotations

import json
import math
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from l0_model import SafeTransactionalEvaluator  # noqa: E402
from run_benchmark import execute_benchmark, write_outputs  # noqa: E402


class L0ReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.summary, cls.ledger = execute_benchmark(ROOT / "expected_results.json")
        cls.by_key = {
            (item["scenario"], item["variant"]): item for item in cls.summary["outcomes"]
        }

    def test_predeclared_matrix_passes(self) -> None:
        self.assertTrue(self.summary["overall_pass"])
        self.assertEqual(len(self.summary["outcomes"]), 9)

    def test_discarded_trial_exact_counterexample(self) -> None:
        item = self.by_key[("discarded_trial_replay", "unsafe_persistent")]
        self.assertEqual(item["delta_residual"], 1.0)
        self.assertEqual(item["delta_residual"], 2.0 * self.summary["parameters"]["alpha"])

    def test_unsafe_variants_are_finite_and_detected(self) -> None:
        unsafe = [item for item in self.summary["outcomes"] if item["variant"] == "unsafe_persistent"]
        self.assertEqual(len(unsafe), 3)
        self.assertTrue(all(math.isfinite(item["delta_residual"]) for item in unsafe))
        self.assertTrue(all(item["delta_residual"] != 0.0 for item in unsafe))

    def test_safe_local_is_replay_invariant(self) -> None:
        safe = [item for item in self.summary["outcomes"] if item["variant"] == "safe_local"]
        self.assertTrue(all(item["delta_residual"] == 0.0 for item in safe))

    def test_safe_transactional_is_replay_invariant(self) -> None:
        safe = [item for item in self.summary["outcomes"] if item["variant"] == "safe_transactional"]
        self.assertTrue(all(item["delta_residual"] == 0.0 for item in safe))

    def test_compared_replay_state_is_equal(self) -> None:
        self.assertTrue(all(item["declared_state_equal"] for item in self.summary["outcomes"]))

    def test_rejected_candidate_does_not_change_committed_state(self) -> None:
        evaluator = SafeTransactionalEvaluator(committed_c=1.0, alpha=0.5)
        before = evaluator.committed_state().copy()
        evaluator.evaluate(2.0, event="trial", candidate_id="a1")
        evaluator.reject("a1")
        self.assertEqual(evaluator.committed_state(), before)

    def test_accept_promotes_exactly_one_candidate(self) -> None:
        evaluator = SafeTransactionalEvaluator(committed_c=1.0, alpha=0.5)
        evaluator.evaluate(2.0, event="trial", candidate_id="a1")
        evaluator.accept("a1")
        self.assertEqual(evaluator.committed_p, 2.0)
        self.assertNotIn("a1", evaluator.candidates)

    def test_duplicate_execution_is_deterministic(self) -> None:
        second_summary, second_ledger = execute_benchmark(ROOT / "expected_results.json")
        self.assertEqual(self.summary, second_summary)
        self.assertEqual(self.ledger, second_ledger)

    def test_outputs_are_machine_readable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            write_outputs(output_dir, self.summary, self.ledger)
            loaded = json.loads((output_dir / "l0_summary.json").read_text(encoding="utf-8"))
            self.assertTrue(loaded["overall_pass"])
            self.assertTrue((output_dir / "l0_call_ledger.csv").stat().st_size > 0)
            self.assertTrue((output_dir / "l0_manifest.json").stat().st_size > 0)


if __name__ == "__main__":
    unittest.main()
