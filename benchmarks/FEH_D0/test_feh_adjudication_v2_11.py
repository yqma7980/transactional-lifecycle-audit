from __future__ import annotations

import sys
import types
import unittest

# The adjudication contract is intentionally unit-tested without importing or
# executing the finite-element model. The runner only needs these names at
# module import; none is called by classify_replay_comparison.
feh_model = types.ModuleType("feh_model")
for name in (
    "SERIALIZER_VERSION", "audit_replay_pair", "case_payload",
    "compare_histories", "patch_oracle", "run_history",
):
    setattr(feh_model, name, None)
sys.modules.setdefault("feh_model", feh_model)

from run_feh_d0 import INVALID_A4, classify_replay_comparison


def comparison(*, persistent_equal: bool, drift: float) -> dict:
    return {
        "all_values_finite": True,
        "persistent_fingerprint_equal": persistent_equal,
        "observed_persistent_fingerprint_equal": persistent_equal,
        "residual_relative_drift": drift,
        "tangent_relative_drift": drift,
        "displacement_relative_error": 0.0,
        "reaction_relative_error": 0.0,
        "stress_relative_error": 0.0,
        "kappa_relative_error": 0.0,
    }


class TestFEHAdjudicationV211(unittest.TestCase):
    def test_safe_control_is_full_tla_pass(self):
        result = classify_replay_comparison(
            "safe_transactional",
            "PASS_SAFE_LINE_SEARCH_PARITY",
            True,
            True,
            comparison(persistent_equal=True, drift=0.0),
        )
        self.assertTrue(result["full_tla_pass_flag"])
        self.assertTrue(result["formal_case_contract_pass"])
        self.assertEqual(result["full_tla_verdict"], "PASS_SAFE_LINE_SEARCH_PARITY")

    def test_seeded_control_is_invalid_a4_but_detected(self):
        result = classify_replay_comparison(
            "unsafe_trial_cache",
            "DETECT_TRIAL_CACHE_DRIFT",
            True,
            True,
            comparison(persistent_equal=False, drift=1.0e-3),
        )
        self.assertFalse(result["a4_persistent_compatibility_satisfied"])
        self.assertFalse(result["full_tla_pass_flag"])
        self.assertEqual(result["full_tla_verdict"], INVALID_A4)
        self.assertTrue(result["operator_replay_drift_detected"])
        self.assertTrue(result["negative_control_gate_pass"])
        self.assertTrue(result["formal_case_contract_pass"])

    def test_seeded_control_without_drift_fails_control_gate(self):
        result = classify_replay_comparison(
            "unsafe_output_feedback",
            "DETECT_OUTPUT_FEEDBACK_DRIFT",
            True,
            True,
            comparison(persistent_equal=False, drift=0.0),
        )
        self.assertEqual(result["full_tla_verdict"], INVALID_A4)
        self.assertFalse(result["operator_replay_drift_detected"])
        self.assertFalse(result["negative_control_gate_pass"])
        self.assertFalse(result["formal_case_contract_pass"])


if __name__ == "__main__":
    unittest.main()

