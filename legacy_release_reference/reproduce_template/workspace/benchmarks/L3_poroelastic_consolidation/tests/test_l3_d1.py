"""Directed tests for L3-D1.0a poroelastic consolidation."""

from __future__ import annotations

import json
from pathlib import Path
import unittest

from benchmarks.L3_poroelastic_consolidation.src.l3_canonical import L2_STATE_SHA256
from benchmarks.L3_poroelastic_consolidation.src.l3_cases import execute_case, load_design
from benchmarks.L3_poroelastic_consolidation.src.l3_lifecycle import (
    SafeTransactionalVariant,
    UnsafePreviousStateCacheVariant,
    compare_retry,
)
from benchmarks.L3_poroelastic_consolidation.src.l3_oracle import mean_pressure, pressure_at
from benchmarks.L3_poroelastic_consolidation.src.l3_state import PoroModel


ROOT = Path(__file__).resolve().parents[3]
CASE_IDS = (
    "L3-REF-01", "L3-CV-S-01", "L3-CV-T-01", "L3-MB-01",
    "L3-ST-01", "L3-RT-01", "L3-RT-02",
)


class L3D1Tests(unittest.TestCase):
    def test_frozen_identity_and_case_set(self):
        freeze, matrix = load_design(ROOT)
        self.assertEqual(freeze["design_version"], "L3-D1.0a")
        self.assertEqual(set(matrix), set(CASE_IDS))
        self.assertFalse(freeze["execution_authorized"])
        self.assertFalse(freeze["results_exist"])

    def test_model_reductions_are_frozen(self):
        model = PoroModel()
        self.assertEqual(model.storage_coefficient, 0.5)
        self.assertEqual(model.diffusivity, 1.0)
        self.assertEqual(model.p0, 0.5)

    def test_authoritative_l2_serializer_hash(self):
        manifest = json.loads((ROOT / "benchmarks" / "L3_poroelastic_consolidation" / "L3_D1_source_manifest.json").read_text(encoding="utf-8"))
        declared = next(row["sha256"] for row in manifest["protected_inputs"] if row["path"].endswith("l2_state.py"))
        self.assertEqual(L2_STATE_SHA256, declared)

    def test_fourier_oracle_is_finite_and_bounded(self):
        model = PoroModel()
        point = pressure_at(model, 0.5, 0.2)
        mean = mean_pressure(model, 0.2)
        self.assertGreater(point.value, 0.0)
        self.assertLess(point.value, model.p0)
        self.assertGreater(mean.value, 0.0)
        self.assertLess(mean.value, model.p0)
        self.assertLessEqual(max(point.tail_envelope, mean.tail_envelope), 1.0e-15)

    def test_reference_case(self):
        result = execute_case(ROOT, "L3-REF-01", "unit")["case_result"]
        self.assertTrue(result["pass_flag"])
        self.assertEqual(result["observed_classification"], "PASS_ANALYTICAL_REFERENCE")
        self.assertTrue(result["all_values_finite"])

    def test_convergence_cases(self):
        spatial = execute_case(ROOT, "L3-CV-S-01", "unit")["case_result"]
        temporal = execute_case(ROOT, "L3-CV-T-01", "unit")["case_result"]
        self.assertTrue(spatial["pass_flag"])
        self.assertTrue(temporal["pass_flag"])
        self.assertGreaterEqual(spatial["pressure_orders"][1], 1.7)
        self.assertGreaterEqual(spatial["settlement_orders"][1], 1.7)
        self.assertGreaterEqual(temporal["pressure_orders"][1], 0.8)
        self.assertGreaterEqual(temporal["settlement_orders"][1], 0.8)

    def test_mass_and_stability_cases(self):
        mass = execute_case(ROOT, "L3-MB-01", "unit")["case_result"]
        stability = execute_case(ROOT, "L3-ST-01", "unit")["case_result"]
        self.assertTrue(mass["pass_flag"])
        self.assertLessEqual(mass["maximum_step_mass_defect_normalized"], 5.0e-12)
        self.assertLessEqual(mass["cumulative_mass_defect_normalized"], 5.0e-12)
        self.assertTrue(stability["pass_flag"])
        self.assertTrue(stability["pressure_bounds_ok"])
        self.assertTrue(stability["pressure_depth_monotone"])

    def test_safe_retry_exact_and_event_transaction(self):
        comparison = compare_retry(PoroModel(), 32, SafeTransactionalVariant)
        self.assertTrue(comparison.declared_context_equal)
        self.assertTrue(comparison.committed_before_replay_unchanged)
        self.assertTrue(comparison.rejected_candidate_unreachable)
        self.assertTrue(comparison.accepted_pressure_exact)
        self.assertTrue(comparison.accepted_state_fingerprint_exact)
        self.assertEqual(comparison.pressure_l2_drift, 0.0)
        self.assertEqual(comparison.settlement_drift, 0.0)
        trial = next(row for row in comparison.events if row["history_id"] == "RETRY" and row["event"] == "TrialEvaluate" and row["attempt_id"] == "REJECTED_TRIAL")
        rejected = next(row for row in comparison.events if row["event"] == "RejectAttempt")
        self.assertTrue(trial["candidate_reachable"])
        self.assertFalse(rejected["candidate_reachable"])

    def test_unsafe_retry_is_finite_discriminating_control(self):
        comparison = compare_retry(PoroModel(), 32, UnsafePreviousStateCacheVariant)
        self.assertTrue(comparison.declared_context_equal)
        self.assertTrue(comparison.committed_before_replay_unchanged)
        self.assertTrue(comparison.rejected_candidate_unreachable)
        self.assertFalse(comparison.observed_replay_fingerprint_equal)
        self.assertGreaterEqual(comparison.pressure_l2_drift, 1.0e-8)
        self.assertGreaterEqual(comparison.settlement_drift, 1.0e-10)
        self.assertGreaterEqual(comparison.declared_mass_defect, 1.0e-8)
        self.assertTrue(comparison.all_values_finite)

    def test_all_frozen_cases_preflight(self):
        for case_id in CASE_IDS:
            with self.subTest(case_id=case_id):
                result = execute_case(ROOT, case_id, "unit")["case_result"]
                self.assertTrue(result["pass_flag"])
                self.assertTrue(result["all_values_finite"])

    def test_unauthorized_case_rejected(self):
        with self.assertRaises(KeyError):
            execute_case(ROOT, "L3-NOT-A-CASE", "unit")


if __name__ == "__main__":
    unittest.main()
