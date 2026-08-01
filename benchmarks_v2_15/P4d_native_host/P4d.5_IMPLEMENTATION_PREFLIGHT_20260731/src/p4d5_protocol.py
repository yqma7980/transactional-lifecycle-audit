
from __future__ import annotations

import csv
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

ROOT = Path(__file__).resolve().parents[1]
P4D_ROOT = ROOT.parent
FREEZE_ROOT = P4D_ROOT / "P4d.5_INDEPENDENT_BRANCH_RESUMPTION_FREEZE_20260731"
P4D2_ROOT = P4D_ROOT / "P4d.2_FULL_IMPLEMENTATION_20260731"
P4D2_RESULTS_ROOT = P4D2_ROOT / "results" / "P4d2_formal_20260731"

CASE_ORDER = (
    "P4D-SAFE-RT-01",
    "P4D-SAFE-RS-01",
    "P4D-VER-01",
    "P4D-NC-CACHE-01",
    "P4D-NC-OUTPUT-01",
)
RUN_IDS = ("run_1", "run_2")

PROTECTED_SHA256 = {
    "P4d.5_INDEPENDENT_BRANCH_RESUMPTION_FREEZE_20260731/P4d5_source_manifest.json": "2acac695c8f4085df606fd4acd643172ea622145914950dc11d94e5b520d8395",
    "P4d.5_INDEPENDENT_BRANCH_RESUMPTION_FREEZE_20260731/P4d5_branch_resumption_freeze.json": "37346cca6fbf7d0e662c3b6af24b79cc10926992d2212d5e4e1e6669249536c3",
    "P4d.5_INDEPENDENT_BRANCH_RESUMPTION_FREEZE_20260731/P4d5_case_matrix.csv": "ba160da4be56ec4bcde62865cfd445b768a11a091f6ad7135e25524bf3a41bb3",
    "P4d.5_INDEPENDENT_BRANCH_RESUMPTION_FREEZE_20260731/P4d5_acceptance_gates.md": "67d6b02a0633070bedad8f25cf55a27f7f662ded1445813ab81f757527f99c06",
    "P4d.5_INDEPENDENT_BRANCH_RESUMPTION_FREEZE_20260731/P4d5_execution_plan.md": "ecd1f7ab11ebf10b30358617a51abf0795818e2e79ff16a5e9bb7174a25ba564",
    "P4d.2_FULL_IMPLEMENTATION_20260731/run_p4d2.py": "f6ba558860b5e84c818c7a41cdf191c7dfc7b43d2f26dc49f78326a89fb456b6",
    "P4d.2_FULL_IMPLEMENTATION_20260731/src/p4d_cases.py": "40830e1c2a4e1d177b942ef069831e9f993a1ecfc0ffe16f1133edf2aa3680f7",
    "P4d.2_FULL_IMPLEMENTATION_20260731/src/p4d_config.py": "58a36323256d24fbb49507a690218db99361d2d9ad79792e3b8ffc377e338300",
    "P4d.2_FULL_IMPLEMENTATION_20260731/results/P4d2_formal_20260731/final/p4d2_formal_stop_summary.json": "df520423b04e189da13923aa3ef1a0387fa1e0c44720d5bb0482d167c683c73e",
    "P4d.2_FULL_IMPLEMENTATION_20260731/results/P4d2_formal_20260731/final/p4d2_formal_raw_manifest.json": "384b7b4e5a8e1244672c5d076f46a589dae3995a91ec1d10ff0c7d13e0ecb22b",
    "P4d.2_FULL_IMPLEMENTATION_20260731/results/P4d2_formal_20260731/final/p4d2_duplicate_run_comparison.json": "00f469a9eca36016d75c35b03fb03bc0a2625cd2120a332bffcca1223989a5dd",
}

EXPECTED_VERDICTS = {
    "P4D-SAFE-RT-01": "PASS_REPLAY_INVARIANCE_WITHIN_TESTED_CLASS",
    "P4D-SAFE-RS-01": "PASS_REPLAY_INVARIANCE_WITHIN_TESTED_CLASS",
    "P4D-VER-01": "EXPECTED_REJECT_OPERATOR_VERSION_MISMATCH_BEFORE_CORRECTION",
    "P4D-NC-CACHE-01": "FAIL_PERSISTENT_STATE_RESTORATION",
    "P4D-NC-OUTPUT-01": "FAIL_REJECTED_CANDIDATE_REACHABILITY",
}


@dataclass(frozen=True)
class CaseContract:
    case_id: str
    execution_wave: int
    branch_id: str
    expected_primary_verdict: str
    formal_repetitions: int
    branch_local_prerequisite: str


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_freeze_source_manifest() -> dict[str, str]:
    manifest_path = FREEZE_ROOT / "P4d5_source_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    observed = {
        manifest_path.relative_to(P4D_ROOT).as_posix(): sha256(manifest_path)
    }
    for item in manifest["source_inputs"]:
        path = P4D_ROOT / item["path"]
        relative = path.relative_to(P4D_ROOT).as_posix()
        if not path.is_file():
            raise RuntimeError(f"missing freeze source input: {relative}")
        if path.stat().st_size != item["size_bytes"] or sha256(path) != item["sha256"]:
            raise RuntimeError(f"freeze source input mismatch: {relative}")
        observed[relative] = item["sha256"]
    for item in manifest["generated_outputs"]:
        path = FREEZE_ROOT / item["path"]
        relative = path.relative_to(P4D_ROOT).as_posix()
        if not path.is_file():
            raise RuntimeError(f"missing freeze generated output: {relative}")
        if path.stat().st_size != item["size_bytes"] or sha256(path) != item["sha256"]:
            raise RuntimeError(f"freeze generated output mismatch: {relative}")
        observed[relative] = item["sha256"]
    return observed


def verify_protected_inputs() -> dict[str, str]:
    observed = verify_freeze_source_manifest()
    for relative, expected in PROTECTED_SHA256.items():
        path = P4D_ROOT / relative
        if not path.is_file():
            raise RuntimeError(f"missing protected input: {relative}")
        actual = sha256(path)
        if actual != expected:
            raise RuntimeError(f"protected input hash mismatch: {relative}")
        observed[relative] = actual
    return observed


def load_case_contracts() -> tuple[CaseContract, ...]:
    path = FREEZE_ROOT / "P4d5_case_matrix.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    contracts = tuple(
        CaseContract(
            case_id=row["case_id"],
            execution_wave=int(row["execution_wave"]),
            branch_id=row["branch_id"],
            expected_primary_verdict=row["expected_primary_verdict"],
            formal_repetitions=int(row["formal_repetitions"]),
            branch_local_prerequisite=row["branch_local_prerequisite"],
        )
        for row in rows
    )
    validate_contracts(contracts, rows)
    return contracts


def validate_contracts(contracts: tuple[CaseContract, ...], rows: list[dict[str, str]]) -> None:
    if tuple(item.case_id for item in contracts) != CASE_ORDER:
        raise RuntimeError("P4d.5 case order differs from the frozen matrix")
    if len(set(item.case_id for item in contracts)) != len(CASE_ORDER):
        raise RuntimeError("P4d.5 case IDs are not unique")
    for contract, row in zip(contracts, rows, strict=True):
        if contract.expected_primary_verdict != EXPECTED_VERDICTS[contract.case_id]:
            raise RuntimeError(f"unexpected verdict for {contract.case_id}")
        if contract.formal_repetitions != 2:
            raise RuntimeError(f"unexpected repetition count for {contract.case_id}")
        if row["implementation_status"] != "FROZEN_STATIC_NOT_IMPLEMENTED":
            raise RuntimeError(f"unexpected frozen implementation status for {contract.case_id}")
        if row["execution_authorized"] != "false":
            raise RuntimeError(f"frozen matrix already authorizes {contract.case_id}")


def verify_inherited_prerequisites() -> dict[str, str]:
    summary_path = P4D2_RESULTS_ROOT / "final" / "p4d2_formal_stop_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    statuses = {item["case_id"]: item["status"] for item in summary["case_status"]}
    required = ("P4D-REF-01", "P4D-CONST-01", "P4D-SAFE-DIR-01")
    for case_id in required:
        if statuses.get(case_id) != "PASS_TWO_FRESH_PROCESS":
            raise RuntimeError(f"inherited prerequisite not passed twice: {case_id}")
    if summary["frozen_protocol_adjudication"] != "NOT_SUPPORTED_BY_FROZEN_HISTORY":
        raise RuntimeError("historical line-search adjudication changed")
    return {case_id: statuses[case_id] for case_id in required}


def require_case_and_run(case_id: str, run_id: str) -> CaseContract:
    contracts = {item.case_id: item for item in load_case_contracts()}
    if case_id not in contracts:
        raise SystemExit("unauthorized or unknown P4d.5 case")
    if run_id not in RUN_IDS:
        raise SystemExit("run_id must be run_1 or run_2")
    return contracts[case_id]


def case_authorized(cli_lock: bool, environment: Mapping[str, str] | None = None) -> bool:
    env = os.environ if environment is None else environment
    return bool(cli_lock and env.get("P4D5_EXECUTION_AUTHORIZED") == "YES")


def matrix_authorized(cli_lock: bool, environment: Mapping[str, str] | None = None) -> bool:
    env = os.environ if environment is None else environment
    return bool(cli_lock and env.get("P4D5_MATRIX_EXECUTION_AUTHORIZED") == "YES")


def require_single_thread_environment(environment: Mapping[str, str] | None = None) -> None:
    env = os.environ if environment is None else environment
    for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "PYTHONDONTWRITEBYTECODE"):
        if env.get(name) != "1":
            raise SystemExit(f"{name}=1 is required")


def require_descendant(candidate: Path, parent: Path) -> Path:
    resolved = candidate.resolve()
    base = parent.resolve()
    if not resolved.is_relative_to(base):
        raise SystemExit(f"path must remain below {base}")
    return resolved
