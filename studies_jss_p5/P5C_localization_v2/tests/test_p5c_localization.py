from __future__ import annotations

import inspect
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.p5c_localization import (  # noqa: E402
    METHOD_B3,
    METHOD_B6,
    case_by_id,
    execute_case,
    load_cases,
    load_ontology,
    score_b3,
    score_b6,
)


class P5CLocalizationTests(unittest.TestCase):
    def test_frozen_matrix_partition(self) -> None:
        cases = load_cases(ROOT)
        self.assertEqual(len(cases), 12)
        self.assertEqual(sum(row["partition"] == "DEVELOPMENT" for row in cases), 9)
        self.assertEqual(sum(row["partition"] == "HELD_OUT" for row in cases), 3)

    def test_ontology_has_eight_candidates_per_subject(self) -> None:
        rows = load_ontology(ROOT)
        for subject in ("JSS-S01", "JSS-S02", "JSS-S03"):
            ids = [row.candidate_id for row in rows if row.subject_id == subject]
            self.assertEqual(len(ids), 8)
            self.assertEqual(len(set(ids)), 8)

    def test_scorer_signatures_do_not_accept_ground_truth(self) -> None:
        for function in (score_b3, score_b6):
            self.assertNotIn("ground_truth", inspect.signature(function).parameters)

    def test_all_cases_emit_common_complete_universe(self) -> None:
        ontology = load_ontology(ROOT)
        for case in load_cases(ROOT):
            packet = execute_case(ROOT, case["case_id"], "unit")
            result = packet["result"]
            universe = {
                row.candidate_id for row in ontology if row.subject_id == case["subject_id"]
            }
            for key, method in (("b3_ranking", METHOD_B3), ("b6_ranking", METHOD_B6)):
                ranking = result[key]
                self.assertEqual([row["rank"] for row in ranking], list(range(1, 9)))
                self.assertEqual({row["candidate_id"] for row in ranking}, universe)
                self.assertTrue(all(row["method_id"] == method for row in ranking))
            self.assertTrue(result["pass_flag"])

    def test_tie_break_is_candidate_id_ascending(self) -> None:
        packet = execute_case(ROOT, "P5C-L02", "unit")
        b3 = packet["result"]["b3_ranking"]
        equal_score_ids = [
            row["candidate_id"] for row in b3 if row["score"] == b3[0]["score"]
        ]
        self.assertEqual(equal_score_ids, sorted(equal_score_ids))

    def test_ground_truth_is_evaluated_after_rankings(self) -> None:
        packet = execute_case(ROOT, "P5C-L08", "unit")
        result = packet["result"]
        self.assertEqual(result["ground_truth_candidate_ids"], ["S02-C05"])
        self.assertEqual(result["b6_metrics"]["first_ground_truth_rank"], 1)
        self.assertGreaterEqual(result["b3_metrics"]["first_ground_truth_rank"], 1)

    def test_observation_is_run_id_invariant(self) -> None:
        one = execute_case(ROOT, "P5C-L11", "run_1")["result"]
        two = execute_case(ROOT, "P5C-L11", "run_2")["result"]
        self.assertEqual(one["observation_fingerprint"], two["observation_fingerprint"])
        self.assertEqual(one["semantic_fingerprint"], two["semantic_fingerprint"])

    def test_unknown_case_rejected(self) -> None:
        with self.assertRaises(ValueError):
            case_by_id(ROOT, "P5C-UNKNOWN")

    def test_runner_rejects_missing_authorization_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            env = os.environ.copy()
            env.pop("P5C_EXECUTION_AUTHORIZED", None)
            process = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "run_p5c.py"),
                    "--case-id",
                    "P5C-L01",
                    "--run-id",
                    "unauthorized",
                ],
                cwd=temp,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(process.returncode, 0)
            self.assertFalse((ROOT / "results" / "development" / "P5C-L01" / "unauthorized").exists())

    def test_heldout_requires_second_lock(self) -> None:
        env = os.environ.copy()
        env["P5C_EXECUTION_AUTHORIZED"] = "YES"
        env.pop("P5C_HELDOUT_AUTHORIZED", None)
        process = subprocess.run(
            [
                sys.executable,
                str(ROOT / "run_p5c.py"),
                "--case-id",
                "P5C-L04",
                "--run-id",
                "unauthorized",
                "--execute-authorized",
            ],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(process.returncode, 0)
        self.assertFalse((ROOT / "results" / "held_out" / "P5C-L04" / "unauthorized").exists())

    def test_freeze_json_status(self) -> None:
        freeze = json.loads((ROOT / "P5C_implementation_freeze.json").read_text(encoding="utf-8"))
        self.assertEqual(freeze["implementation_status"], "IMPLEMENTED_NOT_EXECUTED")
        self.assertFalse(freeze["ground_truth_visible_to_scorers"])
        self.assertFalse(freeze["abaqus_used"])


if __name__ == "__main__":
    unittest.main()

