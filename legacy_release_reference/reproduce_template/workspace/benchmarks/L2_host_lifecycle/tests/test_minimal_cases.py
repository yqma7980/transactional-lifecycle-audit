from __future__ import annotations

from pathlib import Path
import unittest

from src.l2_cases import authorized_case_ids, execute_case


ROOT = Path(__file__).resolve().parents[1]


class MinimalCaseTests(unittest.TestCase):
    def test_only_frozen_cases_are_exposed(self) -> None:
        self.assertEqual(
            authorized_case_ids(),
            (
                "L2-REF-01",
                "L2-REF-02",
                "L2-RT-01",
                "L2-RT-02",
                "L2-RT-03",
            ),
        )

    def test_minimal_cases_meet_frozen_expectations(self) -> None:
        for case_id in authorized_case_ids():
            with self.subTest(case_id=case_id):
                execution = execute_case(ROOT, case_id, "L2-D1-TEST")
                self.assertTrue(execution.result["passed"])
                self.assertEqual(
                    execution.result["observed_classification"],
                    execution.result["expected_classification"],
                )


if __name__ == "__main__":
    unittest.main()
