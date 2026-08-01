from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest

import numpy as np

from benchmarks.PERF_cost_overhead.src.perf_postprocess import (
    METRIC_FIELDS,
    bootstrap_median_ci,
    distribution_stats,
    quantile_linear,
)


ROOT = Path(__file__).resolve().parents[1]


class PerfPostprocessTests(unittest.TestCase):
    def test_linear_quantiles(self) -> None:
        values = list(range(1, 11))
        self.assertEqual(quantile_linear(values, 0.25), 3.25)
        self.assertEqual(quantile_linear(values, 0.5), 5.5)
        self.assertEqual(quantile_linear(values, 0.75), 7.75)

    def test_bootstrap_is_deterministic(self) -> None:
        first = bootstrap_median_ci(range(1, 11), np.random.default_rng(20260722))
        second = bootstrap_median_ci(range(1, 11), np.random.default_rng(20260722))
        self.assertEqual(first, second)
        self.assertLessEqual(first[0], 5.5)
        self.assertGreaterEqual(first[1], 5.5)

    def test_distribution_contract(self) -> None:
        stats = distribution_stats(range(1, 11), np.random.default_rng(20260722))
        self.assertEqual(stats["median"], 5.5)
        self.assertEqual(stats["iqr"], 4.5)
        self.assertEqual(set(stats), {
            "median", "q1", "q3", "iqr", "median_ci95_low", "median_ci95_high"
        })

    def test_metric_order_is_unique_and_frozen(self) -> None:
        self.assertEqual(len(METRIC_FIELDS), 19)
        self.assertEqual(len(set(METRIC_FIELDS)), 19)
        self.assertEqual(METRIC_FIELDS[0], "wall_time_ns")
        self.assertEqual(METRIC_FIELDS[-1], "hashing_time_ns")

    def test_postprocessor_refuses_missing_dual_authorization(self) -> None:
        final_root = ROOT / "results" / "PERF_D1_cost_overhead" / "final"
        self.assertFalse(final_root.exists())
        completed = subprocess.run(
            [sys.executable, str(ROOT / "run_perf_postprocess.py")],
            cwd=str(ROOT), capture_output=True, text=True, check=False,
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertFalse(final_root.exists())

    def test_preflight_is_pass_and_formal_not_started(self) -> None:
        preflight = json.loads((
            ROOT / "preflight" / "PERF_D1_all_cells" / "preflight_summary.json"
        ).read_text(encoding="utf-8"))
        self.assertEqual(preflight["cell_count"], 45)
        self.assertTrue(preflight["all_output_equivalence_gates_passed"])
        self.assertFalse((ROOT / "results" / "PERF_D1_cost_overhead").exists())


if __name__ == "__main__":
    unittest.main()
