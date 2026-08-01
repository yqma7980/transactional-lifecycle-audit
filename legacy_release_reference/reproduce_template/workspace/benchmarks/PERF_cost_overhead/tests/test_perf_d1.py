from __future__ import annotations

import csv
import hashlib
import math
from pathlib import Path
import subprocess
import sys
import unittest

from benchmarks.L6_external_host.src.l6_state import canonical_json
from benchmarks.PERF_cost_overhead.src.perf_instrumentation import (
    AuditCollector,
    MODE_FLAGS,
)
from benchmarks.PERF_cost_overhead.src.perf_worker import (
    peak_working_set,
    set_and_verify_affinity,
)
from benchmarks.PERF_cost_overhead.src.perf_workloads import execute_family


ROOT = Path(__file__).resolve().parents[1]


class PerfD1Tests(unittest.TestCase):
    def test_case_matrix_is_frozen_45_cell_product(self) -> None:
        with (ROOT / "PERF_D0_case_matrix.csv").open(
            "r", encoding="utf-8", newline=""
        ) as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 45)
        self.assertEqual(len({row["case_id"] for row in rows}), 45)
        self.assertEqual({row["family"] for row in rows}, {"L3", "L4", "L6"})
        self.assertEqual({row["size"] for row in rows}, {"S", "M", "L"})
        self.assertEqual({row["config_id"] for row in rows}, set(MODE_FLAGS))

    def test_mode_lattice_is_cumulative(self) -> None:
        self.assertEqual(
            MODE_FLAGS["C0"],
            {
                "transaction": False,
                "fingerprint": False,
                "event_log": False,
                "full_provenance": False,
            },
        )
        self.assertTrue(MODE_FLAGS["C4"]["transaction"])
        self.assertTrue(MODE_FLAGS["C4"]["fingerprint"])
        self.assertTrue(MODE_FLAGS["C4"]["event_log"])
        self.assertTrue(MODE_FLAGS["C4"]["full_provenance"])

    def _assert_tiny_equivalence(self, row: dict[str, str]) -> None:
        fingerprints = set()
        outputs = []
        for mode in MODE_FLAGS:
            local = dict(row)
            local["config_id"] = mode
            audit = AuditCollector(mode)
            output, counts = execute_family(local, audit)
            audit.finalize(output)
            payload = canonical_json(output).encode("utf-8")
            fingerprints.add(hashlib.sha256(payload).hexdigest())
            outputs.append(output)
            self.assertTrue(all(math.isfinite(float(value)) for value in counts.values()))
        self.assertEqual(len(fingerprints), 1)
        for output in outputs[1:]:
            self.assertEqual(output, outputs[0])

    def test_tiny_l3_output_equivalence(self) -> None:
        self._assert_tiny_equivalence(
            {
                "family": "L3",
                "n_cells": "8",
                "accepted_steps": "4",
                "end_time": "0.02",
                "cfl": "",
                "batch_repeats": "",
            }
        )

    def test_tiny_l4_output_equivalence(self) -> None:
        self._assert_tiny_equivalence(
            {
                "family": "L4",
                "n_cells": "8",
                "accepted_steps": "8",
                "end_time": "0.02",
                "cfl": "0.4",
                "batch_repeats": "",
            }
        )

    def test_tiny_l6_output_equivalence(self) -> None:
        self._assert_tiny_equivalence(
            {
                "family": "L6",
                "n_cells": "",
                "accepted_steps": "",
                "end_time": "",
                "cfl": "",
                "batch_repeats": "1",
            }
        )

    def test_audit_layers_do_not_mutate_output(self) -> None:
        output = {"x": 1.0, "field": [0.0, 0.5, 1.0]}
        original = canonical_json(output)
        for mode in MODE_FLAGS:
            audit = AuditCollector(mode)
            audit.begin_attempt({"accepted_version": 0})
            audit.observe_candidate({"x": 0.25})
            audit.commit({"accepted_version": 1})
            audit.finalize(output)
            self.assertEqual(canonical_json(output), original)

    def test_windows_affinity_and_peak_memory_capability(self) -> None:
        affinity = set_and_verify_affinity(1)
        self.assertEqual(affinity["process_mask"], 1)
        self.assertGreater(peak_working_set(), 0)

    def test_runner_refuses_missing_dual_authorization(self) -> None:
        result_root = ROOT / "results" / "PERF_D1_cost_overhead"
        self.assertFalse(result_root.exists())
        completed = subprocess.run(
            [
                sys.executable,
                str(ROOT / "run_perf_d1.py"),
                "--phase",
                "preflight",
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertFalse(result_root.exists())

    def test_frozen_scientific_inputs_unchanged(self) -> None:
        expected = {
            ROOT.parent / "L3_poroelastic_consolidation" / "src" / "l3_fv.py":
                "5d1e2400eeb524edbff59902ace9569fd3566272ccf48972acc34bd56e213bf7",
            ROOT.parent / "L4_two_phase_displacement" / "src" / "l4_fv.py":
                "fe69f646f3efea9e81d5945e5ddb0a2f5a577c907a36330dd4dd03d1a9259b2e",
            ROOT.parent / "L6_external_host" / "src" / "l6_scipy_adapter.py":
                "c3cfb96ff618c019bb577b631b8b618abb76ece983f8252325ffa6aa7f599055",
        }
        for path, digest in expected.items():
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)


if __name__ == "__main__":
    unittest.main()