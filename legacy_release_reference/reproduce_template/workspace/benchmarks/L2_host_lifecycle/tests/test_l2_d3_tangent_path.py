"""Future execution tests for L2-D3.0.

The static implementation task creates this definition but does not run it.
"""

from __future__ import annotations

from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from oracle.l2_d3_fraction_oracle import derive_tangent_path_oracle
from src.l2_d3_tangent_path import (
    AUTHORIZED_CASES,
    DESIGN_VERSION,
    EXPECTED_CLASSIFICATIONS,
    build_tg03_packets,
    execute_tangent_path_case,
    load_frozen_design,
    validate_operator_versions,
)


class TangentPathStaticContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.freeze, cls.matrix = load_frozen_design(ROOT)

    def test_freeze_and_matrix_versions_match(self) -> None:
        self.assertEqual(DESIGN_VERSION, "L2-D3.0")
        self.assertEqual(self.freeze["design_version"], DESIGN_VERSION)
        self.assertEqual(self.freeze["design_status"], "FROZEN_NOT_IMPLEMENTED")
        self.assertFalse(self.freeze["execution_authorized"])
        self.assertFalse(self.freeze["results_exist"])

    def test_case_ids_are_unique_and_exact(self) -> None:
        case_ids = tuple(row["case_id"] for row in self.matrix)
        self.assertEqual(case_ids, AUTHORIZED_CASES)
        self.assertEqual(len(case_ids), len(set(case_ids)))
        for row in self.matrix:
            self.assertEqual(
                row["expected_classification"],
                EXPECTED_CLASSIFICATIONS[row["case_id"]],
            )

    def test_frozen_analytical_paths(self) -> None:
        oracle = derive_tangent_path_oracle()
        self.assertEqual(oracle["exact_evaluation_count"], 3)
        self.assertEqual(oracle["declared_lagged_evaluation_count"], 4)
        self.assertTrue(oracle["accepted_fields_equal"])
        self.assertEqual(oracle["accepted_state"]["u"], "21/1000")
        self.assertEqual(oracle["accepted_state"]["sigma"], "11/10")
        self.assertEqual(oracle["accepted_state"]["epsilon_p"], "1/100")
        self.assertEqual(oracle["accepted_state"]["kappa"], "1/100")

    def test_tg03_fraction_packet(self) -> None:
        tg03 = derive_tangent_path_oracle()["tg03"]
        self.assertEqual(tg03["u"], "3/100")
        self.assertEqual(tg03["force"], "1/2")
        self.assertEqual(tg03["sigma"], "13/11")
        self.assertEqual(tg03["epsilon_p"], "1/55")
        self.assertEqual(tg03["kappa"], "1/55")
        self.assertEqual(tg03["residual"], "15/22")
        self.assertEqual(tg03["current_tangent"], "100/11")


class TangentPathExecutionContractTests(unittest.TestCase):
    def test_tg01_exact_same_track_parity(self) -> None:
        result = execute_tangent_path_case(ROOT, "L2-TG-01", "TEST-TG01")
        self.assertTrue(result.pass_flag)
        self.assertEqual(
            result.observed_classification,
            "PASS_SAME_TRACK_REPEATABILITY",
        )
        self.assertTrue(result.comparison.packet_semantic_equal)
        self.assertTrue(result.comparison.accepted_fingerprint_equal)
        self.assertTrue(result.comparison.committed_transition_valid)
        self.assertTrue(result.comparison.candidates_unreachable)
        self.assertFalse(result.comparison.committed_state_unchanged)
        self.assertEqual(result.comparison.left_evaluation_count, 3)
        self.assertEqual(result.comparison.right_evaluation_count, 3)

    def test_tg02_accepted_parity_is_separate_from_iteration_count(self) -> None:
        result = execute_tangent_path_case(ROOT, "L2-TG-02", "TEST-TG02")
        self.assertTrue(result.pass_flag)
        self.assertEqual(
            result.observed_classification,
            "PASS_DECLARED_LAGGED_TANGENT_PARITY",
        )
        self.assertTrue(result.comparison.accepted_field_equal)
        self.assertTrue(result.comparison.accepted_fingerprint_equal)
        self.assertTrue(result.comparison.committed_transition_valid)
        self.assertTrue(result.comparison.candidates_unreachable)
        self.assertFalse(result.comparison.committed_state_unchanged)
        self.assertFalse(result.comparison.iteration_count_equal)
        self.assertEqual(result.comparison.left_evaluation_count, 3)
        self.assertEqual(result.comparison.right_evaluation_count, 4)

    def test_tg03_matched_pass_and_mismatch_reject(self) -> None:
        result = execute_tangent_path_case(ROOT, "L2-TG-03", "TEST-TG03")
        self.assertTrue(result.pass_flag)
        self.assertEqual(
            result.observed_classification,
            "REJECT_VERSION_MISMATCH_BEFORE_LIFECYCLE_VERDICT",
        )
        self.assertTrue(result.comparison.matched_version_compatible)
        self.assertFalse(result.comparison.mismatched_version_compatible)
        self.assertEqual(result.comparison.numeric_residual_delta, 0.0)
        self.assertEqual(result.comparison.numeric_tangent_delta, 0.0)
        self.assertTrue(result.comparison.committed_state_unchanged)
        self.assertTrue(result.comparison.committed_transition_valid)
        self.assertEqual(result.event_log[1]["event"], "RejectBeforeCorrection")
        self.assertIsNone(result.event_log[1]["correction"])

    def test_tg03_committed_state_and_output_remain_unreachable(self) -> None:
        freeze, _ = load_frozen_design(ROOT)
        matched, mismatched = build_tg03_packets(freeze)
        for packet in (matched, mismatched):
            self.assertEqual(
                packet.committed_fingerprint_before,
                packet.committed_fingerprint_after,
            )
            self.assertFalse(packet.candidate_reachable_after_reject)
            self.assertFalse(packet.accepted_output_reachable)
            self.assertFalse(packet.correction_applied)
            self.assertTrue(packet.all_values_finite)
        self.assertTrue(validate_operator_versions(matched))
        self.assertFalse(validate_operator_versions(mismatched))

    def test_all_case_values_respect_finite_limit(self) -> None:
        for case_id in AUTHORIZED_CASES:
            result = execute_tangent_path_case(ROOT, case_id, f"FINITE-{case_id}")
            self.assertTrue(result.comparison.all_values_finite)

    def test_unauthorized_case_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            execute_tangent_path_case(ROOT, "L2-TG-99", "TEST-DENY")

    def test_import_has_no_filesystem_or_execution_side_effect(self) -> None:
        before = sorted(
            path.relative_to(ROOT).as_posix()
            for path in ROOT.rglob("*")
            if path.is_file()
        )
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                "import src.l2_d3_tangent_path",
            ],
            cwd=ROOT,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
        after = sorted(
            path.relative_to(ROOT).as_posix()
            for path in ROOT.rglob("*")
            if path.is_file()
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout, "")
        self.assertEqual(completed.stderr, "")
        self.assertEqual(before, after)

    def test_runner_requires_both_authorization_locks(self) -> None:
        runner = ROOT / "run_l2_d3.py"
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        environment.pop("L2_D3_EXECUTION_AUTHORIZED", None)
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "must_not_exist"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(runner),
                    "--case-id",
                    "L2-TG-01",
                    "--run-id",
                    "LOCK-TEST",
                    "--execute-authorized",
                    "--output-root",
                    str(output),
                ],
                cwd=ROOT,
                env=environment,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
