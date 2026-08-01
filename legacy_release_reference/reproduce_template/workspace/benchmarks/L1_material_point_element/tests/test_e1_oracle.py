from __future__ import annotations

from fractions import Fraction
import unittest

from src.l1_element import ElementData, evaluate_element
from src.l1_state import MaterialData
from src.l1_variants import SafeLocal


def exact_bar_operator(u: Fraction, force: Fraction) -> tuple[Fraction, Fraction]:
    E, H, sigma_y = Fraction(100), Fraction(10), Fraction(1)
    sigma_trial = E * u
    if abs(sigma_trial) <= sigma_y:
        sigma, tangent = sigma_trial, E
    else:
        direction = Fraction(1) if sigma_trial >= 0 else Fraction(-1)
        gamma = (abs(sigma_trial) - sigma_y) / (E + H)
        sigma = sigma_trial - E * gamma * direction
        tangent = E * H / (E + H)
    return sigma - force, tangent


class E1IndependentOracleTests(unittest.TestCase):
    def test_fraction_reference_packets(self) -> None:
        self.assertEqual(exact_bar_operator(Fraction(1, 200), Fraction(1, 2)), (0, 100))
        self.assertEqual(
            exact_bar_operator(Fraction(21, 1000), Fraction(11, 10)),
            (0, Fraction(100, 11)),
        )
        self.assertEqual(
            exact_bar_operator(Fraction(3, 100), Fraction(13, 11)),
            (0, Fraction(100, 11)),
        )

    def test_runtime_operator_does_not_mutate_committed_state(self) -> None:
        variant = SafeLocal(MaterialData())
        before = variant.committed
        result = evaluate_element(
            variant,
            ElementData(),
            case_id="ORACLE",
            configuration_hash="0" * 64,
            u=0.021,
            force=1.1,
            candidate_id="candidate",
            attempt_id="attempt",
            source_call_index=0,
        )
        self.assertAlmostEqual(result.residual, 0.0, places=12)
        self.assertAlmostEqual(result.tangent, 100.0 / 11.0, places=12)
        self.assertEqual(variant.committed, before)
        self.assertTrue(result.version_compatible)


if __name__ == "__main__":
    unittest.main()

