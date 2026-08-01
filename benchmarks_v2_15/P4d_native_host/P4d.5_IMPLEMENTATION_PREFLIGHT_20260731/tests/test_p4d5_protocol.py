
from __future__ import annotations

import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from p4d5_protocol import CASE_ORDER, load_case_contracts, verify_inherited_prerequisites, verify_protected_inputs


class ProtocolTests(unittest.TestCase):
    def test_protected_inputs_and_inherited_evidence(self):
        observed = verify_protected_inputs()
        self.assertEqual(len(observed), 31)
        self.assertEqual(
            verify_inherited_prerequisites(),
            {"P4D-REF-01": "PASS_TWO_FRESH_PROCESS", "P4D-CONST-01": "PASS_TWO_FRESH_PROCESS", "P4D-SAFE-DIR-01": "PASS_TWO_FRESH_PROCESS"},
        )

    def test_five_frozen_contracts(self):
        contracts = load_case_contracts()
        self.assertEqual(tuple(item.case_id for item in contracts), CASE_ORDER)
        self.assertEqual(len({item.case_id for item in contracts}), 5)
        self.assertTrue(all(item.formal_repetitions == 2 for item in contracts))


if __name__ == "__main__":
    unittest.main()
