from __future__ import annotations

from pathlib import Path
import sys
import unittest

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from p5_quadrature_backend_erratum import reduce_cell_quadrature


class P5QuadratureBackendErratumTests(unittest.TestCase):
    def test_uniform_packets_preserve_the_first_point_exactly(self):
        first = np.array([[1.25, -2.5], [3.5, 4.75]], dtype=np.float64)
        values = np.repeat(first[:, None, :], 3, axis=1)
        reduced, mode = reduce_cell_quadrature(
            values,
            np.array([1.0 / 6.0] * 3),
        )
        np.testing.assert_array_equal(reduced, first)
        self.assertEqual(mode, "IDENTICAL_GP_FAST_PATH")

    def test_nonuniform_packets_use_the_frozen_equal_weight_rule(self):
        values = np.array(
            [
                [[1.0, 3.0], [4.0, 6.0], [7.0, 9.0]],
                [[-2.0, 2.0], [1.0, 5.0], [4.0, 8.0]],
            ],
            dtype=np.float64,
        )
        reduced, mode = reduce_cell_quadrature(
            values,
            np.array([1.0 / 6.0] * 3),
        )
        np.testing.assert_allclose(
            reduced,
            np.array([[4.0, 6.0], [1.0, 5.0]]),
            rtol=0.0,
            atol=0.0,
        )
        self.assertEqual(mode, "WEIGHTED_GP_REDUCTION")

    def test_invalid_weight_contract_is_rejected(self):
        values = np.zeros((2, 3, 2), dtype=np.float64)
        with self.assertRaises(ValueError):
            reduce_cell_quadrature(values, np.array([0.5, 0.5]))
        with self.assertRaises(ValueError):
            reduce_cell_quadrature(values, np.zeros(3))


if __name__ == "__main__":
    unittest.main()
