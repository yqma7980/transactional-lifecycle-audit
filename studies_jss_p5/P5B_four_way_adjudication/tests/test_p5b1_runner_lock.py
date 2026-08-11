from __future__ import annotations

import ast
import unittest
from pathlib import Path

from jss_p5b.cases import load_case_matrix
from jss_p5b.development_guard import authorize_development
from jss_p5b.model import ContractError


ROOT = Path(__file__).resolve().parents[1]


class DevelopmentRunnerLockTests(unittest.TestCase):
    def test_runner_has_main_guard_and_both_authorization_tokens(self) -> None:
        path = ROOT / "run_p5b_development.py"
        source = path.read_text(encoding="utf-8")
        ast.parse(source, filename=str(path))
        self.assertIn('if __name__ == "__main__"', source)
        self.assertIn("--execute-authorized", source)
        self.assertIn("JSS_P5B_DEVELOPMENT_AUTHORIZED", source)

    def test_all_held_out_cases_are_rejected_before_output_creation(self) -> None:
        held_out = [
            case.case_id for case in load_case_matrix(ROOT) if case.partition == "HELD_OUT"
        ]
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
            self.assertFalse((ROOT / "results" / "development" / case_id).exists())


if __name__ == "__main__":
    unittest.main()
