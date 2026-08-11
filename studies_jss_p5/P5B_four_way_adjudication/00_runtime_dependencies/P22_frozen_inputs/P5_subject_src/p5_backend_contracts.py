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
FREEZE_ROOT = WORKING / "P5_SCALED_THRESHOLD_AND_FRESH_PROCESS_NULL_ENVELOPE_FREEZE_20260731"
PREFLIGHT_ROOT = WORKING / "P5_IMPLEMENTATION_PREFLIGHT_20260731"
P4D_ROOT = WORKING / "P4d_DOLFINx_PETSc_MINIMAL_FE_HOST_20260731"
P4D2_ROOT = P4D_ROOT / "P4d.2_FULL_IMPLEMENTATION_20260731"
P4D5B_ROOT = P4D_ROOT / "P4d.5b_OUTPUT_SCHEMA_ERRATUM_20260731"

DESIGN_VERSION = "CMAME-P5.0"
IMPLEMENTATION_VERSION = "CMAME-P5.2-FE-BACKEND"
HOST_VERSION = "P4D-DOLFINX-PETSC-HOST-1.0+P5-AUDIT-ADAPTER-1.0"
IMAGE = "dolfinx/dolfinx@sha256:1bb0d528457c78db65ba5445421abe37d0cdfa542cc182bf36d3b4aca02f1fab"
EXPECTED_FREEZE_MANIFEST_SHA256 = "6e64554f9547b71ca2e407acc6a8e14153abc8683e6688f3e3604e6d0188d573"
EXPECTED_PREFLIGHT_MANIFEST_SHA256 = "7b91a8580250f162fb06b44611f7e132f72b4bcecedea66e980fd290e3e0efeb"
EXPECTED_PREFLIGHT_IMPLEMENTATION_SHA256 = "1a97292f5222e7c7205d4c361991d5f36b2ffda9e22fdb811ef1d9a9603edb80"

CASE_IDS = (
    "P5-NULL-EXACT-CAL-01",
    "P5-NULL-ARITH-CAL-01",
    "P5-NULL-ARITH-CONF-01",
    "P5-SCALE-F01-DEV",
    "P5-SCALE-F02-DEV",
    "P5-SCALE-F05-DEV",
    "P5-SCALE-F07-DEV",
)

NULL_CASE_LIMITS = {
    "P5-NULL-EXACT-CAL-01": 6,
    "P5-NULL-ARITH-CAL-01": 6,
    "P5-NULL-ARITH-CONF-01": 2,
}
SCALED_CASES = {
    "P5-SCALE-F01-DEV": "F01",
    "P5-SCALE-F02-DEV": "F02",
    "P5-SCALE-F05-DEV": "F05",
    "P5-SCALE-F07-DEV": "F07",
}
ARITHMETIC_PATHS = (
    "ARITH_A_REFERENCE",
    "ARITH_B_CALIBRATION",
    "ARITH_C_CONFIRMATION",
    "ARITH_D_P6_BENIGN",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json_new(path: Path, payload: object) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


@dataclass(frozen=True)
class CaseContract:
    case_id: str
    role: str
    family_id: str
    process_budget: int


def _verify_manifest(manifest_path: Path, expected_hash: str, base: Path) -> int:
    if sha256(manifest_path) != expected_hash:
        raise RuntimeError(f"protected manifest drift: {manifest_path.name}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    checked = 0
    for key in ("outputs", "protected_inputs", "host_dependencies", "files_before_manifest"):
        for item in manifest.get(key, []):
            path = base / item["path"]
            expected_bytes = item.get("bytes", item.get("size_bytes"))
            if not path.is_file() or sha256(path) != item["sha256"]:
                raise RuntimeError(f"protected evidence drift: {item['path']}")
            if expected_bytes is not None and path.stat().st_size != int(expected_bytes):
                raise RuntimeError(f"protected evidence size drift: {item['path']}")
            checked += 1
    return checked


def verify_protected_evidence() -> dict[str, int]:
    workspace = WORKING.parent
    freeze_count = _verify_manifest(
        FREEZE_ROOT / "P5_source_manifest.json",
        EXPECTED_FREEZE_MANIFEST_SHA256,
        workspace,
    )
    preflight_source = PREFLIGHT_ROOT / "P5_source_manifest.json"
    if sha256(preflight_source) != EXPECTED_PREFLIGHT_MANIFEST_SHA256:
        raise RuntimeError("P5 preflight source manifest drift")
    if sha256(PREFLIGHT_ROOT / "P5_implementation_manifest.json") != EXPECTED_PREFLIGHT_IMPLEMENTATION_SHA256:
        raise RuntimeError("P5 preflight implementation manifest drift")
    implementation = json.loads((PREFLIGHT_ROOT / "P5_implementation_manifest.json").read_text(encoding="utf-8"))
    dependency_count = 0
    for key in ("files_before_manifest", "host_dependencies"):
        for item in implementation[key]:
            path = workspace / item["path"]
            if not path.is_file() or path.stat().st_size != int(item["bytes"]) or sha256(path) != item["sha256"]:
                raise RuntimeError(f"P5 preflight dependency drift: {item['path']}")
            dependency_count += 1
    return {"freeze_entries": freeze_count, "preflight_entries": dependency_count}


def load_case_contracts() -> tuple[CaseContract, ...]:
    with (FREEZE_ROOT / "P5_case_matrix.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    contracts = tuple(
        CaseContract(
            row["case_id"],
            row["case_role"],
            row["fault_family"],
            int(row["planned_fresh_process_count"]),
        )
        for row in rows
    )
    if tuple(item.case_id for item in contracts) != CASE_IDS:
        raise RuntimeError("P5 case order differs from the frozen matrix")
    if sum(item.process_budget for item in contracts) != 90:
        raise RuntimeError("P5 frozen process budget is not 90")
    return contracts


def load_strength_grid() -> tuple[dict[str, object], ...]:
    payload = json.loads((FREEZE_ROOT / "P5_execution_freeze.json").read_text(encoding="utf-8"))
    grid = tuple(payload["strength_grid"])
    if len(grid) != 15 or [item["index"] for item in grid] != list(range(15)):
        raise RuntimeError("P5 frozen strength grid mismatch")
    return grid


def require_case_and_run(case_id: str, run_id: str) -> CaseContract:
    contracts = {item.case_id: item for item in load_case_contracts()}
    if case_id not in contracts:
        raise SystemExit("unauthorized P5 case")
    if not run_id.startswith("run_") or not run_id[4:].isdigit():
        raise SystemExit("run_id must have the form run_N")
    number = int(run_id[4:])
    limit = NULL_CASE_LIMITS.get(case_id, 19)
    if not 1 <= number <= limit:
        raise SystemExit("run_id is outside the frozen case budget")
    return contracts[case_id]


def strength_index_for_run(case_id: str, run_id: str, selection_file: Path | None) -> int | None:
    if case_id not in SCALED_CASES:
        return None
    number = int(run_id[4:])
    if number <= 15:
        return number - 1
    if selection_file is None or not selection_file.is_file():
        raise SystemExit("fresh verification runs require a frozen selected-strength file")
    payload = json.loads(selection_file.read_text(encoding="utf-8"))
    family = SCALED_CASES[case_id]
    record = payload.get("families", {}).get(family)
    if not record or record.get("status") != "SELECTED_PENDING_FRESH_VERIFICATION":
        raise SystemExit("family has no eligible frozen selected pair")
    mapping = {
        16: int(record["selected_index"]),
        17: int(record["selected_index"]),
        18: int(record["next_index"]),
        19: int(record["next_index"]),
    }
    return mapping[number]


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
