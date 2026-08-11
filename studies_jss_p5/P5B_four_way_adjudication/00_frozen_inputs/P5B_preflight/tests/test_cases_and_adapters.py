from __future__ import annotations

import unittest
from pathlib import Path

from jss_p5b.adjudication import adjudicate
from jss_p5b.adapters import (
    MECHANISM_REQUIREMENTS,
    SUBJECT_CAPABILITIES,
    adapter_for_subject,
)
from jss_p5b.canonical import canonical_sha256
from jss_p5b.cases import load_case_matrix
from jss_p5b.model import Verdict

from helpers import synthetic_observation


ROOT = Path(__file__).resolve().parents[1]


class CaseAndAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cases = load_case_matrix(ROOT)

    def test_frozen_matrix_has_balanced_four_way_allocation(self) -> None:
        self.assertEqual(len(self.cases), 20)
        for verdict in Verdict:
            self.assertEqual(
                sum(case.target_verdict is verdict for case in self.cases),
                5,
            )
            self.assertEqual(
                sum(
                    case.target_verdict is verdict and case.partition == "HELD_OUT"
                    for case in self.cases
                ),
                1,
            )

    def test_formal_execution_remains_unauthorized(self) -> None:
        self.assertTrue(all(not case.execution_authorized for case in self.cases))

    def test_all_frozen_mechanisms_have_adapter_requirements(self) -> None:
        mechanisms = {case.fault_or_control for case in self.cases}
        self.assertEqual(mechanisms, set(MECHANISM_REQUIREMENTS))
        self.assertEqual(set(SUBJECT_CAPABILITIES), {"JSS-S01", "JSS-S02", "JSS-S03"})

    def test_development_adapters_reproduce_frozen_contract(self) -> None:
        development = [case for case in self.cases if case.partition == "DEVELOPMENT"]
        self.assertEqual(len(development), 16)
        for case in development:
            with self.subTest(case_id=case.case_id):
                raw = synthetic_observation(case)
                before = canonical_sha256(raw)
                request = adapter_for_subject(case.subject_id).adapt(
                    case,
                    raw,
                    run_id="unit_run_1",
                )
                result = adjudicate(request)
                self.assertEqual(result.verdict, case.target_verdict)
                self.assertTrue(result.pass_flag)
                self.assertEqual(before, canonical_sha256(raw))

    def test_not_supported_development_cases_name_missing_evidence(self) -> None:
        cases = [
            case
            for case in self.cases
            if case.partition == "DEVELOPMENT"
            and case.target_verdict is Verdict.NOT_SUPPORTED
        ]
        self.assertEqual(len(cases), 4)
        for case in cases:
            raw = synthetic_observation(case)
            result = adjudicate(
                adapter_for_subject(case.subject_id).adapt(
                    case,
                    raw,
                    run_id="unit_run_1",
                )
            )
            self.assertFalse(result.capability.observable)
            self.assertTrue(
                result.capability.missing_fields or result.capability.missing_events
            )
            self.assertFalse(result.lifecycle_evaluated)


if __name__ == "__main__":
    unittest.main()

