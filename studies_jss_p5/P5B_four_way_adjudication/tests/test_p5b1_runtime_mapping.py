from __future__ import annotations

import json
import unittest
from pathlib import Path

from jss_p5b.cases import load_case_matrix
from jss_p5b.runtime_mapping import load_runtime_mapping


ROOT = Path(__file__).resolve().parents[1]


class RuntimeMappingTests(unittest.TestCase):
    def test_mapping_is_exactly_the_development_partition(self) -> None:
        cases = load_case_matrix(ROOT)
        expected = {case.case_id for case in cases if case.partition == "DEVELOPMENT"}
        mapping = load_runtime_mapping(ROOT)
        self.assertEqual(set(mapping), expected)
        self.assertEqual(len(mapping), 16)
        self.assertFalse(any(case_id.endswith("-05") for case_id in mapping))

    def test_runtime_freeze_keeps_held_out_sealed(self) -> None:
        payload = json.loads(
            (ROOT / "P5B1_EXECUTION_ADAPTER_FREEZE.json").read_text(encoding="utf-8")
        )
        self.assertEqual(payload["development_case_count"], 16)
        self.assertTrue(payload["development_execution_authorized"])
        self.assertFalse(payload["held_out_access_authorized"])
        self.assertEqual(payload["fresh_process_repetitions_per_case"], 2)

    def test_mapping_rejects_nonexistent_root(self) -> None:
        with self.assertRaises(FileNotFoundError):
            load_runtime_mapping(ROOT / "__missing__")


if __name__ == "__main__":
    unittest.main()
