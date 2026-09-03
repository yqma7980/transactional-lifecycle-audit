from __future__ import annotations

import itertools
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from r3sqlite.adjudicator import adjudicate
from r3sqlite.model import Verdict
from r3sqlite.subject import execute_case

import historical_wal_reproducer


CONFIG = json.loads((ROOT / "config" / "preregistration.json").read_text(encoding="utf-8"))


class AdjudicatorTests(unittest.TestCase):
    def test_four_way_priority_is_total(self) -> None:
        observed = set()
        for coverage, eligible, *signals in itertools.product((False, True), repeat=7):
            verdict, _ = adjudicate(
                capability_complete=coverage,
                eligible=eligible,
                signals=dict(zip(("O1", "O2", "O3", "O4", "O5"), signals, strict=True)),
            )
            observed.add(verdict)
        self.assertEqual(observed, set(Verdict))

    def test_missing_coverage_is_never_invariant(self) -> None:
        verdict, _ = adjudicate(
            capability_complete=False,
            eligible=True,
            signals={"O1": False, "O2": False, "O3": False, "O4": False, "O5": False},
        )
        self.assertEqual(verdict, Verdict.UNSUPPORTED)


class SQLiteSemanticsTests(unittest.TestCase):
    def test_rollback_to_keeps_outer_transaction_open(self) -> None:
        connection = sqlite3.connect(":memory:", isolation_level=None)
        connection.execute("CREATE TABLE t(value INTEGER)")
        connection.execute("BEGIN")
        connection.execute("SAVEPOINT s")
        connection.execute("INSERT INTO t VALUES(1)")
        connection.execute("ROLLBACK TO s")
        self.assertTrue(connection.in_transaction)
        connection.execute("RELEASE s")
        connection.execute("COMMIT")
        self.assertEqual(connection.execute("SELECT count(*) FROM t").fetchone()[0], 0)

    def test_historical_output_parser(self) -> None:
        integrity, count = historical_wal_reproducer._parse(
            "noise\n__R3_RESULT_BEGIN__\nok\n3\n__R3_RESULT_END__\n"
        )
        self.assertEqual((integrity, count), ("ok", 3))

    def test_inner_release_is_undone_by_outer_rollback(self) -> None:
        connection = sqlite3.connect(":memory:", isolation_level=None)
        connection.execute("CREATE TABLE t(value INTEGER)")
        connection.execute("BEGIN")
        connection.execute("SAVEPOINT s")
        connection.execute("INSERT INTO t VALUES(1)")
        connection.execute("RELEASE s")
        connection.execute("ROLLBACK")
        self.assertEqual(connection.execute("SELECT count(*) FROM t").fetchone()[0], 0)


class SubjectTests(unittest.TestCase):
    def test_all_registered_diagnostic_cases(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for spec in CONFIG["cases"]:
                with self.subTest(case_id=spec["case_id"]):
                    result = execute_case(
                        spec,
                        run_id="test-01",
                        mode="diagnostic",
                        output_dir=root / spec["case_id"],
                    )
                    self.assertTrue(result["verdict_match"])

    def test_enforcement_blocks_faults_without_false_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for spec in CONFIG["cases"]:
                if not spec["containment_eligible"]:
                    continue
                with self.subTest(case_id=spec["case_id"]):
                    result = execute_case(
                        spec,
                        run_id="test-01",
                        mode="enforce",
                        output_dir=root / spec["case_id"],
                    )
                    self.assertTrue(result["containment_pass"])
                    if spec["fault"] == "NONE":
                        self.assertEqual(result["blocked_count"], 0)
                    else:
                        self.assertGreater(result["blocked_count"], 0)


if __name__ == "__main__":
    unittest.main()
