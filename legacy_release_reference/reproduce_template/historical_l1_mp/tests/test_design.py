from __future__ import annotations

from pathlib import Path
import unittest

from src.l1_design_validation import synthetic_valid_summary, validate_design, validate_summary_document


ROOT = Path(__file__).resolve().parents[1]


class FrozenDesignTests(unittest.TestCase):
    def test_design_inputs_and_hashes(self) -> None:
        result = validate_design(ROOT)
        self.assertTrue(result["passed"], result["errors"])
        self.assertEqual(result["case_count"], 20)
        self.assertEqual(result["scenario_variant_count"], 45)
        self.assertEqual(result["mp_case_count"], 12)
        self.assertEqual(result["mp_scenario_variant_count"], 25)
        self.assertEqual(result["ledger_column_count"], 40)

    def test_valid_summary_is_accepted(self) -> None:
        self.assertEqual(validate_summary_document(synthetic_valid_summary()), [])

    def test_invalid_summary_is_rejected(self) -> None:
        invalid = synthetic_valid_summary()
        invalid["case_count"] = 19
        self.assertTrue(validate_summary_document(invalid))

    def test_e1_remains_unauthorized(self) -> None:
        freeze = (ROOT / "L1_MP_execution_freeze.json").read_text(encoding="utf-8")
        self.assertIn('"e1_authorized": false', freeze)
        self.assertFalse((ROOT / "src" / "l1_element.py").exists())
        self.assertFalse((ROOT / "tests" / "test_e1_cases.py").exists())


if __name__ == "__main__":
    unittest.main()

