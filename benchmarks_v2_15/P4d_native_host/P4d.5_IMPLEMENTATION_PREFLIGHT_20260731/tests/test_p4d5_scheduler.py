from __future__ import annotations

import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from p4d5_protocol import EXPECTED_VERDICTS
from p4d5_scheduler import (
    FAIL,
    INCOMPLETE,
    NOT_SUPPORTED,
    PASS,
    READY,
    SKIPPED_DEPENDENCY,
    WAITING,
    aggregate_boundary,
    classify_case_pair,
    schedule_state,
)


def result(case_id, run_id, *, passed=True, verdict=None, extra=None):
    payload = {
        "case_id": case_id,
        "run_id": run_id,
        "pass_flag": passed,
        "primary_verdict": verdict or EXPECTED_VERDICTS[case_id],
    }
    if extra:
        payload.update(extra)
    return payload


class SchedulerTests(unittest.TestCase):
    def test_initial_schedule_has_three_independent_cases(self):
        state = schedule_state({})
        self.assertEqual(
            [case for case, value in state.items() if value == READY],
            ["P4D-SAFE-RT-01", "P4D-SAFE-RS-01", "P4D-VER-01"],
        )
        self.assertEqual(state["P4D-NC-CACHE-01"], WAITING)
        self.assertEqual(state["P4D-NC-OUTPUT-01"], WAITING)

    def test_pair_requires_exactly_two_fresh_runs(self):
        case = "P4D-SAFE-RT-01"
        observed = classify_case_pair(case, [result(case, "run_1")])
        self.assertEqual(observed.classification, INCOMPLETE)
        self.assertIsNone(observed.normalized_results_equal)
        duplicate_ids = [
            result(case, "run_1"),
            result(case, "run_1"),
        ]
        self.assertEqual(
            classify_case_pair(case, duplicate_ids).classification,
            INCOMPLETE,
        )

    def test_retry_pass_releases_two_dependents(self):
        state = schedule_state({"P4D-SAFE-RT-01": PASS})
        self.assertEqual(state["P4D-NC-CACHE-01"], READY)
        self.assertEqual(state["P4D-NC-OUTPUT-01"], READY)

    def test_retry_failure_skips_only_retry_dependents(self):
        state = schedule_state({"P4D-SAFE-RT-01": FAIL})
        self.assertEqual(state["P4D-NC-CACHE-01"], SKIPPED_DEPENDENCY)
        self.assertEqual(state["P4D-NC-OUTPUT-01"], SKIPPED_DEPENDENCY)
        self.assertEqual(state["P4D-SAFE-RS-01"], READY)
        self.assertEqual(state["P4D-VER-01"], READY)

    def test_not_supported_is_preserved(self):
        case = "P4D-SAFE-RT-01"
        runs = [
            result(
                case,
                "run_1",
                passed=False,
                verdict="P4D-SAFE-RT-01_CONTRACT_FAIL",
                extra={
                    "prerequisite_status":
                    "NOT_SUPPORTED_FORCED_RETRY_TRIGGER"
                },
            ),
            result(
                case,
                "run_2",
                passed=False,
                verdict="P4D-SAFE-RT-01_CONTRACT_FAIL",
                extra={
                    "prerequisite_status":
                    "NOT_SUPPORTED_FORCED_RETRY_TRIGGER"
                },
            ),
        ]
        observed = classify_case_pair(case, runs)
        self.assertEqual(observed.classification, NOT_SUPPORTED)
        self.assertTrue(observed.normalized_results_equal)

    def test_expected_pair_pass_and_verdict_mismatch_fail(self):
        case = "P4D-VER-01"
        passed = classify_case_pair(
            case,
            [result(case, "run_1"), result(case, "run_2")],
        )
        self.assertEqual(passed.classification, PASS)
        self.assertTrue(passed.normalized_results_equal)
        integer_flags = [
            result(case, "run_1", passed=1),
            result(case, "run_2", passed=1),
        ]
        self.assertEqual(
            classify_case_pair(case, integer_flags).classification,
            PASS,
        )
        bad = [
            result(case, "run_1"),
            result(case, "run_2", verdict="WRONG"),
        ]
        self.assertEqual(classify_case_pair(case, bad).classification, FAIL)

    def test_duplicate_scientific_mismatch_fails_pair(self):
        case = "P4D-SAFE-RS-01"
        runs = [
            result(case, "run_1", extra={"final_state_hash": "A"}),
            result(case, "run_2", extra={"final_state_hash": "B"}),
        ]
        observed = classify_case_pair(case, runs)
        self.assertEqual(observed.classification, FAIL)
        self.assertFalse(observed.normalized_results_equal)

    def test_aggregate_never_claims_observed_p4d_before_file_qa(self):
        statuses = {case: PASS for case in EXPECTED_VERDICTS}
        self.assertEqual(
            aggregate_boundary(statuses),
            "P4D5_PAIR_CONTRACTS_PASS_PENDING_FULL_FILE_DUPLICATE_QA",
        )


if __name__ == "__main__":
    unittest.main()
