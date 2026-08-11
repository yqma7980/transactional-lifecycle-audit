from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path

from jss_p5b.cases import load_case_matrix
from jss_p5b.heldout_guard import authorize_heldout
from jss_p5b.heldout_mapping import load_heldout_mapping
from jss_p5b.model import ContractError


ROOT = Path(__file__).resolve().parents[1]
HELD_OUT = (
    "P5B-DETECT-05",
    "P5B-INVALID-05",
    "P5B-NS-05",
    "P5B-PASS-05",
)


class HeldoutContractTests(unittest.TestCase):
    def test_authorization_binds_exactly_four_cases(self) -> None:
        payload = json.loads(
            (ROOT / "P5B3_HELDOUT_EXECUTION_AUTHORIZATION.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertTrue(payload["held_out_execution_authorized"])
        self.assertEqual(tuple(payload["authorized_case_ids"]), HELD_OUT)
        self.assertEqual(payload["allowed_run_ids"], ["run_1", "run_2"])
        self.assertTrue(payload["no_replacement"])
        self.assertTrue(payload["no_reseeding"])
        self.assertTrue(payload["no_threshold_change"])
        self.assertTrue(payload["no_tuning"])

    def test_mapping_matches_frozen_heldout_partition(self) -> None:
        cases = load_case_matrix(ROOT)
        frozen = tuple(sorted(c.case_id for c in cases if c.partition == "HELD_OUT"))
        mappings = load_heldout_mapping(ROOT)
        self.assertEqual(frozen, HELD_OUT)
        self.assertEqual(tuple(sorted(mappings)), HELD_OUT)
        self.assertEqual(
            mappings["P5B-PASS-05"].evidence_tokens,
            ("COMMIT_REACHABILITY", "OUTPUT_CANDIDATE"),
        )
        self.assertEqual(
            mappings["P5B-DETECT-05"].lifecycle_signals,
            ("output_provenance_violation",),
        )
        self.assertEqual(
            mappings["P5B-INVALID-05"].expected_packet_mismatch,
            ("environment_hash",),
        )
        self.assertEqual(mappings["P5B-NS-05"].evidence_tokens, ())

    def test_missing_cli_lock_rejects_without_write(self) -> None:
        target = ROOT / "results" / "heldout" / "P5B-PASS-05" / "run_1"
        self.assertFalse(target.exists())
        with self.assertRaises(ContractError):
            authorize_heldout(
                ROOT,
                case_id="P5B-PASS-05",
                run_id="run_1",
                cli_authorized=False,
                environment={"JSS_P5B_HELDOUT_AUTHORIZED": "YES"},
            )
        self.assertFalse(target.exists())

    def test_missing_environment_lock_rejects_without_write(self) -> None:
        target = ROOT / "results" / "heldout" / "P5B-PASS-05" / "run_1"
        self.assertFalse(target.exists())
        with self.assertRaises(ContractError):
            authorize_heldout(
                ROOT,
                case_id="P5B-PASS-05",
                run_id="run_1",
                cli_authorized=True,
                environment={},
            )
        self.assertFalse(target.exists())

    def test_development_case_is_rejected(self) -> None:
        with self.assertRaises(ContractError):
            authorize_heldout(
                ROOT,
                case_id="P5B-PASS-01",
                run_id="run_1",
                cli_authorized=True,
                environment={"JSS_P5B_HELDOUT_AUTHORIZED": "YES"},
            )

    def test_invalid_run_id_is_rejected(self) -> None:
        with self.assertRaises(ContractError):
            authorize_heldout(
                ROOT,
                case_id="P5B-PASS-05",
                run_id="run_3",
                cli_authorized=True,
                environment={"JSS_P5B_HELDOUT_AUTHORIZED": "YES"},
            )

    def test_valid_dual_lock_returns_path_without_creating_it(self) -> None:
        for case_id in HELD_OUT:
            with self.subTest(case_id=case_id):
                result = authorize_heldout(
                    ROOT,
                    case_id=case_id,
                    run_id="run_1",
                    cli_authorized=True,
                    environment={"JSS_P5B_HELDOUT_AUTHORIZED": "YES"},
                )
                self.assertTrue(str(result).endswith("case_result.json"))
                self.assertFalse(result.exists())
                self.assertFalse(result.parent.exists())

    def test_runner_contract_is_static_and_double_locked(self) -> None:
        path = ROOT / "run_p5b_heldout.py"
        source = path.read_text(encoding="utf-8")
        ast.parse(source, filename=str(path))
        self.assertIn('if __name__ == "__main__"', source)
        self.assertIn("--execute-authorized", source)
        self.assertIn("JSS_P5B_HELDOUT_AUTHORIZED=YES", source)
        self.assertIn("--pull=never", source)
        self.assertIn("--network=none", source)
        self.assertIn("1bb0d528457c78db65ba5445421abe37d", source)

    def test_new_modules_parse_without_import_execution(self) -> None:
        for relative in (
            "src/jss_p5b/heldout_guard.py",
            "src/jss_p5b/heldout_mapping.py",
            "src/jss_p5b/heldout_runtime.py",
            "src/jss_p5b/heldout_executor.py",
            "run_p5b_heldout.py",
        ):
            with self.subTest(relative=relative):
                path = ROOT / relative
                ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


if __name__ == "__main__":
    unittest.main()
