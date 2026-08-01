
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class AuthorizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runner = load("run_p4d5_guard_test", ROOT / "run_p4d5.py")
        cls.matrix = load("run_p4d5_matrix_guard_test", ROOT / "run_p4d5_branch_matrix.py")

    def test_case_runner_missing_environment_lock_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "must_not_exist"
            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaises(SystemExit):
                    self.runner.main(["--case-id", "P4D-SAFE-RT-01", "--run-id", "run_1", "--results-root", str(candidate), "--dependency-root", str(candidate), "--execute-authorized"])
            self.assertFalse(candidate.exists())

    def test_case_runner_missing_cli_lock_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "must_not_exist"
            with patch.dict(os.environ, {"P4D5_EXECUTION_AUTHORIZED": "YES"}, clear=True):
                with self.assertRaises(SystemExit):
                    self.runner.main(["--case-id", "P4D-SAFE-RT-01", "--run-id", "run_1", "--results-root", str(candidate), "--dependency-root", str(candidate)])
            self.assertFalse(candidate.exists())

    def test_unknown_case_rejected_before_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "must_not_exist"
            with patch.dict(os.environ, {"P4D5_EXECUTION_AUTHORIZED": "YES"}, clear=True):
                with self.assertRaises(SystemExit):
                    self.runner.main(["--case-id", "P4D-SAFE-LS-01", "--run-id", "run_1", "--results-root", str(candidate), "--dependency-root", str(candidate), "--execute-authorized"])
            self.assertFalse(candidate.exists())

    def test_matrix_missing_lock_writes_no_results_or_logs(self):
        results = ROOT / "results"
        logs = ROOT / "formal_execution_logs"
        before = (results.exists(), logs.exists())
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(SystemExit):
                self.matrix.main(["--execution-tag", "P4d5_branch_resumption_guard_test", "--execute-authorized"])
        self.assertEqual((results.exists(), logs.exists()), before)

    def test_import_has_no_results_side_effect(self):
        self.assertFalse((ROOT / "results").exists())
        self.assertFalse((ROOT / "formal_execution_logs").exists())


if __name__ == "__main__":
    unittest.main()
