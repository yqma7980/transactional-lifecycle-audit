from __future__ import annotations

import csv
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

ROOT = Path(__file__).resolve().parents[1]
WORKING = ROOT.parent
WORKSPACE = WORKING.parent
FREEZE = WORKING / "P5_SCALED_THRESHOLD_AND_FRESH_PROCESS_NULL_ENVELOPE_FREEZE_20260731"
EXPECTED_MANIFEST_SHA256 = "6e64554f9547b71ca2e407acc6a8e14153abc8683e6688f3e3604e6d0188d573"
DESIGN_VERSION = "CMAME-P5.0"
IMPLEMENTATION_VERSION = "CMAME-P5.1-PREFLIGHT"
CASE_IDS = (
    "P5-NULL-EXACT-CAL-01",
    "P5-NULL-ARITH-CAL-01",
    "P5-NULL-ARITH-CONF-01",
    "P5-SCALE-F01-DEV",
    "P5-SCALE-F02-DEV",
    "P5-SCALE-F05-DEV",
    "P5-SCALE-F07-DEV",
)
RUN_IDS = tuple(f"run_{index}" for index in range(1, 7))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass(frozen=True)
class CaseContract:
    case_id: str
    case_role: str
    fault_family: str
    planned_fresh_process_count: int


def verify_frozen_evidence() -> dict[str, int]:
    manifest_path = FREEZE / "P5_source_manifest.json"
    if sha256(manifest_path) != EXPECTED_MANIFEST_SHA256:
        raise RuntimeError("P5 source manifest drift")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    counts = {"outputs": 0, "protected_inputs": 0}
    for section in counts:
        for item in manifest[section]:
            path = WORKSPACE / item["path"]
            if not path.is_file() or sha256(path) != item["sha256"] or path.stat().st_size != item["bytes"]:
                raise RuntimeError(f"protected evidence drift: {item['path']}")
            counts[section] += 1
    return counts


def load_case_contracts() -> tuple[CaseContract, ...]:
    with (FREEZE / "P5_case_matrix.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    contracts = tuple(
        CaseContract(
            case_id=row["case_id"],
            case_role=row["case_role"],
            fault_family=row["fault_family"],
            planned_fresh_process_count=int(row["planned_fresh_process_count"]),
        )
        for row in rows
    )
    if tuple(item.case_id for item in contracts) != CASE_IDS:
        raise RuntimeError("P5 case matrix identity/order mismatch")
    if sum(item.planned_fresh_process_count for item in contracts) != 90:
        raise RuntimeError("P5 future process budget mismatch")
    return contracts


def require_case_and_run(case_id: str, run_id: str) -> CaseContract:
    contracts = {item.case_id: item for item in load_case_contracts()}
    if case_id not in contracts:
        raise SystemExit("unauthorized P5 case")
    contract = contracts[case_id]
    maximum = 6 if contract.case_role.startswith("null") else 19
    if not run_id.startswith("run_") or not run_id[4:].isdigit() or not (1 <= int(run_id[4:]) <= maximum):
        raise SystemExit("run_id is outside the frozen case budget")
    return contract


def case_authorized(cli_lock: bool, environment: Mapping[str, str] | None = None) -> bool:
    env = os.environ if environment is None else environment
    return bool(cli_lock and env.get("P5_EXECUTION_AUTHORIZED") == "YES")


def matrix_authorized(cli_lock: bool, environment: Mapping[str, str] | None = None) -> bool:
    env = os.environ if environment is None else environment
    return bool(cli_lock and env.get("P5_MATRIX_EXECUTION_AUTHORIZED") == "YES")


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
