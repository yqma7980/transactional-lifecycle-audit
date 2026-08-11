from __future__ import annotations

import copy
import unittest
from dataclasses import replace
from pathlib import Path

from jss_p5b.adjudication import adjudicate
from jss_p5b.adapters import adapter_for_subject
from jss_p5b.cases import load_case_matrix
from jss_p5b.development_guard import (
    authorize_development,
    select_development_case,
    validate_activation_payload,
)
from jss_p5b.model import ContractError, PrecomparisonRelation, Verdict
from jss_p5b.schema import validate_case_result_payload

from helpers import synthetic_observation


ROOT = Path(__file__).resolve().parents[1]


def activation_payload(cases):
    return {
        "activation_id": "JSS-P5B-DEVELOPMENT-ACTIVATION-1.0",
        "activation_status": "DEVELOPMENT_ACTIVE_NOT_EXECUTED",
        "design_version": "JSS-P5B.0",
        "implementation_version": "JSS-P5B-IMPL-1.0a",
        "development_execution_authorized": True,
        "held_out_access_authorized": False,
        "formal_results_exist": False,
        "development_case_ids": sorted(
            case.case_id for case in cases if case.partition == "DEVELOPMENT"
        ),
        "held_out_case_ids": sorted(
            case.case_id for case in cases if case.partition == "HELD_OUT"
        ),
        "required_cli_lock": "--execute-authorized",
        "required_environment_lock": "JSS_P5B_DEVELOPMENT_AUTHORIZED",
        "required_environment_value": "YES",
        "allowed_run_ids": ["run_1", "run_2"],
        "protected_implementation_files": {},
        "formal_review_freeze_sha256": "0" * 64,
    }


class FormalReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cases = load_case_matrix(ROOT)

    def test_exact_partition_is_sixteen_plus_four(self) -> None:
        development = [case for case in self.cases if case.partition == "DEVELOPMENT"]
        held_out = [case for case in self.cases if case.partition == "HELD_OUT"]
        self.assertEqual(len(development), 16)
        self.assertEqual(len(held_out), 4)
        self.assertEqual({case.target_verdict for case in held_out}, set(Verdict))

    def test_adapter_rejects_relation_disagreement(self) -> None:
        case = next(case for case in self.cases if case.case_id == "P5B-PASS-01")
        raw = synthetic_observation(case)
        bad = replace(raw, precomparison_relation=PrecomparisonRelation.INCOMPATIBLE)
        with self.assertRaises(ContractError):
            adapter_for_subject(case.subject_id).adapt(case, bad, run_id="unit_run_1")

    def test_adapter_rejects_packet_mismatch_contract_drift(self) -> None:
        case = next(case for case in self.cases if case.case_id == "P5B-INVALID-01")
        raw = synthetic_observation(case)
        bad_packet = replace(raw.packet_b, load_hash="LOAD-UNDECLARED")
        bad = replace(raw, packet_b=bad_packet)
        with self.assertRaises(ContractError):
            adapter_for_subject(case.subject_id).adapt(case, bad, run_id="unit_run_1")

    def test_all_development_contract_fixtures_still_adjudicate(self) -> None:
        for case in self.cases:
            if case.partition != "DEVELOPMENT":
                continue
            with self.subTest(case_id=case.case_id):
                request = adapter_for_subject(case.subject_id).adapt(
                    case,
                    synthetic_observation(case),
                    run_id="unit_run_1",
                )
                result = adjudicate(request)
                self.assertEqual(result.verdict, case.target_verdict)
                self.assertTrue(result.pass_flag)
                validate_case_result_payload(result.to_dict())

    def test_execution_error_stage_flags_are_enforced(self) -> None:
        case = next(case for case in self.cases if case.case_id == "P5B-PASS-01")
        request = adapter_for_subject(case.subject_id).adapt(
            case,
            replace(synthetic_observation(case), execution_error="unit_execution_error"),
            run_id="unit_run_1",
        )
        payload = adjudicate(request).to_dict()
        validate_case_result_payload(payload)
        for key, value in (
            ("stage", "ELIGIBILITY"),
            ("applicability_evaluated", True),
        ):
            altered = copy.deepcopy(payload)
            altered[key] = value
            with self.subTest(key=key), self.assertRaises(ContractError):
                validate_case_result_payload(altered)

    def test_pass_and_detect_signal_contracts_are_enforced(self) -> None:
        pass_case = next(case for case in self.cases if case.case_id == "P5B-PASS-01")
        detect_case = next(case for case in self.cases if case.case_id == "P5B-DETECT-01")
        pass_payload = adjudicate(
            adapter_for_subject(pass_case.subject_id).adapt(
                pass_case, synthetic_observation(pass_case), run_id="unit_run_1"
            )
        ).to_dict()
        detect_payload = adjudicate(
            adapter_for_subject(detect_case.subject_id).adapt(
                detect_case, synthetic_observation(detect_case), run_id="unit_run_1"
            )
        ).to_dict()
        pass_payload["active_signals"] = ["operator_replay_drift"]
        detect_payload["active_signals"] = []
        with self.assertRaises(ContractError):
            validate_case_result_payload(pass_payload)
        with self.assertRaises(ContractError):
            validate_case_result_payload(detect_payload)

    def test_development_selector_rejects_held_out_and_unknown(self) -> None:
        selected = select_development_case(self.cases, "P5B-PASS-01")
        self.assertEqual(selected.partition, "DEVELOPMENT")
        for case_id in ("P5B-PASS-05", "P5B-UNKNOWN-01"):
            with self.subTest(case_id=case_id), self.assertRaises(ContractError):
                select_development_case(self.cases, case_id)

    def test_activation_contract_requires_exact_partitions(self) -> None:
        payload = activation_payload(self.cases)
        validate_activation_payload(payload, self.cases)
        payload["development_case_ids"] = payload["development_case_ids"][:-1]
        with self.assertRaises(ContractError):
            validate_activation_payload(payload, self.cases)

    def test_activation_contract_keeps_held_out_locked(self) -> None:
        payload = activation_payload(self.cases)
        payload["held_out_access_authorized"] = True
        with self.assertRaises(ContractError):
            validate_activation_payload(payload, self.cases)

    def test_live_activation_returns_development_path_without_write(self) -> None:
        output = authorize_development(
            ROOT,
            case_id="P5B-PASS-01",
            run_id="run_1",
            cli_authorized=True,
            environment={"JSS_P5B_DEVELOPMENT_AUTHORIZED": "YES"},
        )
        self.assertFalse(output.exists())
        self.assertFalse(output.parent.exists())
        self.assertFalse((ROOT / "results").exists())

    def test_live_activation_blocks_all_held_out_ids_before_write(self) -> None:
        held_out = [case.case_id for case in self.cases if case.partition == "HELD_OUT"]
        self.assertEqual(len(held_out), 4)
        for case_id in held_out:
            with self.subTest(case_id=case_id), self.assertRaises(ContractError):
                authorize_development(
                    ROOT,
                    case_id=case_id,
                    run_id="run_1",
                    cli_authorized=True,
                    environment={"JSS_P5B_DEVELOPMENT_AUTHORIZED": "YES"},
                )
        self.assertFalse((ROOT / "results").exists())

    def test_live_activation_requires_both_locks(self) -> None:
        for cli_authorized, environment in (
            (False, {"JSS_P5B_DEVELOPMENT_AUTHORIZED": "YES"}),
            (True, {}),
        ):
            with self.subTest(cli=cli_authorized), self.assertRaises(ContractError):
                authorize_development(
                    ROOT,
                    case_id="P5B-PASS-01",
                    run_id="run_1",
                    cli_authorized=cli_authorized,
                    environment=environment,
                )
        self.assertFalse((ROOT / "results").exists())


if __name__ == "__main__":
    unittest.main()
