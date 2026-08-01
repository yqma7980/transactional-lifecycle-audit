"""Targeted unit tests for the L2-D3.0b implementation correction."""

from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.l2_d3b_tangent_path import (
    ABSOLUTE_TOLERANCE,
    CORRECTIVE_REPLAY_CLASSIFICATION,
    EXPECTED_CLASSIFICATION,
    classify_tg02,
    compare_tg02_paths,
    corrective_replay_from_payload,
    execute_tangent_path_case,
    load_correction_freeze,
    original_tg01_exact_rule_is_unchanged,
)


RUN_ROOT = ROOT / "results" / "L2_D3_tangent_path" / "L2-TG-02"
RUN_1 = RUN_ROOT / "run_1"
NEW_RESULT_ROOT = ROOT / "results" / "L2_D3b_tangent_path"
EXPECTED_HASHES = {
    "case_manifest.json": (
        "d0e0224f3120fc37a39a5f0365f50307259f93e623a27d2a30fade9be495ed23"
    ),
    "case_result.json": (
        "536dab4abc7a7b710f5f1da0a17e1addbcc0af963b994e0d6982efdfc45749ee"
    ),
    "path_comparison.csv": (
        "e92b96b7ad95839d1b8ceb6f3c38a4563c5f9fd1b42ff49d4567b4c6c44ecbfe"
    ),
    "tangent_event_log.csv": (
        "6d37199764f69b08c746da06a9f2278f1cd2fecafcba6d3db07f5ea2522d2287"
    ),
}


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class D3bCorrectionContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        load_correction_freeze(ROOT)
        cls.payload = json.loads(
            (RUN_1 / "case_result.json").read_text(encoding="utf-8")
        )
        cls.replay = corrective_replay_from_payload(cls.payload)

    def test_preserved_run_hashes_and_scope(self) -> None:
        self.assertTrue(RUN_1.is_dir())
        self.assertFalse((RUN_ROOT / "run_2").exists())
        self.assertFalse(
            (ROOT / "results" / "L2_D3_tangent_path" / "L2-TG-03").exists()
        )
        for name, expected in EXPECTED_HASHES.items():
            self.assertEqual(file_hash(RUN_1 / name), expected)

    def test_preserved_deltas_are_within_frozen_tolerance(self) -> None:
        fields = self.replay.comparison.accepted_fields
        self.assertLessEqual(abs(fields.u_delta), ABSOLUTE_TOLERANCE)
        self.assertLessEqual(abs(fields.sigma_delta), ABSOLUTE_TOLERANCE)
        self.assertLessEqual(abs(fields.epsilon_p_delta), ABSOLUTE_TOLERANCE)
        self.assertLessEqual(abs(fields.kappa_delta), ABSOLUTE_TOLERANCE)
        self.assertLessEqual(abs(fields.force_delta), ABSOLUTE_TOLERANCE)
        self.assertTrue(fields.all_equal)

    def test_fingerprint_difference_is_informational_for_tg02(self) -> None:
        self.assertFalse(self.replay.comparison.accepted_fingerprint_equal)
        self.assertTrue(self.replay.pass_flag)
        self.assertEqual(
            self.replay.observed_classification,
            CORRECTIVE_REPLAY_CLASSIFICATION,
        )

    def test_field_outside_tolerance_fails(self) -> None:
        left = self.replay.left_path
        right = replace(
            self.replay.right_path,
            accepted_u=left.accepted_u + 2.0e-12,
        )
        comparison = compare_tg02_paths(left, right)
        observed, passed = classify_tg02(comparison)
        self.assertFalse(comparison.accepted_field_equal)
        self.assertFalse(passed)
        self.assertEqual(observed, "FAIL_DECLARED_LAGGED_TANGENT_PARITY")

    def test_evaluation_counts_and_iteration_parity(self) -> None:
        comparison = self.replay.comparison
        self.assertEqual(comparison.left_evaluation_count, 3)
        self.assertEqual(comparison.right_evaluation_count, 4)
        self.assertFalse(comparison.iteration_count_equal)
        self.assertEqual(EXPECTED_CLASSIFICATION, classify_tg02(comparison)[0])
        invalid = replace(comparison, right_evaluation_count=5)
        self.assertFalse(classify_tg02(invalid)[1])

    def test_each_committed_transition_is_independently_valid(self) -> None:
        comparison = self.replay.comparison
        self.assertTrue(comparison.left_committed_transition_valid)
        self.assertTrue(comparison.right_committed_transition_valid)
        self.assertTrue(comparison.committed_transition_valid)
        self.assertFalse(comparison.cross_path_committed_fingerprint_equal)
        self.assertEqual(
            self.replay.left_path.committed_fingerprint_after,
            comparison.left_expected_committed_after,
        )
        self.assertEqual(
            self.replay.right_path.committed_fingerprint_after,
            comparison.right_expected_committed_after,
        )

    def test_invalid_path_transition_fails(self) -> None:
        invalid_left = replace(
            self.replay.left_path,
            committed_fingerprint_after="invalid-transition",
        )
        comparison = compare_tg02_paths(invalid_left, self.replay.right_path)
        self.assertFalse(comparison.left_committed_transition_valid)
        self.assertTrue(comparison.right_committed_transition_valid)
        self.assertFalse(classify_tg02(comparison)[1])

    def test_rejected_candidates_remain_unreachable(self) -> None:
        self.assertTrue(self.replay.comparison.candidates_unreachable)
        invalid_right = replace(
            self.replay.right_path,
            candidates_unreachable_after_accept=False,
        )
        comparison = compare_tg02_paths(self.replay.left_path, invalid_right)
        self.assertFalse(comparison.candidates_unreachable)
        self.assertFalse(classify_tg02(comparison)[1])

    def test_tg01_exact_fingerprint_rule_is_not_relaxed(self) -> None:
        original = self.replay.comparison.original_comparison
        self.assertIsNotNone(original)
        strict_failure = replace(
            original,
            case_id="L2-TG-01",
            left_evaluation_count=3,
            right_evaluation_count=3,
            packet_semantic_equal=True,
            accepted_field_equal=True,
            accepted_fingerprint_equal=False,
            iteration_count_equal=True,
            committed_transition_valid=True,
            candidates_unreachable=True,
            all_values_finite=True,
        )
        self.assertFalse(
            original_tg01_exact_rule_is_unchanged(strict_failure)
        )
        strict_pass = replace(
            strict_failure,
            accepted_fingerprint_equal=True,
        )
        self.assertTrue(original_tg01_exact_rule_is_unchanged(strict_pass))

    def test_unauthorized_case_is_rejected_before_execution(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unauthorized"):
            execute_tangent_path_case(ROOT, "L2-TG-03", "UNIT-ONLY")

    def test_import_and_tests_create_no_formal_outputs_or_bytecode(self) -> None:
        self.assertFalse(NEW_RESULT_ROOT.exists())
        self.assertEqual(list(ROOT.rglob("__pycache__")), [])


if __name__ == "__main__":
    unittest.main()
