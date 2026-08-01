from __future__ import annotations

from fractions import Fraction
from pathlib import Path
import unittest

from tests.independent_oracle import OracleState, accepted_path, update


ROOT = Path(__file__).resolve().parents[1]


class FractionOracleTests(unittest.TestCase):
    def test_virgin_elastic(self) -> None:
        result = update(Fraction(1, 200), OracleState())
        self.assertEqual(result.sigma, Fraction(1, 2))
        self.assertEqual(result.E_alg, Fraction(100))
        self.assertEqual(result.state, OracleState())

    def test_virgin_plastic(self) -> None:
        result = update(Fraction(3, 100), OracleState())
        self.assertEqual(result.delta_gamma, Fraction(1, 55))
        self.assertEqual(result.sigma, Fraction(13, 11))
        self.assertEqual(result.E_alg, Fraction(100, 11))
        self.assertEqual(result.state.epsilon_p, Fraction(1, 55))
        self.assertEqual(result.state.kappa, Fraction(1, 55))

    def test_seeded_unsafe_replay(self) -> None:
        disposable = update(Fraction(3, 100), OracleState())
        replay = update(Fraction(1, 200), disposable.state)
        self.assertEqual(replay.sigma, Fraction(-289, 242))
        self.assertEqual(replay.sigma - Fraction(1, 2), Fraction(-205, 121))

    def test_load_unload_reload_path(self) -> None:
        results = accepted_path([Fraction(3, 100), Fraction(0), Fraction(3, 100)])
        expected = [
            (Fraction(13, 11), Fraction(1, 55), Fraction(1, 55), Fraction(12, 605)),
            (Fraction(-150, 121), Fraction(3, 242), Fraction(29, 1210), Fraction(2051, 292820)),
            (Fraction(1713, 1331), Fraction(114, 6655), Fraction(191, 6655), Fraction(211869, 35431220)),
        ]
        for result, values in zip(results, expected, strict=True):
            sigma, epsilon_p, kappa, dissipation = values
            self.assertEqual(result.sigma, sigma)
            self.assertEqual(result.state.epsilon_p, epsilon_p)
            self.assertEqual(result.state.kappa, kappa)
            self.assertEqual(result.plastic_dissipation, dissipation)

    def test_runtime_does_not_import_fraction_or_test_oracle(self) -> None:
        runtime = (ROOT / "src" / "l1_material.py").read_text(encoding="utf-8")
        self.assertNotIn("fractions", runtime)
        self.assertNotIn("independent_oracle", runtime)


if __name__ == "__main__":
    unittest.main()

