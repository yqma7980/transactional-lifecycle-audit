"""Directed implementation and scientific preflight tests for L5-D2."""

from __future__ import annotations

import ast
import hashlib
import json
import math
from pathlib import Path
import unittest

from benchmarks.L5_independent_validation.src.l5_d2_cases import (
    DESIGN_VERSION,
    HOST_VERSION,
    execute_case,
    load_design,
    regression_diagnostics,
)
from benchmarks.L5_independent_validation.src.l5_oracle import independent_oracle
from benchmarks.L5_independent_validation.src.l5_state import (
    binary_fingerprint,
    initial_committed,
)


ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "benchmarks" / "L5_independent_validation"


class L5D2Tests(unittest.TestCase):
    def test_freeze_matrix_and_protocol(self):
        freeze, matrix = load_design(ROOT)
        self.assertEqual(DESIGN_VERSION, "L5-D2.0")
        self.assertEqual(HOST_VERSION, "L5-HOST-D2.0")
        self.assertEqual(freeze["design_status"], "FROZEN_NOT_IMPLEMENTED")
        self.assertFalse(freeze["execution_authorized"])
        self.assertFalse(freeze["results_exist"])
        self.assertEqual(tuple(freeze["solver"]["convergence_N"]), (80, 160, 320, 640, 1280))
        self.assertEqual(freeze["convergence_estimator"]["minimum_order"], 0.7)
        self.assertTrue(freeze["convergence_estimator"]["errors_must_be_strictly_monotone_decreasing"])
        self.assertFalse(freeze["convergence_estimator"]["adjacent_orders_are_hard_gate"])
        self.assertEqual(len(matrix), 8)
        self.assertEqual(set(matrix), set(freeze["formal_cases"]))

    def test_immutable_dependencies_match_source_manifest(self):
        manifest = json.loads((BASE / "L5_D2_source_manifest.json").read_text(encoding="utf-8"))
        for item in manifest["immutable_l5_dependencies"]:
            path = ROOT / item["path"]
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"])
        failure = BASE / "L5_D1_pre_execution_gate_failure_20260722.json"
        self.assertEqual(
            hashlib.sha256(failure.read_bytes()).hexdigest(),
            "d055d78c7d01f0312eae07422483dc6287a2b481da5748036a0930c036bda1e6",
        )

    def test_no_l4_implementation_import(self):
        forbidden = "benchmarks.L4_two_phase_displacement"
        paths = [BASE / "src" / "l5_d2_cases.py"]
        paths.extend(BASE / "src" / name for name in (
            "l5_state.py", "l5_solver.py", "l5_oracle.py", "l5_lifecycle.py", "l5_cases.py"
        ))
        for path in paths:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    self.assertTrue(all(not alias.name.startswith(forbidden) for alias in node.names), path.name)
                if isinstance(node, ast.ImportFrom):
                    self.assertFalse((node.module or "").startswith(forbidden), path.name)

    def test_regression_diagnostics_on_declared_power_law(self):
        levels = (80, 160, 320, 640, 1280)
        values = tuple(2.5 * (1.0 / level) ** 0.8 for level in levels)
        result = regression_diagnostics(levels, values)
        self.assertTrue(result["finite_positive"])
        self.assertTrue(result["strictly_monotone_decreasing"])
        self.assertAlmostEqual(result["order"], 0.8, places=14)
        self.assertAlmostEqual(result["r_squared"], 1.0, places=14)
        self.assertEqual(len(result["adjacent_pair_orders"]), 4)

    def test_regression_rejects_nonpositive_values(self):
        result = regression_diagnostics((80, 160, 320, 640, 1280), (1.0, 0.5, 0.0, 0.1, 0.05))
        self.assertFalse(result["finite_positive"])
        self.assertIsNone(result["order"])

    def test_independent_oracle_and_serializer(self):
        state = initial_committed(16)
        self.assertEqual(state.fingerprint, binary_fingerprint(state))
        reference = independent_oracle(160, 0.2)
        self.assertLessEqual(reference.maximum_root_residual, 1e-13)
        self.assertLessEqual(reference.phase_mass_identity_error, 1e-12)

    def test_five_level_convergence_preflight(self):
        result = execute_case(ROOT, "L5-D2-CV-01", "unit_preflight")["case_result"]
        self.assertTrue(result["pass_flag"], result)
        self.assertTrue(result["all_values_finite"])
        self.assertEqual(result["convergence_levels"], [80, 160, 320, 640, 1280])
        self.assertGreaterEqual(result["minimum_observed_regression_order"], 0.7)
        for item in result["regression_diagnostics"].values():
            self.assertTrue(item["finite_positive"])
            self.assertTrue(item["strictly_monotone_decreasing"])
            self.assertEqual(len(item["adjacent_pair_orders"]), 4)

    def test_all_cases_preflight(self):
        _, matrix = load_design(ROOT)
        for case_id in matrix:
            with self.subTest(case_id=case_id):
                payload = execute_case(ROOT, case_id, "unit_preflight")
                result = payload["case_result"]
                self.assertTrue(result["pass_flag"], result)
                self.assertTrue(result["all_values_finite"])
                self.assertEqual(result["design_version"], DESIGN_VERSION)
                self.assertEqual(result["host_version"], HOST_VERSION)
                self.assertEqual(result["case_id"], case_id)
                for collection in ("metric_comparison", "accepted_profile", "lifecycle_event_log"):
                    self.assertTrue(all(row["case_id"] == case_id for row in payload[collection]))

    def test_no_formal_result_root_created_by_preflight(self):
        self.assertFalse((BASE / "results" / "L5_D2_independent_validation").exists())

    def test_unauthorized_case(self):
        with self.assertRaises(KeyError):
            execute_case(ROOT, "L5-D2-NOT-A-CASE", "unit_preflight")


if __name__ == "__main__":
    unittest.main()
