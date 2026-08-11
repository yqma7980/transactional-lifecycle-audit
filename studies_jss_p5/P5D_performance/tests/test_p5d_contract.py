from __future__ import annotations

import ast
import csv
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from p5d_common import canonical_hash


class FrozenMatrixTests(unittest.TestCase):
    def setUp(self) -> None:
        with (ROOT / "frozen_inputs" / "P5D_performance_matrix.csv").open(
            "r", encoding="utf-8", newline=""
        ) as stream:
            self.rows = list(csv.DictReader(stream))

    def test_matrix_is_18_unique_cells(self) -> None:
        self.assertEqual(len(self.rows), 18)
        self.assertEqual(len({row["cell_id"] for row in self.rows}), 18)

    def test_every_workload_has_three_modes(self) -> None:
        workloads = {}
        for row in self.rows:
            workloads.setdefault(row["workload_id"], set()).add(row["instrumentation_mode"])
        self.assertEqual(len(workloads), 6)
        for modes in workloads.values():
            self.assertEqual(modes, {"M0_AUDIT_OFF", "M3_GENERIC_REPLAY", "M6_FULL_TLA"})

    def test_repetition_and_thread_contract(self) -> None:
        for row in self.rows:
            self.assertEqual(row["warmup_processes"], "2")
            self.assertEqual(row["timed_fresh_processes"], "10")
            self.assertEqual(row["processes_per_run"], "1")
            self.assertEqual(row["threads_per_process"], "1")


class ImplementationContractTests(unittest.TestCase):
    def test_canonical_hash_distinguishes_float_bits(self) -> None:
        self.assertNotEqual(canonical_hash({"x": 0.0}), canonical_hash({"x": -0.0}))

    def test_python_sources_parse(self) -> None:
        paths = [
            ROOT / "run_p5d.py",
            ROOT / "orchestrate_p5d.py",
            ROOT / "analyze_p5d.py",
            *(ROOT / "src").glob("*.py"),
        ]
        for path in paths:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    def test_runner_has_dual_authorization_before_output(self) -> None:
        source = (ROOT / "run_p5d.py").read_text(encoding="utf-8")
        lock = source.index("P5D_EXECUTION_AUTHORIZED")
        writer = source.index("write_json_new(args.output")
        self.assertLess(lock, writer)
        self.assertIn("--execute-authorized", source)

    def test_matrix_runner_has_second_dual_lock(self) -> None:
        source = (ROOT / "orchestrate_p5d.py").read_text(encoding="utf-8")
        self.assertIn("P5D_MATRIX_EXECUTION_AUTHORIZED", source)
        self.assertIn("--execute-authorized", source)
        self.assertIn("--cpuset-cpus", source)
        self.assertIn('"0"', source)

    def test_subject_specific_environment_binding_is_explicit(self) -> None:
        source = (ROOT / "orchestrate_p5d.py").read_text(encoding="utf-8")
        self.assertIn("HOST_PYTHON_SCIPY_1_17_1", source)
        self.assertIn("qualification_v3", source)

    def test_audit_modes_execute_after_production(self) -> None:
        source = (ROOT / "src" / "p5d_subjects.py").read_text(encoding="utf-8")
        self.assertIn("production_seconds", source)
        self.assertIn("audit_seconds", source)
        self.assertIn("M0_AUDIT_OFF", source)
        self.assertIn("M3_GENERIC_REPLAY", source)
        self.assertIn("M6_FULL_TLA", source)


if __name__ == "__main__":
    unittest.main()
