from __future__ import annotations

import ast
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

import numpy as np


ROOT = pathlib.Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "oracle"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from p4d_config import CASE_CONTRACTS, FORMAL_CASE_IDS, LOAD_PATH
from p4d_fraction_oracle import derive_fraction_packets
from p4d_io import AcceptedOutputStore, checkpoint_identity, read_checkpoint, write_checkpoint
from p4d_material import evaluate_material
from p4d_oracle_case import execute_constitutive_oracle
from p4d_state import (
    CommittedState,
    OperatorVersionPacket,
    PersistentState,
    initial_committed_state,
    validate_operator_versions,
)
from p4d_version_guard import execute_version_guard_case


class DummyMetrics:
    residual_norm = 0.0
    top_reaction = 1.0
    bottom_reaction = -1.0
    maximum_alpha = 0.0
    plastic_point_count = 0


class P4d2ContractTests(unittest.TestCase):
    def test_frozen_case_set_and_load_path(self):
        self.assertEqual(tuple(CASE_CONTRACTS), FORMAL_CASE_IDS)
        self.assertEqual(len(FORMAL_CASE_IDS), 9)
        self.assertEqual(LOAD_PATH, (0.0, 0.04, 0.08, 0.10, 0.12, 0.16, 0.20, 0.14, 0.08, 0.16, 0.20))

    def test_material_oracle_and_pure_candidate(self):
        committed = np.zeros(2)
        packet = evaluate_material(np.array([0.2, 0.0]), committed, 0.0)
        self.assertTrue(np.array_equal(committed, np.zeros(2)))
        self.assertFalse(np.shares_memory(committed, packet.candidate.gamma_p))
        result = execute_constitutive_oracle(derive_fraction_packets())
        self.assertTrue(result["pass_flag"])

    def test_committed_arrays_are_immutable(self):
        state = initial_committed_state()
        with self.assertRaises(ValueError):
            state.alpha[0, 0] = 1.0

    def test_declared_and_undeclared_version_relations(self):
        exact = validate_operator_versions(OperatorVersionPacket("R", "J", "EXACT_CURRENT", 2, 2))
        lag = validate_operator_versions(OperatorVersionPacket("R", "J", "DECLARED_ACCEPTED_STATE_LAG", 3, 2))
        bad = validate_operator_versions(OperatorVersionPacket("R", "J", "UNDECLARED_MISMATCH", 3, 2))
        self.assertTrue(exact.compatible)
        self.assertTrue(lag.compatible)
        self.assertFalse(bad.compatible)
        self.assertTrue(bad.rejected_before_correction)
        self.assertTrue(execute_version_guard_case()["pass_flag"])

    def test_output_provenance_positive_and_negative_paths(self):
        store = AcceptedOutputStore()
        state = initial_committed_state()
        store.append_after_commit(
            state=state,
            candidate_id="accepted-candidate",
            metrics=DummyMetrics(),
            mesh_hashes={"material": "m", "mesh": "x"},
            relation="EXACT_CURRENT",
        )
        self.assertFalse(store.rejected_candidate_reachable())
        store.inject_rejected_candidate(candidate_id="failed-candidate", source_load=0.08, target_load=0.20)
        self.assertTrue(store.rejected_candidate_reachable())

    def test_checkpoint_roundtrip_without_pickle(self):
        state = CommittedState(
            primary=np.arange(25, dtype=np.float64),
            gamma_p=np.zeros((32, 3, 2)),
            alpha=np.zeros((32, 3)),
            accepted_index=4,
            accepted_load=0.12,
            accepted_version=4,
        )
        hashes = {
            "coordinates": "c",
            "connectivity": "k",
            "boundary_dof_order": "b",
            "quadrature_rule": "q",
            "material": "m",
        }
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "checkpoint"
            write_checkpoint(path, state, hashes, "environment")
            loaded, manifest = read_checkpoint(path, hashes, "environment")
            self.assertEqual(loaded.full_hash, state.full_hash)
            self.assertNotIn("pickle", json.dumps(manifest).lower())

    def test_formal_runner_denies_before_write(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory) / "results"
            environment = dict(os.environ)
            environment.pop("P4D2_EXECUTION_AUTHORIZED", None)
            process = subprocess.run(
                [sys.executable, str(ROOT / "run_p4d2.py"), "--case-id", "P4D-REF-01", "--run-id", "run_1", "--results-root", str(root)],
                text=True,
                capture_output=True,
                env=environment,
                check=False,
            )
            self.assertNotEqual(process.returncode, 0)
            self.assertFalse(root.exists())

    def test_preflight_runner_rejects_formal_id_before_write(self):
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory) / "forbidden.json"
            process = subprocess.run(
                [sys.executable, str(ROOT / "run_p4d2_preflight.py"), "--preflight-id", "P4D-SAFE-DIR-01", "--output", str(output)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(process.returncode, 0)
            self.assertFalse(output.exists())

    def test_no_commit_call_inside_assembly_callbacks(self):
        tree = ast.parse((ROOT / "src" / "p4d_host.py").read_text(encoding="utf-8"))
        functions = {node.name: node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
        for name in ("_assemble_residual", "_assemble_jacobian", "_prepare_packet"):
            calls = [node for node in ast.walk(functions[name]) if isinstance(node, ast.Call)]
            self.assertFalse(any(isinstance(call.func, ast.Attribute) and call.func.attr == "commit" for call in calls))

    def test_c_observer_postcheck_is_read_only(self):
        source = (ROOT / "src" / "p4d_observer_bridge.c").read_text(encoding="utf-8")
        self.assertIn("*changed_direction = PETSC_FALSE", source)
        self.assertIn("*changed_work = PETSC_FALSE", source)


if __name__ == "__main__":
    unittest.main()
