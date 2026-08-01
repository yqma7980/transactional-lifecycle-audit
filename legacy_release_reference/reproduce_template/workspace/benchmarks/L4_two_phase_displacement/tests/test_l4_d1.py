"""Directed non-formal tests for the frozen L4-D1 implementation."""

from __future__ import annotations

import json
import math
from pathlib import Path
import unittest

from benchmarks.L4_two_phase_displacement.src.l4_cases import execute_case, load_design
from benchmarks.L4_two_phase_displacement.src.l4_fv import (
    cumulative_phase_defects,
    make_candidate,
    run_to_checkpoints,
)
from benchmarks.L4_two_phase_displacement.src.l4_lifecycle import (
    SafeTransactionalVariant,
    UnsafePreviousSaturationCacheVariant,
    compare_retry,
)
from benchmarks.L4_two_phase_displacement.src.l4_oracle import (
    BREAKTHROUGH_TIME,
    SHOCK_SATURATION,
    SHOCK_SPEED,
    analytical_identity,
    oracle_profile,
)
from benchmarks.L4_two_phase_displacement.src.l4_state import TwoPhaseModel, initial_state


ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "benchmarks" / "L4_two_phase_displacement"


class L4D1Tests(unittest.TestCase):
    def test_freeze_and_matrix_match(self) -> None:
        freeze, matrix = load_design(ROOT)
        self.assertEqual(freeze["design_version"], "L4-D1.0")
        self.assertEqual(freeze["design_status"], "FROZEN_NOT_IMPLEMENTED")
        self.assertFalse(freeze["results_exist"])
        self.assertEqual(len(matrix), 10)
        self.assertEqual(set(matrix), set(freeze["formal_cases"]))

    def test_source_manifest_matches_design(self) -> None:
        manifest = json.loads((BASE / "L4_D1_source_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["design_version"], "L4-D1.0")
        self.assertEqual(manifest["case_count"], 10)
        self.assertFalse(manifest["execution_authorized"])

    def test_analytical_identity(self) -> None:
        identity = analytical_identity()
        self.assertEqual(identity["shock_saturation"], SHOCK_SATURATION)
        self.assertEqual(identity["shock_speed"], SHOCK_SPEED)
        self.assertEqual(identity["breakthrough_time"], BREAKTHROUGH_TIME)
        self.assertLessEqual(identity["rankine_hugoniot_characteristic_residual"], 1.0e-15)

    def test_oracle_is_finite_and_pre_breakthrough(self) -> None:
        profile = oracle_profile(80, 0.2)
        self.assertLess(0.2, BREAKTHROUGH_TIME)
        self.assertTrue(all(math.isfinite(value) for value in profile.saturation_n))
        self.assertTrue(all(math.isfinite(value) for value in profile.pressure))
        self.assertLessEqual(profile.maximum_root_residual, 1.0e-13)
        self.assertLessEqual(profile.maximum_quadrature_error, 1.0e-12)

    def test_single_step_phase_balance(self) -> None:
        model = TwoPhaseModel()
        committed = initial_state(32)
        candidate = make_candidate(model, committed, 0.005, attempt_id="TEST")
        self.assertLessEqual(abs(candidate.internal_n_mass_defect), 1.0e-15)
        self.assertLessEqual(abs(candidate.internal_w_mass_defect), 1.0e-15)

    def test_cumulative_phase_balance(self) -> None:
        model = TwoPhaseModel()
        state = run_to_checkpoints(model, 64, 0.4, (0.2,))[0][0.2]
        defect_n, defect_w = cumulative_phase_defects(model, state)
        self.assertLessEqual(abs(defect_n), 1.0e-12)
        self.assertLessEqual(abs(defect_w), 1.0e-12)

    def test_safe_retry_exact(self) -> None:
        comparison = compare_retry(
            TwoPhaseModel(), 32, SafeTransactionalVariant,
            trial_dt=0.01, replay_dt=0.005,
        )
        self.assertTrue(comparison.declared_context_equal)
        self.assertTrue(comparison.committed_before_replay_unchanged)
        self.assertTrue(comparison.rejected_candidate_unreachable)
        self.assertTrue(comparison.accepted_saturation_exact)
        self.assertTrue(comparison.accepted_pressure_exact)
        self.assertTrue(comparison.accepted_output_fingerprint_exact)
        self.assertEqual(comparison.saturation_l2_drift, 0.0)
        self.assertEqual(comparison.pressure_l2_drift, 0.0)

    def test_unsafe_retry_is_finite_and_discriminating(self) -> None:
        comparison = compare_retry(
            TwoPhaseModel(), 32, UnsafePreviousSaturationCacheVariant,
            trial_dt=0.01, replay_dt=0.005,
        )
        self.assertTrue(comparison.declared_context_equal)
        self.assertTrue(comparison.committed_before_replay_unchanged)
        self.assertTrue(comparison.rejected_candidate_unreachable)
        self.assertFalse(comparison.observed_replay_fingerprint_equal)
        self.assertGreaterEqual(comparison.saturation_l2_drift, 1.0e-4)
        self.assertGreaterEqual(comparison.pressure_l2_drift, 1.0e-6)
        self.assertGreaterEqual(comparison.displacement_drift, 1.0e-6)
        self.assertGreaterEqual(comparison.declared_phase_mass_defect, 1.0e-4)
        self.assertTrue(comparison.all_values_finite)

    def test_all_frozen_cases_pass_in_memory(self) -> None:
        _, matrix = load_design(ROOT)
        for case_id in matrix:
            with self.subTest(case_id=case_id):
                payload = execute_case(ROOT, case_id, "unit_preflight")
                self.assertTrue(payload["case_result"]["pass_flag"])
                self.assertTrue(payload["case_result"]["all_values_finite"])

    def test_unauthorized_case_rejected(self) -> None:
        with self.assertRaises(KeyError):
            execute_case(ROOT, "L4-NOT-A-CASE", "unit_preflight")


if __name__ == "__main__":
    unittest.main()

