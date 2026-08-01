from __future__ import annotations

import csv
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
EXPECTED = (
    "L2-REF-01",
    "L2-REF-02",
    "L2-RT-01",
    "L2-RT-02",
    "L2-RT-03",
)


class StaticContractTests(unittest.TestCase):
    def test_freeze_authorizes_only_minimal_subset(self) -> None:
        freeze = json.loads(
            (ROOT / "L2_D1_execution_freeze.json").read_text(encoding="utf-8")
        )
        self.assertEqual(tuple(freeze["authorized_case_subset"]), EXPECTED)
        self.assertFalse(freeze["execution_authorized"])
        self.assertEqual(freeze["threading"]["thread_count"], 1)
        self.assertEqual(
            freeze["reproducibility"]["formal_repetition_count"],
            2,
        )

    def test_case_matrix_is_frozen_not_executed(self) -> None:
        with (ROOT / "L2_D1_minimal_case_matrix.csv").open(
            "r", encoding="utf-8", newline=""
        ) as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(tuple(row["case_id"] for row in rows), EXPECTED)
        self.assertTrue(all(row["status"] == "FROZEN_NOT_EXECUTED" for row in rows))
        self.assertTrue(all(row["repeat_count"] == "2" for row in rows))
        self.assertTrue(all(row["thread_count"] == "1" for row in rows))


if __name__ == "__main__":
    unittest.main()
