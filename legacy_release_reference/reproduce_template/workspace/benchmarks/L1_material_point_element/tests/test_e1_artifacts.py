from __future__ import annotations

import csv
import json
from pathlib import Path
import shutil
import unittest

from run_l1_e1 import run
from src.l1_design_validation import validate_summary_document


ROOT = Path(__file__).resolve().parents[1]


class E1ArtifactTests(unittest.TestCase):
    def test_runner_writes_valid_candidate_artifacts(self) -> None:
        output = ROOT / "_artifact_test_e1_candidate"
        self.assertFalse(output.exists(), f"stale test output: {output}")
        try:
            self.assertEqual(run(output), 0)
            required = {
                "l1_e1_run_summary.json",
                "l1_e1_call_ledger.csv",
                "l1_e1_case_results.csv",
                "l1_e1_accepted_checkpoints.csv",
                "l1_e1_manifest.json",
                "l1_e1_result_report.md",
            }
            self.assertTrue(required.issubset({path.name for path in output.iterdir()}))
            summary = json.loads(
                (output / "l1_e1_run_summary.json").read_text(encoding="utf-8")
            )
            self.assertEqual(validate_summary_document(summary), [])
            self.assertEqual(summary["sublevels"]["L1-MP"]["status"], "PASS")
            self.assertEqual(summary["sublevels"]["L1-E1"]["status"], "PASS")
            self.assertFalse(summary["overall_pass"])
            with (output / "l1_e1_case_results.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 20)
            self.assertTrue(all(row["passed"] == "true" for row in rows))
        finally:
            shutil.rmtree(output, ignore_errors=True)

    def test_final_results_record_full_l1_only(self) -> None:
        result_dir = ROOT / "results"
        summary = json.loads(
            (result_dir / "l1_run_summary.json").read_text(encoding="utf-8")
        )
        self.assertEqual(validate_summary_document(summary), [])
        self.assertEqual(summary["execution_status"], "COMPLETE")
        self.assertTrue(summary["overall_pass"])
        self.assertEqual(summary["sublevels"]["L1-MP"]["passed_cases"], 12)
        self.assertEqual(summary["sublevels"]["L1-E1"]["passed_cases"], 8)
        with (result_dir / "l1_case_results.csv").open(
            "r", encoding="utf-8", newline=""
        ) as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 45)
        self.assertTrue(all(row["passed"] == "true" for row in rows))
        comparison = json.loads(
            (result_dir / "l1_duplicate_run_comparison.json").read_text(encoding="utf-8")
        )
        self.assertTrue(comparison["all_match"])
        manifest = json.loads(
            (result_dir / "l1_manifest.json").read_text(encoding="utf-8")
        )

if __name__ == "__main__":
    unittest.main()

