from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "formal" / "bounded_model.py"
SPEC = importlib.util.spec_from_file_location("bounded_model", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class BoundedModelTests(unittest.TestCase):
    def test_guarded_model_excludes_registered_bad_transitions(self) -> None:
        result = MODULE.explore(guarded=True, depth=8)
        self.assertFalse(result["premature_commit_counterexamples"])
        self.assertFalse(result["output_escape_counterexamples"])
        self.assertFalse(result["rollback_noninterference_counterexamples"])

    def test_unguarded_model_contains_counterexamples(self) -> None:
        result = MODULE.explore(guarded=False, depth=8)
        self.assertTrue(result["premature_commit_counterexamples"])
        self.assertTrue(result["output_escape_counterexamples"])


if __name__ == "__main__":
    unittest.main()
