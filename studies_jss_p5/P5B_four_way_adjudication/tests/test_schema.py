from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from jss_p5b.adjudication import adjudicate
from jss_p5b.adapters import safe_null_request
from jss_p5b.model import ContractError
from jss_p5b.schema import REQUIRED_KEYS, validate_case_result_payload


ROOT = Path(__file__).resolve().parents[1]


class SchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = adjudicate(
            safe_null_request("JSS-S01", "preflight_run_1")
        ).to_dict()

    def test_schema_document_matches_runtime_keys(self) -> None:
        schema = json.loads(
            (ROOT / "schemas" / "p5b_case_result.schema.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(set(schema["required"]), set(REQUIRED_KEYS))
        self.assertFalse(schema["additionalProperties"])
        validate_case_result_payload(self.payload)

    def test_missing_key_is_rejected(self) -> None:
        payload = copy.deepcopy(self.payload)
        payload.pop("stage")
        with self.assertRaises(ContractError):
            validate_case_result_payload(payload)

    def test_extra_key_is_rejected(self) -> None:
        payload = copy.deepcopy(self.payload)
        payload["post_hoc_note"] = "forbidden"
        with self.assertRaises(ContractError):
            validate_case_result_payload(payload)

    def test_invalid_cannot_carry_lifecycle_signal(self) -> None:
        payload = copy.deepcopy(self.payload)
        payload["expected_verdict"] = "INVALID"
        payload["observed_outcome"] = "INVALID"
        payload["four_way_verdict"] = "INVALID"
        payload["stage"] = "ELIGIBILITY"
        payload["lifecycle_evaluated"] = False
        payload["active_signals"] = ["operator_replay_drift"]
        with self.assertRaises(ContractError):
            validate_case_result_payload(payload)


if __name__ == "__main__":
    unittest.main()

