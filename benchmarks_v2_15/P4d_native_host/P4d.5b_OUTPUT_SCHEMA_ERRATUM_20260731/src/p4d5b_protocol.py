from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Mapping

ROOT = Path(__file__).resolve().parents[1]
P4D_ROOT = ROOT.parent
P4D2_ROOT = P4D_ROOT / "P4d.2_FULL_IMPLEMENTATION_20260731"
P4D2_RESULTS_ROOT = P4D2_ROOT / "results" / "P4d2_formal_20260731"
P4D5_ROOT = P4D_ROOT / "P4d.5_IMPLEMENTATION_PREFLIGHT_20260731"
RUN_IDS = ("run_1", "run_2")
CASE_ID = "P4D-NC-OUTPUT-01"
EXPECTED_VERDICT = "FAIL_REJECTED_CANDIDATE_REACHABILITY"
FREEZE_SHA256 = "2b90c6d23404b2dd935d11ca0512810059cc2920ef0ed462c03d95142a3a15de"
PROTECTED_SHA256 = {
    "P4d.2_FULL_IMPLEMENTATION_20260731/src/p4d_cases.py": "40830e1c2a4e1d177b942ef069831e9f993a1ecfc0ffe16f1133edf2aa3680f7",
    "P4d.2_FULL_IMPLEMENTATION_20260731/src/p4d_config.py": "58a36323256d24fbb49507a690218db99361d2d9ad79792e3b8ffc377e338300",
    "P4d.2_FULL_IMPLEMENTATION_20260731/src/p4d_io.py": "6e2d8e30003f8541759aa7406bbebc0da5750105d5a8cf2f7bf5c028e9e87a85",
    "P4d.5_IMPLEMENTATION_PREFLIGHT_20260731/P4d5_source_manifest.json": "6e31e3fc437785933c27b440253332088d151cd2e37a90dc209316fe89d8471a",
    "P4d.5_IMPLEMENTATION_PREFLIGHT_20260731/formal_execution_logs/P4d5_branch_resumption_20260731/P4D-NC-OUTPUT-01_run_1.log": "2ec3cb867d75bc9f2ec108ff7255bce66ffb6ccd973a20381a63086b16dea4ea",
    "P4d.5_IMPLEMENTATION_PREFLIGHT_20260731/formal_execution_logs/P4d5_branch_resumption_20260731/P4D-NC-OUTPUT-01_run_2.log": "2ec3cb867d75bc9f2ec108ff7255bce66ffb6ccd973a20381a63086b16dea4ea",
    "P4d.5_IMPLEMENTATION_PREFLIGHT_20260731/results/P4d5_branch_resumption_20260731/final/p4d5_formal_branch_summary.json": "38cb47ef57e79eea58975bf118cc667401ba893a7f2f4498fcbb51b8148bda72",
    "P4d.5_IMPLEMENTATION_PREFLIGHT_20260731/results/P4d5_branch_resumption_20260731/final/p4d5_formal_raw_manifest.json": "44276cc4d7517fff59228d4e94361f3fa311799b18287ee03d3dcb76aca70e2d",
    "P4d.5_IMPLEMENTATION_PREFLIGHT_20260731/results/P4d5_branch_resumption_20260731/final/p4d5_formal_source_manifest.json": "70ab7b36975457467adbd29bf746e4e456f7190875e55d99b8e3194375919c40"
}

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def verify_protected_inputs() -> dict[str, str]:
    observed = {}
    freeze = ROOT / "P4d5b_erratum_freeze.json"
    if sha256(freeze) != FREEZE_SHA256:
        raise RuntimeError("P4d.5b freeze hash mismatch")
    observed[freeze.name] = FREEZE_SHA256
    for relative, expected in PROTECTED_SHA256.items():
        path = P4D_ROOT / relative
        if not path.is_file() or sha256(path) != expected:
            raise RuntimeError(f"protected input mismatch: {relative}")
        observed[relative] = expected
    return observed

def verify_retry_prerequisite() -> str:
    path = P4D5_ROOT / "results" / "P4d5_branch_resumption_20260731" / "final" / "p4d5_formal_branch_summary.json"
    summary = json.loads(path.read_text(encoding="utf-8"))
    status = {x["case_id"]: x["status"] for x in summary["case_status"]}
    if status.get("P4D-SAFE-RT-01") != "PASS_TWO_FRESH_PROCESS_FULL_FILE_QA":
        raise RuntimeError("P4D-SAFE-RT-01 prerequisite is not a two-run full-file pass")
    if status.get(CASE_ID) != "BLOCKED_OUTPUT_WRITER_SCHEMA":
        raise RuntimeError("historical output blocker changed")
    return status["P4D-SAFE-RT-01"]

def require_case_and_run(case_id: str, run_id: str) -> None:
    if case_id != CASE_ID:
        raise SystemExit("P4d.5b permits only P4D-NC-OUTPUT-01")
    if run_id not in RUN_IDS:
        raise SystemExit("run_id must be run_1 or run_2")

def case_authorized(cli_lock: bool, environment: Mapping[str,str] | None=None) -> bool:
    env = os.environ if environment is None else environment
    return bool(cli_lock and env.get("P4D5B_EXECUTION_AUTHORIZED") == "YES")

def pair_authorized(cli_lock: bool, environment: Mapping[str,str] | None=None) -> bool:
    env = os.environ if environment is None else environment
    return bool(cli_lock and env.get("P4D5B_PAIR_EXECUTION_AUTHORIZED") == "YES")

def require_single_thread_environment(environment: Mapping[str,str] | None=None) -> None:
    env = os.environ if environment is None else environment
    for name in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS","PYTHONDONTWRITEBYTECODE"):
        if env.get(name) != "1":
            raise SystemExit(f"{name}=1 is required")

def require_descendant(candidate: Path, parent: Path) -> Path:
    resolved=candidate.resolve(); base=parent.resolve()
    if not resolved.is_relative_to(base):
        raise SystemExit(f"path must remain below {base}")
    return resolved
