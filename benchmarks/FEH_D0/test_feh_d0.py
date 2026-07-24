from __future__ import annotations

import unittest

import numpy as np

from feh_model import FEHost, audit_replay_pair, canonical_hash, compare_histories, patch_oracle, run_history


class FEHD0Tests(unittest.TestCase):
    def test_canonical_hash_is_repeatable(self):
        value = {"a": np.array([0.0, 1.0]), "b": 2}
        self.assertEqual(canonical_hash(value), canonical_hash(value))

    def test_host_has_multiple_elements_and_quadrature_points(self):
        host = FEHost(8, 6, True, "safe_transactional", 0.0, "test")
        self.assertEqual(host.mesh.nelements, 48)
        self.assertEqual(host.committed.kappa.size, 192)

    def test_patch_oracle_is_plastic(self):
        oracle = patch_oracle()
        self.assertGreater(oracle["kappa"], 0.0)
        self.assertLess(oracle["stress"], 10.0 * 0.12)

    def test_short_safe_history_converges(self):
        result = run_history("direct", load_sequence=(0.2,), heterogeneous=False)
        self.assertTrue(result.pass_flag)
        self.assertEqual(len(result.accepted_rows), 1)

    def test_safe_rejected_probe_replays(self):
        direct = run_history("direct")
        extra = run_history("rejected_line_search")
        comparison = compare_histories(direct, extra)
        self.assertTrue(comparison["declared_fingerprint_equal"])
        self.assertLessEqual(comparison["residual_relative_drift"], 1e-12)
        self.assertLessEqual(comparison["tangent_relative_drift"], 1e-12)

    def test_unsafe_history_keeps_declared_packet_equal(self):
        comparison, _ = audit_replay_pair("unsafe_trial_cache", 1e-2)
        self.assertTrue(comparison["declared_fingerprint_equal"])
        self.assertGreater(comparison["tangent_relative_drift"], 1e-8)


if __name__ == "__main__":
    unittest.main()
