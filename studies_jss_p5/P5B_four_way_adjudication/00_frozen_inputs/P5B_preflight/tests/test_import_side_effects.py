from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ImportSideEffectTests(unittest.TestCase):
    def test_imports_create_no_files(self) -> None:
        modules = (
            "jss_p5b",
            "jss_p5b.adjudication",
            "jss_p5b.adapters",
            "jss_p5b.cases",
            "jss_p5b.runner_guard",
            "jss_p5b.schema",
        )
        statement = ";".join(f"import {module}" for module in modules)
        before = sorted(path.name for path in ROOT.iterdir())
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONPATH"] = str(ROOT / "src")
        completed = subprocess.run(
            [sys.executable, "-c", statement],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        after = sorted(path.name for path in ROOT.iterdir())
        self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
