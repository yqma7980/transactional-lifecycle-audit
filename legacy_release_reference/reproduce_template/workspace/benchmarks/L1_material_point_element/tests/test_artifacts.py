from __future__ import annotations

import csv
import json
from pathlib import Path
import shutil
import unittest

from src.l1_design_validation import validate_summary_document
from run_l1_mp import run


ROOT = Path(__file__).resolve().parents[1]


class ArtifactTests(unittest.TestCase):
    def test_runner_writes_valid_candidate_artifacts(self) -> None:
        output = ROOT / "_artifact_test_candidate"
        self.assertFalse(output.exists(), f"stale test output: {output}")
        try:
            self.assertEqual(run(output), 0)
            required = {
                "l1_run_summary.json",
                "l1_call_ledger.csv",
                "l1_case_results.csv",
                "l1_accepted_checkpoints.csv",
                "l1_manifest.json",
                "l1_result_report.md",
            }
            self.assertTrue(required.issubset({path.name for path in output.iterdir()}))
            summary = json.loads((output / "l1_run_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(validate_summary_document(summary), [])
            self.assertEqual(summary["sublevels"]["L1-MP"]["status"], "PASS")
            self.assertEqual(summary["sublevels"]["L1-E1"]["status"], "BLOCKED")
            with (output / "l1_case_results.csv").open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 25)
            self.assertTrue(all(row["passed"] == "true" for row in rows))
        finally:
            shutil.rmtree(output, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
