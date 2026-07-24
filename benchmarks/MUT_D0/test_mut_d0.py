from __future__ import annotations

import unittest

from run_mut_d0 import STRENGTHS, classify, execute_development


class MUTD0Tests(unittest.TestCase):
    def test_strengths_are_frozen_and_monotone(self):
        self.assertEqual(STRENGTHS[0], 0.0)
        self.assertEqual(len(STRENGTHS), 22)
        self.assertEqual(tuple(sorted(STRENGTHS)), STRENGTHS)

    def test_zero_control_is_below_operator_drift_threshold(self):
        payload, _ = execute_development(0.0)
        self.assertEqual(
            payload["classification"],
            "BELOW_OPERATOR_REPLAY_DRIFT_THRESHOLD",
        )
        self.assertFalse(payload["operator_replay_drift_detected"])
        self.assertFalse(payload["a4_persistent_compatibility_satisfied"])

    def test_preflight_weak_mutation_crosses_operator_drift_threshold(self):
        payload, _ = execute_development(1e-8)
        self.assertEqual(
            payload["classification"],
            "OPERATOR_REPLAY_DRIFT_DETECTED_WITH_CONVENTIONAL_GATES_PASS",
        )
        self.assertTrue(payload["operator_replay_drift_detected"])
        self.assertEqual(
            payload["full_tla_replay_verdict"],
            "INVALID_A4_PERSISTENT_STATE_INCOMPATIBLE",
        )


if __name__ == "__main__":
    unittest.main()
