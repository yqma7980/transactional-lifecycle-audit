from __future__ import annotations

import unittest
from pathlib import Path

from jss_p5b.adjudication import adjudicate
from jss_p5b.adapters import adapter_for_subject
from jss_p5b.cases import load_case_matrix
from jss_p5b.runtime_local import execute_local_runtime
from jss_p5b.runtime_mapping import load_runtime_mapping
from jss_p5b.runtime_schema import validate_runtime_observation_payload


ROOT = Path(__file__).resolve().parents[1]


class LocalRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cases = {
            case.case_id: case
            for case in load_case_matrix(ROOT)
            if case.partition == "DEVELOPMENT" and case.subject_id != "JSS-S01"
        }
        cls.mapping = load_runtime_mapping(ROOT)

    def test_all_twelve_local_cases_match_the_frozen_verdict(self) -> None:
        self.assertEqual(len(self.cases), 12)
        for case_id, case in self.cases.items():
            with self.subTest(case_id=case_id):
                mapping = self.mapping[case_id]
                record = execute_local_runtime(case, "run_1", mapping.runtime_mode)
                validate_runtime_observation_payload(record.to_dict())
                self.assertEqual(record.raw.evidence_tokens, mapping.evidence_tokens)
                self.assertEqual(
                    record.raw.lifecycle_signals.active_names,
                    mapping.lifecycle_signals,
                )
                self.assertEqual(
                    record.raw.packet_a.differing_fields(record.raw.packet_b),
                    mapping.expected_packet_mismatch,
                )
                result = adjudicate(
                    adapter_for_subject(case.subject_id).adapt(
                        case, record.raw, run_id="run_1"
                    )
                )
                self.assertEqual(result.verdict, case.target_verdict)
                self.assertTrue(result.pass_flag)

    def test_local_duplicate_semantics_ignore_only_run_identity(self) -> None:
        for case_id, case in self.cases.items():
            with self.subTest(case_id=case_id):
                mapping = self.mapping[case_id]
                left = execute_local_runtime(case, "run_1", mapping.runtime_mode)
                right = execute_local_runtime(case, "run_2", mapping.runtime_mode)
                self.assertEqual(left.semantic_projection(), right.semantic_projection())
                self.assertEqual(left.semantic_fingerprint, right.semantic_fingerprint)


if __name__ == "__main__":
    unittest.main()
