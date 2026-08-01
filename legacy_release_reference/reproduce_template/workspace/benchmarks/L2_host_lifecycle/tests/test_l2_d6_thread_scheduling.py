"""Directed tests for the L2-D6 support-envelope implementation."""

from pathlib import Path
import unittest

from oracle.l2_d6_fraction_oracle import derive_thread_support_oracle
from src.l2_d6_thread_scheduling import (
    EXPECTED_GATE,
    EXPECTED_OUTCOME,
    execute_thread_scheduling_case,
    inspect_scheduling_capability,
    load_frozen_design,
)


ROOT = Path(__file__).resolve().parents[1]


class L2D6ThreadSchedulingTests(unittest.TestCase):
    def test_frozen_case_identity(self):
        freeze, matrix = load_frozen_design(ROOT)
        self.assertEqual(freeze["design_version"], "L2-D6.0")
        self.assertEqual([row["case_id"] for row in matrix], ["L2-TH-01"])

    def test_capability_probe_detects_serial_host(self):
        freeze, _ = load_frozen_design(ROOT)
        capability = inspect_scheduling_capability(ROOT, freeze)
        self.assertTrue(capability.host_declared_single_threaded)
        self.assertTrue(capability.thread_count_metadata_present)
        self.assertEqual(capability.parallel_backend_markers, ())
        self.assertFalse(capability.alternate_setting_supported)

    def test_fraction_oracle_has_no_parallel_parity_claim(self):
        oracle = derive_thread_support_oracle()
        self.assertEqual(oracle["serial_reference"]["displacement"], "21/1000")
        self.assertIsNone(oracle["parallel_parity_oracle"])

    def test_th01_reports_not_supported_and_passes_reporting_gate(self):
        result = execute_thread_scheduling_case(ROOT, "L2-TH-01", "unit")
        self.assertTrue(result.pass_flag)
        self.assertEqual(result.primary_gate_classification, EXPECTED_GATE)
        self.assertEqual(result.observed_outcome, EXPECTED_OUTCOME)
        self.assertFalse(result.capability.alternate_setting_supported)
        self.assertFalse(result.comparison.synthetic_concurrency_executed)

    def test_serial_health_reference_matches_exact_fingerprints(self):
        result = execute_thread_scheduling_case(ROOT, "L2-TH-01", "unit")
        self.assertTrue(result.comparison.serial_reference_analytical_match)
        self.assertTrue(result.comparison.serial_reference_committed_hash_exact)
        self.assertTrue(result.comparison.serial_reference_physical_hash_exact)
        self.assertTrue(result.comparison.all_values_finite)

    def test_event_ledger_contains_no_parallel_execution(self):
        result = execute_thread_scheduling_case(ROOT, "L2-TH-01", "unit")
        self.assertEqual(len(result.events), 4)
        self.assertTrue(all(not row["synthetic_concurrency_executed"] for row in result.events))
        self.assertIn("DeclineSyntheticAlternate", [row["event"] for row in result.events])

    def test_unauthorized_case_rejected(self):
        with self.assertRaises(ValueError):
            execute_thread_scheduling_case(ROOT, "L2-CP-01", "unit")

    def test_claim_boundary_is_explicit(self):
        result = execute_thread_scheduling_case(ROOT, "L2-TH-01", "unit")
        self.assertIn("not thread-safety", result.claim_boundary)
        self.assertIn("performance", result.claim_boundary)


if __name__ == "__main__":
    unittest.main()
