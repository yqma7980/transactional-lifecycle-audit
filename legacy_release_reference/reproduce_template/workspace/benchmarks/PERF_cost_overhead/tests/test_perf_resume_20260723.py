from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import unittest

from benchmarks.PERF_cost_overhead.run_perf_resume_20260723 import validate_partial


ROOT = Path(__file__).resolve().parents[1]


class PerfResumeTests(unittest.TestCase):
    def test_frozen_partial_inventory(self) -> None:
        rows, result_root = validate_partial(ROOT)
        self.assertEqual(len(rows), 45)
        self.assertFalse((result_root / "formal_execution_receipts.json").exists())
        self.assertFalse(any((result_root / row["case_id"] / "run_10").exists() for row in rows))

    def test_resume_refuses_missing_dual_authorization(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "run_perf_resume_20260723.py")],
            cwd=str(ROOT), capture_output=True, text=True, check=False,
        )
        self.assertNotEqual(completed.returncode, 0)
        rows, result_root = validate_partial(ROOT)
        self.assertFalse(any((result_root / row["case_id"] / "run_10").exists() for row in rows))


if __name__ == "__main__":
    unittest.main()
