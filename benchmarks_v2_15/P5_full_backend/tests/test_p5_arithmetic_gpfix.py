from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys
import unittest

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from p5_arithmetic_gpfix import packet_cell_coefficients


class P5ArithmeticGPFixTests(unittest.TestCase):
    def test_metric_extraction_uses_the_same_equal_weight_reduction(self):
        tau = np.zeros((32, 3, 2), dtype=np.float64)
        tangent = np.zeros((32, 3, 2, 2), dtype=np.float64)
        tau[0, :, 0] = [1.0, 4.0, 7.0]
        tangent[0, :, 1, 1] = [2.0, 5.0, 8.0]
        packet = SimpleNamespace(tau=tau, tangent=tangent)
        context = SimpleNamespace(
            quadrature_weights=np.array([1.0 / 6.0] * 3),
        )
        cell_tau, cell_tangent = packet_cell_coefficients(context, packet)
        self.assertEqual(cell_tau[0, 0], 4.0)
        self.assertEqual(cell_tangent[0, 1, 1], 5.0)
        self.assertTrue(np.all(cell_tau[1:] == 0.0))
        self.assertTrue(np.all(cell_tangent[1:] == 0.0))


if __name__ == "__main__":
    unittest.main()
