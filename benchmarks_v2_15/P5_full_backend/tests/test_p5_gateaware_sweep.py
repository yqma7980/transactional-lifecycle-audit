from __future__ import annotations

from pathlib import Path
import sys
import unittest

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import p5_fe_history
from p5_quadrature_backend_erratum_v2 import P5QuadratureAwareFEHost


p5_fe_history.P5TransactionalFEHost = P5QuadratureAwareFEHost

from p5_case_executor_gatefix import metric_distances_with_availability
from p5_fe_history_gatefix import run_p5_history_gateaware


class P5GateAwareSweepTests(unittest.TestCase):
    def test_shape_mismatch_is_explicit_not_padded(self):
        metrics = {
            "M_R": np.array([1.0]),
            "M_J": np.array([[2.0]]),
            "M_X": np.array([3.0]),
            "M_GP": np.array([4.0]),
            "M_ALPHA": np.array([5.0]),
            "M_REACTION": np.array([6.0, -6.0]),
            "M_OUTPUT_W": np.array([7.0, 8.0]),
            "M_OUTPUT_R": np.array([[9.0, -9.0]]),
        }
        other = {key: value.copy() for key, value in metrics.items()}
        other["M_OUTPUT_W"] = np.array([7.0])
        distances, available = metric_distances_with_availability(
            metrics,
            other,
        )
        self.assertFalse(available["M_OUTPUT_W"])
        self.assertIsNone(distances["M_OUTPUT_W"])
        self.assertTrue(available["M_R"])
        self.assertEqual(distances["M_R"], 0.0)

    def test_high_f05_mechanics_gate_is_structured_without_commit(self):
        history = run_p5_history_gateaware(
            "F05",
            True,
            0.000244140625,
            "P5-GATE-TEST",
        )
        self.assertEqual(
            history.prerequisite_status,
            "FAILED_NORMAL_MECHANICS_GATE",
        )
        self.assertTrue(history.lifecycle_violation_present)
        self.assertFalse(history.conventional_quiet)
        self.assertIsNotNone(history.replay_packet)
        self.assertLess(len(history.output_rows), 10)
        self.assertNotIn(
            history.attempts[-1]["selected_candidate_id"],
            [row["candidate_id"] for row in history.output_rows],
        )


if __name__ == "__main__":
    unittest.main()
