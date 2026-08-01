from __future__ import annotations

import math
import os
import sys
import unittest
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "oracle"))

from p5_contracts import CASE_IDS, case_authorized, load_case_contracts, verify_frozen_evidence
from p5_fraction_oracle import derive_binary_grid, expected_development_deltas, process_budget
from p5_mutations import apply_confirmation_binding, apply_development_mutation, zero_state
from p5_null_envelope import complete_pairwise_envelope, load_metric_scales, reduce_values, scaled_distance, thresholds
from p5_selector import SweepRow, select_strength, verify_fresh_repetitions


class P5PreflightTests(unittest.TestCase):
    def test_01_frozen_evidence_and_matrix(self):
        self.assertEqual(verify_frozen_evidence(), {"outputs": 9, "protected_inputs": 19})
        contracts = load_case_contracts()
        self.assertEqual(tuple(item.case_id for item in contracts), CASE_IDS)
        self.assertEqual(sum(item.planned_fresh_process_count for item in contracts), 90)

    def test_02_authorization_requires_both_locks(self):
        self.assertFalse(case_authorized(False, {}))
        self.assertFalse(case_authorized(True, {}))
        self.assertFalse(case_authorized(False, {"P5_EXECUTION_AUTHORIZED": "YES"}))
        self.assertTrue(case_authorized(True, {"P5_EXECUTION_AUTHORIZED": "YES"}))

    def test_03_fraction_oracle_grid_and_budget(self):
        grid = derive_binary_grid()
        self.assertEqual(len(grid), 15)
        self.assertEqual(grid[0]["eta"], Fraction(1, 2**48))
        self.assertEqual(grid[-1]["eta"], Fraction(1, 2**6))
        self.assertEqual(process_budget()["total"], 90)
        deltas = expected_development_deltas()
        self.assertEqual(deltas["F01"][0], Fraction(1, 10 * 2**48))
        self.assertEqual(deltas["F05"][-1], Fraction(1, 64))

    def test_04_metric_registry_and_null_envelope(self):
        registry = ROOT.parent / "P5_SCALED_THRESHOLD_AND_FRESH_PROCESS_NULL_ENVELOPE_FREEZE_20260731" / "P5_field_and_metric_scale_registry.csv"
        scales = load_metric_scales(registry)
        base = {metric: [1.0, -0.5] for metric in scales}
        perturbed = {metric: [1.0 + 1.0e-14, -0.5] for metric in scales}
        envelope = complete_pairwise_envelope([base, perturbed], scales)
        frozen = thresholds(envelope)
        self.assertTrue(all(value >= 1024 * 2.220446049250313e-16 for value in frozen.values()))
        self.assertAlmostEqual(scaled_distance([1.0], [1.0], 1.0), 0.0)

    def test_05_arithmetic_paths_are_deterministic(self):
        values = [1.0e16, 1.0, -1.0e16, 3.0] * 8
        for path_id in ("ARITH_A_REFERENCE", "ARITH_B_CALIBRATION", "ARITH_C_CONFIRMATION", "ARITH_D_P6_BENIGN"):
            self.assertEqual(reduce_values(values, path_id), reduce_values(values, path_id))

    def test_06_mutations_touch_only_frozen_sites(self):
        source = zero_state()
        f01 = apply_development_mutation(source, "F01", 0.5)
        self.assertEqual(source.gamma_p[0][0][0], 0.0)
        self.assertAlmostEqual(f01.state.gamma_p[0][0][0], 0.05)
        f02 = apply_development_mutation(source, "F02", 0.5)
        self.assertAlmostEqual(f02.state.alpha[0][1], 0.05)
        f05 = apply_development_mutation(source, "F05", 0.5)
        self.assertTrue(f05.state.rejected_source_reachable)
        self.assertAlmostEqual(f05.state.feedback_mirror_E, 0.5)
        f07 = apply_development_mutation(source, "F07", 0.5)
        self.assertAlmostEqual(f07.state.callback_bias_F, 0.5)

    def test_07_confirmation_bindings_are_fixed(self):
        source = zero_state()
        f01 = apply_confirmation_binding(source, "F01", 0.25)
        self.assertAlmostEqual(f01.state.gamma_p[31][2][1], 0.025)
        f05 = apply_confirmation_binding(source, "F05", 0.25)
        self.assertAlmostEqual(f05.state.feedback_mirror_J, 0.25)

    def test_08_selector_requires_complete_grid_and_adjacent_levels(self):
        grid = derive_binary_grid()
        rows = [
            SweepRow(index, float(item["eta"]), True, index >= 5, True, 11.0 if index >= 5 else 0.0, 0.0)
            for index, item in enumerate(grid)
        ]
        selected = select_strength(rows)
        self.assertEqual(selected.selected_index, 5)
        self.assertEqual(selected.next_index, 6)
        with self.assertRaises(ValueError):
            select_strength(rows[:-1])

    def test_09_duplicate_verification_is_exact_after_run_metadata_removal(self):
        grid = derive_binary_grid()
        rows = [SweepRow(i, float(item["eta"]), True, i >= 5, True, 11.0 if i >= 5 else 0.0, 0.0) for i, item in enumerate(grid)]
        selected = select_strength(rows)
        base = {"conventional_quiet": True, "lifecycle_violation_present": True, "z_family": 11.0}
        repetitions = {
            5: [{**base, "run_id": "run_1"}, {**base, "run_id": "run_2"}],
            6: [{**base, "run_id": "run_1"}, {**base, "run_id": "run_2"}],
        }
        self.assertEqual(verify_fresh_repetitions(selected, repetitions), "PASS_FRESH_PROCESS_VERIFICATION")

    def test_10_import_does_not_create_results(self):
        self.assertFalse((ROOT / "results").exists())


if __name__ == "__main__":
    unittest.main()
