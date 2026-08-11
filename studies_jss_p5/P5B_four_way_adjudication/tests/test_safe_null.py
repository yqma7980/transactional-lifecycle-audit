from __future__ import annotations

import unittest

from jss_p5b.adjudication import adjudicate
from jss_p5b.adapters import safe_null_request
from jss_p5b.model import Verdict
from jss_p5b.schema import validate_case_result_payload


class SafeNullTests(unittest.TestCase):
    def test_safe_null_is_exact_and_duplicate_normalized(self) -> None:
        for subject_id in ("JSS-S01", "JSS-S02", "JSS-S03"):
            with self.subTest(subject_id=subject_id):
                left = adjudicate(safe_null_request(subject_id, "preflight_run_1"))
                right = adjudicate(safe_null_request(subject_id, "preflight_run_2"))
                validate_case_result_payload(left.to_dict())
                validate_case_result_payload(right.to_dict())
                self.assertEqual(left.verdict, Verdict.PASS_INVARIANT)
                self.assertTrue(left.pass_flag)
                self.assertEqual(left.mismatch_fields, ())
                self.assertEqual(left.semantic_projection(), right.semantic_projection())
                self.assertEqual(left.semantic_fingerprint, right.semantic_fingerprint)


if __name__ == "__main__":
    unittest.main()

