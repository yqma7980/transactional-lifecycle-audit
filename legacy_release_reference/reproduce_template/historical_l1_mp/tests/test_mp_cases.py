from __future__ import annotations

import csv
from pathlib import Path
import unittest

from src.l1_cases import MPBenchmark


ROOT = Path(__file__).resolve().parents[1]


class MPCaseMatrixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.benchmark = MPBenchmark(ROOT, "a" * 64)
        cls.results, cls.ledger, cls.checkpoints = cls.benchmark.run()

    def test_all_25_outcomes_pass(self) -> None:
        self.assertEqual(len(self.results), 25)
        failed = [row for row in self.results if row["passed"] != "true"]
        self.assertEqual(failed, [])

    def test_all_12_case_ids_are_present(self) -> None:
        self.assertEqual(len({row["case_id"] for row in self.results}), 12)

    def test_primary_seed_matches_fraction_oracle(self) -> None:
        row = next(
            row
            for row in self.results
            if row["case_id"] == "MP-LC-01" and row["variant"] == "unsafe_trial_cache"
        )
        self.assertAlmostEqual(float(row["delta_stress"]), -205.0 / 121.0, delta=1.0e-12)
        self.assertEqual(row["declared_packet_equal"], "true")

    def test_safe_lifecycle_replays_are_exact_zero(self) -> None:
        lifecycle_ids = {"MP-LC-01", "MP-LC-02", "MP-LC-03", "MP-LC-05", "MP-LC-06", "MP-LC-07"}
        rows = [
            row
            for row in self.results
            if row["case_id"] in lifecycle_ids
            and row["variant"] in {"safe_local", "safe_transactional"}
            and row["delta_stress"] != "NA"
        ]
        self.assertTrue(rows)
        self.assertTrue(all(float(row["delta_stress"]) == 0.0 for row in rows))

    def test_ledger_has_frozen_40_columns(self) -> None:
        with (ROOT / "schemas" / "l1_call_ledger_columns.csv").open(
            "r", encoding="utf-8", newline=""
        ) as handle:
            expected = [row["name"] for row in csv.DictReader(handle)]
        self.assertTrue(self.ledger)
        self.assertEqual(list(self.ledger[0]), expected)
        self.assertTrue(all(list(row) == expected for row in self.ledger))

    def test_accepted_checkpoints_have_only_accept_events(self) -> None:
        self.assertTrue(self.checkpoints)
        self.assertTrue(all(int(row["accepted_version"]) >= 1 for row in self.checkpoints))
        self.assertTrue(all(row["candidate_id"] != "NA" for row in self.checkpoints))

    def test_e1_cases_were_not_executed(self) -> None:
        self.assertTrue(all(row["sublevel"] == "L1-MP" for row in self.results))
        self.assertTrue(all(row["sublevel"] == "L1-MP" for row in self.ledger))


if __name__ == "__main__":
    unittest.main()

