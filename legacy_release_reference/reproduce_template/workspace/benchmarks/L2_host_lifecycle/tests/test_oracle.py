from __future__ import annotations

from fractions import Fraction
import unittest

from oracle.l2_fraction_oracle import equilibrium


class FractionOracleTests(unittest.TestCase):
    def test_elastic_reference(self) -> None:
        result = equilibrium(Fraction(1, 2))
        self.assertEqual(result.displacement, Fraction(1, 200))
        self.assertEqual(result.stress, Fraction(1, 2))
        self.assertEqual(result.epsilon_p, 0)
        self.assertEqual(result.kappa, 0)

    def test_plastic_reference(self) -> None:
        result = equilibrium(Fraction(11, 10))
        self.assertEqual(result.displacement, Fraction(21, 1000))
        self.assertEqual(result.stress, Fraction(11, 10))
        self.assertEqual(result.epsilon_p, Fraction(1, 100))
        self.assertEqual(result.kappa, Fraction(1, 100))


if __name__ == "__main__":
    unittest.main()
