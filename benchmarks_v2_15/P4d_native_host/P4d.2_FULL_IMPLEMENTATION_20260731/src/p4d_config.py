from __future__ import annotations

from dataclasses import dataclass


DESIGN_VERSION = "P4d.0"
IMPLEMENTATION_VERSION = "P4d.2"
HOST_VERSION = "P4D-DOLFINX-PETSC-HOST-1.0"
SERIALIZER_VERSION = "P4D-CANONICAL-1.0"
STATE_SCHEMA_VERSION = "CMAME-P4D-STATE-1.0"
OUTPUT_SCHEMA_VERSION = "CMAME-P4D-STATE-IO-1.0"
RESIDUAL_VERSION = "P4D-R-1.0"
TANGENT_VERSION = "P4D-J-1.0"

G = 10.0
TAU_Y0 = 1.0
HARDENING = 2.0
LOAD_PATH = (0.0, 0.04, 0.08, 0.10, 0.12, 0.16, 0.20, 0.14, 0.08, 0.16, 0.20)
RETRY_SOURCE_LOAD = 0.08
RETRY_FAILED_TARGET = 0.20
RETRY_REPLAY_TARGET = 0.10
RESTART_LOAD = 0.12
LAG_SOURCE_LOAD = 0.08
LAG_TARGET_LOAD = 0.16
NEGATIVE_CACHE_SCALE = 1.0e-6

ABS_TOL = 1.0e-10
REL_TOL = 1.0e-10
FINITE_LIMIT = 1.0e100
EQUILIBRIUM_TOL = 1.0e-10
YIELD_TOL = 1.0e-9
OPERATOR_DRIFT_THRESHOLD = 1.0e-10

SNES_OPTIONS = {
    "snes_type": "newtonls",
    "snes_linesearch_type": "bt",
    "snes_atol": 1.0e-11,
    "snes_rtol": 1.0e-10,
    "snes_stol": 1.0e-12,
    "snes_max_it": 25,
    "ksp_type": "preonly",
    "pc_type": "lu",
}

FORMAL_CASE_IDS = (
    "P4D-REF-01",
    "P4D-CONST-01",
    "P4D-SAFE-DIR-01",
    "P4D-SAFE-LS-01",
    "P4D-SAFE-RT-01",
    "P4D-SAFE-RS-01",
    "P4D-NC-CACHE-01",
    "P4D-NC-OUTPUT-01",
    "P4D-VER-01",
)


@dataclass(frozen=True)
class CaseContract:
    case_id: str
    history_id: str
    variant: str
    expected_primary_verdict: str
    prerequisite: str | None


CASE_CONTRACTS = {
    "P4D-REF-01": CaseContract("P4D-REF-01", "H_REFERENCE", "safe_elastic_manufactured", "REFERENCE_GATE_PASS", None),
    "P4D-CONST-01": CaseContract("P4D-CONST-01", "H_MATERIAL_PACKET", "safe_transactional_material", "CONSTITUTIVE_ORACLE_PASS", "P4D-REF-01"),
    "P4D-SAFE-DIR-01": CaseContract("P4D-SAFE-DIR-01", "H_DIRECT", "safe_transactional", "PASS_REPLAY_INVARIANCE_WITHIN_TESTED_CLASS", "P4D-CONST-01"),
    "P4D-SAFE-LS-01": CaseContract("P4D-SAFE-LS-01", "H_NATIVE_LINESEARCH", "safe_transactional_declared_lag", "PASS_REPLAY_INVARIANCE_WITHIN_TESTED_CLASS", "P4D-SAFE-DIR-01"),
    "P4D-SAFE-RT-01": CaseContract("P4D-SAFE-RT-01", "H_DRIVER_RETRY", "safe_transactional", "PASS_REPLAY_INVARIANCE_WITHIN_TESTED_CLASS", "P4D-SAFE-LS-01"),
    "P4D-SAFE-RS-01": CaseContract("P4D-SAFE-RS-01", "H_RESTART", "safe_transactional", "PASS_REPLAY_INVARIANCE_WITHIN_TESTED_CLASS", "P4D-SAFE-RT-01"),
    "P4D-NC-CACHE-01": CaseContract("P4D-NC-CACHE-01", "H_CACHE_NEGATIVE", "unsafe_trial_cache", "FAIL_PERSISTENT_STATE_RESTORATION", "P4D-SAFE-RT-01"),
    "P4D-NC-OUTPUT-01": CaseContract("P4D-NC-OUTPUT-01", "H_OUTPUT_NEGATIVE", "unsafe_rejected_output", "FAIL_REJECTED_CANDIDATE_REACHABILITY", "P4D-SAFE-RT-01"),
    "P4D-VER-01": CaseContract("P4D-VER-01", "H_VERSION_GUARD", "undeclared_tangent_version", "EXPECTED_REJECT_OPERATOR_VERSION_MISMATCH_BEFORE_CORRECTION", "P4D-CONST-01"),
}


def is_declared_lag_step(source_load: float, target_load: float, accepted_index: int) -> bool:
    return accepted_index >= 8 and source_load == LAG_SOURCE_LOAD and target_load == LAG_TARGET_LOAD
