"""Directed preflight tests for independent L5-D1."""

from __future__ import annotations

import ast
import hashlib
import json
import math
from pathlib import Path
import unittest

from benchmarks.L5_independent_validation.src.l5_cases import execute_case,load_design
from benchmarks.L5_independent_validation.src.l5_lifecycle import (
    IndependentSafeVariant,IndependentUnsafeVariant,accepted_output_probe,retry_comparison,
)
from benchmarks.L5_independent_validation.src.l5_oracle import (
    BREAKTHROUGH_TIME,SHOCK_SATURATION,SHOCK_SPEED,independent_oracle,
)
from benchmarks.L5_independent_validation.src.l5_solver import (
    cumulative_defects,run_checkpoints,snapshot,
)
from benchmarks.L5_independent_validation.src.l5_state import (
    IndependentModel,binary_fingerprint,initial_committed,
)

ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/"benchmarks"/"L5_independent_validation"

class L5D1Tests(unittest.TestCase):
    def test_freeze_matrix(self):
        freeze,matrix=load_design(ROOT)
        self.assertEqual(freeze["design_version"],"L5-D1.0")
        self.assertEqual(freeze["design_status"],"FROZEN_NOT_IMPLEMENTED")
        self.assertEqual(len(matrix),8)
        self.assertEqual(set(matrix),set(freeze["formal_cases"]))

    def test_no_L4_implementation_import(self):
        forbidden="benchmarks.L4_two_phase_displacement"
        for path in (BASE/"src").glob("*.py"):
            tree=ast.parse(path.read_text(encoding="utf-8"),filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node,ast.Import):
                    self.assertTrue(all(not alias.name.startswith(forbidden) for alias in node.names),path.name)
                if isinstance(node,ast.ImportFrom):
                    self.assertFalse((node.module or "").startswith(forbidden),path.name)

    def test_binary_serializer(self):
        state=initial_committed(8)
        self.assertEqual(state.fingerprint,binary_fingerprint(state))
        self.assertEqual(state.fingerprint,binary_fingerprint(state))
        self.assertEqual(len(state.fingerprint),64)

    def test_oracle_identity(self):
        profile=independent_oracle(80,0.2)
        self.assertLess(0.2,BREAKTHROUGH_TIME)
        self.assertAlmostEqual(SHOCK_SATURATION,1/math.sqrt(2),places=15)
        self.assertAlmostEqual(SHOCK_SPEED,(1+math.sqrt(2))/2,places=15)
        self.assertLessEqual(profile.maximum_root_residual,1e-13)
        self.assertLessEqual(profile.phase_mass_identity_error,1e-12)

    def test_independent_solver_balance_and_bounds(self):
        model=IndependentModel()
        state=run_checkpoints(model,64,0.35,(0.2,))[0][0.2]
        defects=cumulative_defects(model,state)
        self.assertLessEqual(max(abs(v) for v in defects),1e-11)
        self.assertGreaterEqual(min(state.saturation_n),-1e-12)
        self.assertLessEqual(max(state.saturation_n),1+1e-12)
        self.assertTrue(all(math.isfinite(v) for v in snapshot(model,state).pressure))

    def test_output_provenance(self):
        result=accepted_output_probe()
        self.assertTrue(result["candidate_reachable_while_output"])
        self.assertTrue(result["candidate_unreachable_after_reject"])
        self.assertTrue(result["output_exact"])
        self.assertTrue(result["committed_unchanged"])

    def test_safe_retry(self):
        result=retry_comparison(IndependentSafeVariant)
        self.assertTrue(result.declared_context_equal)
        self.assertTrue(result.exact_saturation)
        self.assertTrue(result.exact_pressure)
        self.assertTrue(result.exact_output_fingerprint)
        self.assertEqual(result.saturation_l2_drift,0.0)

    def test_unsafe_retry(self):
        result=retry_comparison(IndependentUnsafeVariant)
        self.assertTrue(result.declared_context_equal)
        self.assertTrue(result.committed_unchanged_at_reject)
        self.assertFalse(result.observed_fingerprint_equal)
        self.assertGreaterEqual(result.saturation_l2_drift,1e-4)
        self.assertGreaterEqual(result.pressure_l2_drift,1e-7)
        self.assertGreaterEqual(result.displacement_drift,1e-8)
        self.assertGreaterEqual(result.declared_phase_mass_defect,1e-5)
        self.assertTrue(result.all_values_finite)

    def test_protected_L4_aggregate(self):
        raw=ROOT/"benchmarks"/"L4_two_phase_displacement"/"results"/"L4_D1_two_phase_displacement"
        final=raw/"final"
        files=sorted((p for p in raw.rglob("*") if p.is_file() and final not in p.parents),key=lambda p:p.relative_to(raw).as_posix())
        payload="\n".join(f"{p.relative_to(raw).as_posix()}|{hashlib.sha256(p.read_bytes()).hexdigest()}" for p in files)
        self.assertEqual(hashlib.sha256(payload.encode()).hexdigest(),"ff25b0622dd8ce74a6a5d8d3f712df593e732a20918c4259c7fc0afb4539e78d")

    def test_all_cases_preflight(self):
        _,matrix=load_design(ROOT)
        for case_id in matrix:
            with self.subTest(case_id=case_id):
                result=execute_case(ROOT,case_id,"unit_preflight")["case_result"]
                self.assertTrue(result["pass_flag"],result)
                self.assertTrue(result["all_values_finite"])

    def test_unauthorized_case(self):
        with self.assertRaises(KeyError):
            execute_case(ROOT,"L5-NOT-A-CASE","unit_preflight")

if __name__=="__main__":
    unittest.main()
