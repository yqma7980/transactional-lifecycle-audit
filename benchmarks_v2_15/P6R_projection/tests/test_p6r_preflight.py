from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from p6r_contracts import AuthorizationError, ContractError, METHOD_IDS, require_descendant, require_execution_authorized
from p6r_detectors import detect_projection
from p6r_loader import freeze_recursive
from p6r_projection import build_method_projection


def row(**kwargs):
    return MappingProxyType({key: str(value) if value is not None else "" for key, value in kwargs.items()})


def bundle(kind="safe"):
    metrics = {key: 0.0 for key in ("M_ALPHA", "M_GP", "M_J", "M_OUTPUT_R", "M_OUTPUT_W", "M_REACTION", "M_X")}
    metrics["M_R"] = 2.7755575615628914e-17
    events = [row(event_kind="FormTangent", event_ordinal=1, history_id="H_REFERENCE", residual_version="P4D-R-1.0", tangent_version="P4D-J-1.0", operator_version_relation="EXACT_CURRENT", reachable_from_accepted_output=False)]
    if kind in {"m5", "f05", "f07"}:
        metrics["M_R"] = 1.4551915228366852e-11
    if kind == "f05":
        events.append(row(event_kind="SeededLifecycleMutation", event_ordinal=2, history_id="H_PERTURBED", candidate_id="candidate-rejected", persistent_before_hash="before", persistent_after_hash="after", reachable_from_accepted_output=True, field_binding="feedback_mirror_E@output_read", physical_delta=1e-10))
    if kind == "f07":
        events.extend([
            row(event_kind="ExtraNonacceptingResidual", event_ordinal=2, history_id="H_PERTURBED", candidate_id="candidate-rejected", reachable_from_accepted_output=False),
            row(event_kind="SeededLifecycleMutation", event_ordinal=3, history_id="H_PERTURBED", candidate_id="candidate-rejected", persistent_before_hash="before", persistent_after_hash="after", reachable_from_accepted_output=False, field_binding="callback_bias_F@extra_nonaccepting_residual", physical_delta=1e-10),
        ])
    result = MappingProxyType({"case_id": "LEAK-ME-NOT", "family_id": "LEAK-ME-NOT", "expected_lifecycle_verdict": "LEAK-ME-NOT", "all_values_finite": 1, "conventional_quiet": 1, "endpoint_quiet": 1, "accepted_output_length_equal": 1, "metric_distances": MappingProxyType(metrics)})
    accepted = (row(history_role="safe", family_id="LEAK-ME-NOT", accepted_index=1, accepted_load_factor=0.04, accepted_version=1, candidate_id="secret", source_event="AcceptCommit", top_reaction=0.5, bottom_reaction=-0.5, residual_norm=1e-15),)
    return SimpleNamespace(case_result=result, accepted_output=accepted, event_ledger=tuple(events))


class AuthorizationTests(unittest.TestCase):
    def test_double_lock_missing_both(self):
        with self.assertRaises(AuthorizationError): require_execution_authorized(False, {})

    def test_double_lock_missing_cli(self):
        with self.assertRaises(AuthorizationError): require_execution_authorized(False, {"P6R_EXECUTION_AUTHORIZED": "YES"})

    def test_double_lock_missing_env(self):
        with self.assertRaises(AuthorizationError): require_execution_authorized(True, {})

    def test_double_lock_accepts_both(self):
        require_execution_authorized(True, {"P6R_EXECUTION_AUTHORIZED": "YES"})

    def test_results_path_cannot_escape(self):
        with self.assertRaises(ContractError): require_descendant(ROOT.parent, ROOT / "results")

    def test_runner_checks_lock_before_execution(self):
        tree = ast.parse((ROOT / "run_p6r.py").read_text(encoding="utf-8"))
        main = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main")
        calls = [node.func.id for node in ast.walk(main) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)]
        self.assertLess(calls.index("require_execution_authorized"), calls.index("execute_one_projection_process"))


class ProjectionIsolationTests(unittest.TestCase):
    def test_all_six_methods_exist(self): self.assertEqual(len(METHOD_IDS), 6)

    def test_m2_m3_do_not_read_bundle(self):
        class Bomb:
            def __getattr__(self, name): raise AssertionError(name)
        for method_id in ("M2_CKPT", "M3_STATE"):
            self.assertFalse(build_method_projection(method_id, Bomb()).applicable)

    def test_forbidden_ground_truth_is_removed(self):
        for method_id in METHOD_IDS:
            text = repr(build_method_projection(method_id, bundle("f05")).payload)
            self.assertNotIn("LEAK-ME-NOT", text)
            self.assertNotIn("expected_lifecycle_verdict", text)
            self.assertNotIn("family_id", text)

    def test_m1_excludes_event_and_candidate_fields(self):
        text = repr(build_method_projection("M1_FINAL", bundle()).payload)
        self.assertNotIn("event_kind", text); self.assertNotIn("candidate_id", text); self.assertNotIn("persistent", text)

    def test_m4_excludes_numeric_replay_and_callback_history(self):
        text = repr(build_method_projection("M4_OPERATOR", bundle("f05")).payload)
        self.assertNotIn("metric", text); self.assertNotIn("event_kind", text); self.assertNotIn("physical_delta", text)

    def test_m5_excludes_owner_event_and_source_fields(self):
        text = repr(build_method_projection("M5_META", bundle("f05")).payload)
        self.assertNotIn("field_binding", text); self.assertNotIn("persistent", text); self.assertNotIn("reachable", text)

    def test_m6_pseudonymizes_history(self):
        text = repr(build_method_projection("M6_TLA", bundle("f07")).payload)
        self.assertNotIn("H_PERTURBED", text); self.assertNotIn("history_role", text); self.assertIn("stream_id", text)

    def test_projection_source_does_not_import_oracle(self):
        for name in ("p6r_projection.py", "p6r_detectors.py"):
            tree = ast.parse((ROOT / "src" / name).read_text(encoding="utf-8"))
            imports = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module]
            self.assertFalse(any("oracle" in module for module in imports))


class DetectorTests(unittest.TestCase):
    def test_safe_bundle_is_quiet_for_applicable_methods(self):
        for method_id in ("M1_FINAL", "M4_OPERATOR", "M5_META", "M6_TLA"):
            self.assertFalse(detect_projection(build_method_projection(method_id, bundle())).anomaly_detected, method_id)

    def test_m5_detects_replay_drift_without_lifecycle_fields(self):
        result = detect_projection(build_method_projection("M5_META", bundle("m5")))
        self.assertTrue(result.anomaly_detected); self.assertEqual(result.localization_plane, "REPLAY_RELATION")

    def test_m6_detects_f05_reachability(self):
        self.assertEqual(detect_projection(build_method_projection("M6_TLA", bundle("f05"))).classification, "FAIL_REJECTED_CANDIDATE_REACHABILITY")

    def test_m6_detects_f07_restoration(self):
        self.assertEqual(detect_projection(build_method_projection("M6_TLA", bundle("f07"))).classification, "FAIL_PERSISTENT_STATE_RESTORATION")

    def test_not_applicable_has_no_denominator_value(self):
        for method_id in ("M2_CKPT", "M3_STATE"):
            result = detect_projection(build_method_projection(method_id, object()))
            self.assertIsNone(result.anomaly_detected); self.assertFalse(result.applicable)


class ImmutabilityTests(unittest.TestCase):
    def test_recursive_freeze_blocks_mapping_write(self):
        value = freeze_recursive({"nested": {"x": 1}, "items": [1, 2]})
        with self.assertRaises(TypeError): value["nested"]["x"] = 2
        self.assertIsInstance(value["items"], tuple)

    def test_import_does_not_create_results(self): self.assertFalse((ROOT / "results").exists())


if __name__ == "__main__": unittest.main()

