from __future__ import annotations

import copy
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

import numpy as np


ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
ORACLE = ROOT / "oracle"
for path in (SRC, ORACLE):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from p4d_fraction_oracle import derive_fraction_packets
from p4d_material import evaluate_material
from p4d_zero_case import classify_native_nonaccepting_candidate, read_c_ledger


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_bridge_result(value):
    result = copy.deepcopy(value)
    result.pop("run_id", None)
    result.pop("snes_handle", None)
    metadata = result.get("bridge_metadata")
    if metadata:
        metadata.pop("handle_integer", None)
        metadata.pop("ledger_path", None)
        metadata.pop("library_path", None)
    candidate = result.get("native_candidate_classification", {}).get("first_unselected_candidate")
    if candidate:
        candidate["solve_id"] = "NORMALIZED"
    return result


class P4d1PreflightTests(unittest.TestCase):
    def test_fraction_packets(self):
        packets = derive_fraction_packets()
        self.assertEqual(str(packets["plastic"]["delta_lambda"]), "1/12")
        self.assertEqual(str(packets["plastic"]["tau"][0]), "7/6")
        self.assertEqual(str(packets["plastic"]["tangent"][0][0]), "5/3")
        self.assertEqual(str(packets["plastic"]["tangent"][1][1]), "35/6")

    def test_trial_does_not_mutate_committed_arrays(self):
        gamma_p = np.zeros(2)
        original = gamma_p.copy()
        packet = evaluate_material(np.array([0.2, 0.0]), gamma_p, 0.0)
        self.assertTrue(np.array_equal(gamma_p, original))
        self.assertFalse(np.shares_memory(gamma_p, packet.candidate.gamma_p))

    def test_observer_no_effect(self):
        off = load_json(ROOT / "runtime_evidence" / "observer_off" / "result.json")
        on = load_json(ROOT / "runtime_evidence" / "observer_on_run_1" / "result.json")
        for field in ("solution_hex", "snes_reason", "iteration_count", "residual_sequence_hex"):
            self.assertEqual(off[field], on[field])

    def test_observer_duplicate(self):
        first = normalize_bridge_result(load_json(ROOT / "runtime_evidence" / "observer_on_run_1" / "result.json"))
        second = normalize_bridge_result(load_json(ROOT / "runtime_evidence" / "observer_on_run_2" / "result.json"))
        self.assertEqual(first, second)

    def test_native_nonaccepting_candidate(self):
        events = read_c_ledger(ROOT / "runtime_evidence" / "observer_on_run_1" / "c_ledger.jsonl")
        classification = classify_native_nonaccepting_candidate(events)
        self.assertGreaterEqual(classification["structured_unselected_candidate_count"], 1)
        self.assertEqual(events[0]["callback_kind"], "ATTACH")
        self.assertFalse(events[0]["postcheck_change_flags"])

    def test_oracle_and_topology_gates(self):
        oracle = load_json(ROOT / "runtime_evidence" / "oracle" / "result.json")
        topology = load_json(ROOT / "runtime_evidence" / "topology" / "result.json")
        self.assertTrue(oracle["oracle_gate_pass"])
        self.assertTrue(topology["topology_gate_pass"])
        self.assertTrue(topology["committed_immutable_after_trial"])

    def test_safe_smoke_ordering_and_versions(self):
        smoke = load_json(ROOT / "runtime_evidence" / "safe_increment" / "result.json")
        events = [event["event"] for event in smoke["event_ledger"]]
        self.assertLess(events.index("AcceptCommit"), events.index("OutputAcceptedState"))
        self.assertTrue(smoke["accepted_output_candidate_matches"])
        self.assertEqual(smoke["operator_version_relation"], "EXACT_CURRENT")
        self.assertTrue(smoke["mechanics_gate_pass"])
        self.assertFalse(smoke["continued_to_next_load"])

    def test_unauthorized_formal_case_rejected_before_write(self):
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory) / "forbidden.json"
            process = subprocess.run(
                [sys.executable, str(ROOT / "run_p4d1_stage.py"), "--preflight-id", "P4D-REF-01",
                 "--mode", "oracle", "--output", str(output)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(process.returncode, 0)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
