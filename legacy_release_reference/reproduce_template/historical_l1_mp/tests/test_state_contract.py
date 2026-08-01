from __future__ import annotations

from pathlib import Path
import unittest

from src.l1_material import evaluate_material
from src.l1_state import (
    CommittedState,
    MaterialData,
    TransactionHost,
    checkpoint_payload,
    checkpoint_restore,
)
from src.l1_variants import SafeLocal, SafeTransactional, UnsafeOutputFeedback, UnsafeTrialCache


class StateContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.material = MaterialData()

    def test_pure_evaluation_does_not_mutate_committed_state(self) -> None:
        committed = CommittedState()
        before_hash = committed.fingerprint
        evaluate_material(
            0.03,
            committed,
            self.material,
            candidate_id="c1",
            attempt_id="a1",
            source_call_index=0,
        )
        self.assertEqual(committed.fingerprint, before_hash)

    def test_transaction_reject_invalidates_candidates(self) -> None:
        variant = SafeTransactional(self.material)
        variant.begin_attempt("a1")
        result = variant.evaluate(0.03, candidate_id="c1", attempt_id="a1", source_call_index=0)
        self.assertTrue(variant.candidate_reachable(result.candidate.candidate_id))
        before = variant.committed
        variant.reject_attempt("a1")
        self.assertFalse(variant.candidate_reachable(result.candidate.candidate_id))
        self.assertEqual(variant.committed, before)

    def test_accept_advances_once(self) -> None:
        variant = SafeTransactional(self.material)
        variant.begin_attempt("a1")
        result = variant.evaluate(0.03, candidate_id="c1", attempt_id="a1", source_call_index=0)
        first, _ = variant.accept(result.candidate)
        after_first = variant.committed
        second, reason = variant.accept(result.candidate)
        self.assertTrue(first)
        self.assertFalse(second)
        self.assertEqual(reason, "duplicate_accept_rejected")
        self.assertEqual(variant.committed, after_first)
        self.assertEqual(after_first.accepted_version, 1)

    def test_safe_terminal_read_is_noninterfering(self) -> None:
        for cls in (SafeLocal, SafeTransactional):
            variant = cls(self.material)
            before = variant.committed
            persistent = variant.persistent_hash
            snapshot = variant.terminal_read(0.03)
            self.assertEqual(variant.committed, before)
            self.assertEqual(variant.persistent_hash, persistent)
            self.assertEqual(snapshot.source_version, "accepted:0")

    def test_unsafe_trial_cache_seed_is_finite_and_nonzero(self) -> None:
        variant = UnsafeTrialCache(self.material)
        variant.evaluate(0.03, candidate_id="discard", attempt_id="a", source_call_index=0)
        variant.reject_attempt("a")
        replay = variant.evaluate(0.005, candidate_id="replay", attempt_id="r", source_call_index=1)
        self.assertAlmostEqual(replay.sigma, -289.0 / 242.0, places=14)

    def test_unsafe_output_feedback_seed_is_noninterfering_only_for_safe_controls(self) -> None:
        variant = UnsafeOutputFeedback(self.material)
        snapshot = variant.terminal_read(0.03)
        replay = variant.evaluate(0.005, candidate_id="replay", attempt_id="r", source_call_index=1)
        self.assertEqual(snapshot.source_version, "trial_hidden")
        self.assertNotEqual(replay.sigma, 0.5)
        self.assertEqual(variant.committed, CommittedState())

    def test_checkpoint_round_trip(self) -> None:
        committed = CommittedState(epsilon_p=1.0 / 55.0, kappa=1.0 / 55.0, accepted_version=1)
        payload = checkpoint_payload(committed, "f" * 64)
        restored = checkpoint_restore(payload, "f" * 64)
        self.assertEqual(restored, committed)
        self.assertEqual(restored.fingerprint, committed.fingerprint)


if __name__ == "__main__":
    unittest.main()

