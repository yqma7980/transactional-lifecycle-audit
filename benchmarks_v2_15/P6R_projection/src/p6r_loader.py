from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from p6r_contracts import (
    ContractError,
    DESIGN_VERSION,
    EXPECTED_FREEZE_MANIFEST_SHA256,
    sha256_file,
)


def freeze_recursive(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: freeze_recursive(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(freeze_recursive(item) for item in value)
    return value


@dataclass(frozen=True)
class RawBundle:
    p6r_case_id: str
    repetition: int
    p5_run_id: str
    file_hashes: Mapping[str, str]
    case_result: Mapping[str, Any]
    accepted_output: tuple[Mapping[str, str], ...]
    event_ledger: tuple[Mapping[str, str], ...]
    environment: Mapping[str, Any]
    metric_packets: Mapping[str, Any]
    operator_contributions: Mapping[str, Any]


def _read_csv(path: Path) -> tuple[Mapping[str, str], ...]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return tuple(MappingProxyType(dict(row)) for row in csv.DictReader(stream))


def _read_json(path: Path) -> Mapping[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        value = freeze_recursive(json.load(stream))
    if not isinstance(value, Mapping):
        raise ContractError(f"JSON root is not an object: {path}")
    return value


def _read_npz(path: Path) -> Mapping[str, Any]:
    try:
        import numpy as np
    except ImportError as exc:
        raise ContractError("NumPy is required only when a formal raw bundle is loaded") from exc
    arrays: dict[str, Any] = {}
    with np.load(path, allow_pickle=False) as archive:
        for key in sorted(archive.files):
            array = archive[key].copy()
            array.flags.writeable = False
            arrays[key] = array
    return MappingProxyType(arrays)


def verify_frozen_design(study_root: Path) -> dict[str, Any]:
    manifest_path = study_root / "P6R_source_manifest.json"
    observed = sha256_file(manifest_path)
    if observed != EXPECTED_FREEZE_MANIFEST_SHA256:
        raise ContractError(
            f"P6R source manifest drift: {observed} != {EXPECTED_FREEZE_MANIFEST_SHA256}"
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("design_version") != DESIGN_VERSION:
        raise ContractError("unexpected P6R design version")
    for record in manifest.get("design_outputs", []):
        path = study_root / record["path"]
        if not path.is_file() or sha256_file(path) != record["sha256"]:
            raise ContractError(f"frozen design output drift: {record['path']}")
    return manifest


def validate_raw_evidence(ncs_root: Path, study_root: Path) -> dict[str, Any]:
    manifest = verify_frozen_design(study_root)
    mismatches: list[str] = []
    for record in manifest.get("raw_inputs", []):
        path = ncs_root / record["relative_path"]
        if not path.is_file() or sha256_file(path) != record["sha256"]:
            mismatches.append(record["relative_path"])
    if mismatches:
        raise ContractError(f"immutable P5 raw evidence drift: {mismatches[:3]}")
    return {
        "design_version": manifest["design_version"],
        "raw_file_count": len(manifest.get("raw_inputs", [])),
        "raw_hash_mismatch_count": 0,
        "formal_projection_executed": False,
    }


def validate_raw_schemas(ncs_root: Path, study_root: Path) -> dict[str, Any]:
    manifest = verify_frozen_design(study_root)
    required = {
        "accepted_output.csv": {"accepted_version", "residual_norm", "relation"},
        "event_ledger.csv": {
            "event_kind",
            "candidate_id",
            "persistent_projection_hash",
            "operator_version_relation",
        },
    }
    checked = 0
    for record in manifest.get("raw_inputs", []):
        name = Path(record["relative_path"]).name
        if name not in required:
            continue
        path = ncs_root / record["relative_path"]
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            header = set(next(csv.reader(stream)))
        missing = required[name] - header
        if missing:
            raise ContractError(f"raw schema missing {sorted(missing)} in {path}")
        checked += 1
    return {"csv_schema_files_checked": checked, "csv_schema_mismatch_count": 0}


def _bundle_records(study_root: Path, case_id: str, repetition: int) -> list[dict[str, Any]]:
    manifest = json.loads((study_root / "P6R_source_manifest.json").read_text(encoding="utf-8"))
    records = [
        record
        for record in manifest["raw_inputs"]
        if record["p6r_case_id"] == case_id and int(record["repetition"]) == repetition
    ]
    if len(records) != 7:
        raise ContractError(f"expected seven immutable files for {case_id}/rep{repetition}")
    return records


def load_raw_bundle(
    ncs_root: Path, study_root: Path, case_id: str, repetition: int
) -> RawBundle:
    verify_frozen_design(study_root)
    records = _bundle_records(study_root, case_id, repetition)
    paths: dict[str, Path] = {}
    hashes: dict[str, str] = {}
    run_ids = {record["p5_run_id"] for record in records}
    if len(run_ids) != 1:
        raise ContractError("raw bundle spans multiple P5 run IDs")
    for record in records:
        path = ncs_root / record["relative_path"]
        observed = sha256_file(path)
        if observed != record["sha256"]:
            raise ContractError(f"immutable raw file drift: {record['relative_path']}")
        paths[path.name] = path
        hashes[path.name] = observed
    return RawBundle(
        p6r_case_id=case_id,
        repetition=repetition,
        p5_run_id=next(iter(run_ids)),
        file_hashes=MappingProxyType(hashes),
        case_result=_read_json(paths["case_result.json"]),
        accepted_output=_read_csv(paths["accepted_output.csv"]),
        event_ledger=_read_csv(paths["event_ledger.csv"]),
        environment=_read_json(paths["environment.json"]),
        metric_packets=_read_npz(paths["metric_packets.npz"]),
        operator_contributions=_read_npz(paths["operator_contributions.npz"]),
    )

