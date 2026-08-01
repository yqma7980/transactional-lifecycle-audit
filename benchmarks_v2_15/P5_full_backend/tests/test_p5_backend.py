from __future__ import annotations

import ast
import os
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from p5_arithmetic import PATH_IDS, reduce_operator, synthetic_triangle_packet
from p5_backend_contracts import (
    CASE_IDS,
    case_authorized,
    load_case_contracts,
    load_strength_grid,
    matrix_authorized,
    require_case_and_run,
    strength_index_for_run,
    verify_protected_evidence,
)
from p5_case_executor import flatten_term_lists
from p5_fe_adapter import P5PersistentState, inject_fault
from p5_scheduler import _normalize


class P5BackendTests(unittest.TestCase):
    def test_01_protected_evidence_and_process_budget(self):
        checked = verify_protected_evidence()
        self.assertGreater(checked["freeze_entries"], 0)
        self.assertGreater(checked["preflight_entries"], 0)
        contracts = load_case_contracts()
        self.assertEqual(tuple(item.case_id for item in contracts), CASE_IDS)
        self.assertEqual(sum(item.process_budget for item in contracts), 90)

    def test_02_strength_grid_and_run_mapping(self):
        grid = load_strength_grid()
        self.assertEqual(len(grid), 15)
        self.assertEqual(strength_index_for_run("P5-SCALE-F01-DEV", "run_1", None), 0)
        self.assertEqual(strength_index_for_run("P5-SCALE-F01-DEV", "run_15", None), 14)
        self.assertIsNone(strength_index_for_run("P5-NULL-EXACT-CAL-01", "run_1", None))
        with self.assertRaises(SystemExit):
            require_case_and_run("P5-SCALE-F01-DEV", "run_20")

    def test_03_case_and_matrix_dual_locks(self):
        self.assertFalse(case_authorized(False, {}))
        self.assertFalse(case_authorized(True, {}))
        self.assertTrue(case_authorized(True, {"P5_EXECUTION_AUTHORIZED": "YES"}))
        self.assertFalse(matrix_authorized(True, {}))
        self.assertTrue(matrix_authorized(True, {"P5_MATRIX_EXECUTION_AUTHORIZED": "YES"}))

    def test_04_arithmetic_paths_are_deterministic_and_distinguishing(self):
        packet = synthetic_triangle_packet()
        outputs = {path_id: reduce_operator(packet, path_id) for path_id in PATH_IDS}
        for path_id in PATH_IDS:
            np.testing.assert_array_equal(outputs[path_id].residual, reduce_operator(packet, path_id).residual)
            np.testing.assert_array_equal(outputs[path_id].tangent, reduce_operator(packet, path_id).tangent)
        self.assertNotEqual(outputs["ARITH_A_REFERENCE"].residual[0], outputs["ARITH_B_CALIBRATION"].residual[0])

    def test_05_fault_bindings_touch_only_frozen_fields(self):
        for family, expected in {
            "F01": "trial_cache.gamma_p[0,0,0]",
            "F02": "declared_snapshot.alpha[0,1]",
            "F05": "feedback_mirror_E@first_lambda_0.10_replay",
            "F07": "callback_bias_F@extra_nonaccepting_residual",
        }.items():
            state = P5PersistentState()
            before = state.snapshot()
            record = inject_fault(state, family, 0.5, "candidate")
            self.assertEqual(record["field_binding"], expected)
            self.assertEqual(state.mutation_count, 1)
            self.assertNotEqual(before["projection_hash"], state.projection_hash)
        self.assertAlmostEqual(P5PersistentState().hidden_trial_cache.sum(), 0.0)

    def test_06_flattened_contributions_require_no_pickle(self):
        values, offsets = flatten_term_lists(((1.0, 2.0), (), (3.0,)))
        np.testing.assert_array_equal(values, np.array([1.0, 2.0, 3.0]))
        np.testing.assert_array_equal(offsets, np.array([0, 2, 2, 3]))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "terms.npz"
            np.savez(path, values=values, offsets=offsets)
            with np.load(path, allow_pickle=False) as archive:
                np.testing.assert_array_equal(archive["values"], values)

    def test_07_duplicate_normalization_removes_only_diagnostics(self):
        left = {"run_id": "run_1", "wall_clock_timestamp": "a", "scientific": {"value": 3}}
        right = {"run_id": "run_2", "wall_clock_timestamp": "b", "scientific": {"value": 3}}
        self.assertEqual(_normalize(left), _normalize(right))
        right["scientific"]["value"] = 4
        self.assertNotEqual(_normalize(left), _normalize(right))

    def test_08_runner_contracts_are_present_in_ast(self):
        single = (ROOT / "run_p5.py").read_text(encoding="utf-8")
        matrix = (ROOT / "run_p5_matrix.py").read_text(encoding="utf-8")
        ast.parse(single)
        ast.parse(matrix)
        self.assertIn("P5_EXECUTION_AUTHORIZED", (ROOT / "src" / "p5_backend_contracts.py").read_text(encoding="utf-8"))
        self.assertIn("P5_MATRIX_EXECUTION_AUTHORIZED", (ROOT / "src" / "p5_backend_contracts.py").read_text(encoding="utf-8"))
        self.assertIn("--network\", \"none", matrix)
        self.assertIn("range(1, 16)", matrix)
        self.assertIn("range(16, 20)", matrix)

    def test_09_import_has_no_result_side_effect(self):
        self.assertFalse((ROOT / "results").exists())
        self.assertFalse(any(ROOT.rglob("__pycache__")))


if __name__ == "__main__":
    unittest.main()
