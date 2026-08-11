from __future__ import annotations

import unittest
from pathlib import Path

from jss_p5b.model import ContractError
from jss_p5b.runner_guard import authorize_preflight, validate_protected_inputs


ROOT = Path(__file__).resolve().parents[1]


class RunnerGuardTests(unittest.TestCase):
    def test_protected_hashes_match(self) -> None:
        observed = validate_protected_inputs(ROOT)
        self.assertEqual(len(observed), 7)

    def test_formal_case_is_rejected_before_write(self) -> None:
        target = ROOT / "qa" / "safe_null_runtime"
        self.assertFalse(target.exists())
        with self.assertRaises(ContractError):
            authorize_preflight(
                ROOT,
                preflight_id="P5B-PASS-01",
                run_id="preflight_run_1",
                cli_authorized=True,
                environment={"JSS_P5B_PREFLIGHT_AUTHORIZED": "YES"},
            )
        self.assertFalse(target.exists())

    def test_missing_cli_lock_is_rejected(self) -> None:
        with self.assertRaises(ContractError):
            authorize_preflight(
                ROOT,
                preflight_id="P5B-PREFLIGHT-SAFE-NULL-S01",
                run_id="preflight_run_1",
                cli_authorized=False,
                environment={"JSS_P5B_PREFLIGHT_AUTHORIZED": "YES"},
            )

    def test_missing_environment_lock_is_rejected(self) -> None:
        with self.assertRaises(ContractError):
            authorize_preflight(
                ROOT,
                preflight_id="P5B-PREFLIGHT-SAFE-NULL-S01",
                run_id="preflight_run_1",
                cli_authorized=True,
                environment={},
            )

    def test_invalid_run_id_is_rejected(self) -> None:
        with self.assertRaises(ContractError):
            authorize_preflight(
                ROOT,
                preflight_id="P5B-PREFLIGHT-SAFE-NULL-S01",
                run_id="run_1",
                cli_authorized=True,
                environment={"JSS_P5B_PREFLIGHT_AUTHORIZED": "YES"},
            )

    def test_valid_dual_lock_returns_path_without_creating_it(self) -> None:
        output = authorize_preflight(
            ROOT,
            preflight_id="P5B-PREFLIGHT-SAFE-NULL-S01",
            run_id="preflight_run_1",
            cli_authorized=True,
            environment={"JSS_P5B_PREFLIGHT_AUTHORIZED": "YES"},
        )
        self.assertTrue(str(output).endswith("case_result.json"))
        self.assertFalse(output.exists())
        self.assertFalse(output.parent.exists())

    def test_missing_protected_root_is_rejected(self) -> None:
        missing_root = ROOT / "__definitely_missing_protected_root__"
        self.assertFalse(missing_root.exists())
        with self.assertRaises(ContractError):
            validate_protected_inputs(missing_root)


if __name__ == "__main__":
    unittest.main()
