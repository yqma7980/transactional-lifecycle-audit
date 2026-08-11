from __future__ import annotations

from dataclasses import dataclass
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping


FINITE_LIMIT = 1.0e100
STRENGTHS = {"ETA-LOW": 1.0e-10, "ETA-HIGH": 1.0e-6, "CONTROL": 0.0}


def _canonical(value: Any) -> Any:
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("nonfinite value cannot be canonicalized")
        return {"__float_hex__": value.hex()}
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, Mapping):
        return {str(key): _canonical(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    if hasattr(value, "tolist"):
        return _canonical(value.tolist())
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(_canonical(value), ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("ascii")).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json_new(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, ensure_ascii=True)
        handle.write("\n")


def write_csv_new(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    materialized = [dict(row) for row in rows]
    if not materialized:
        raise ValueError("CSV rows cannot be empty")
    fields = list(materialized[0])
    if any(list(row) != fields for row in materialized):
        raise ValueError("CSV rows have inconsistent fields")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(materialized)


@dataclass(frozen=True)
class CaseSpec:
    case_id: str
    canonical_identity: str
    effective_partition: str
    subject_id: str
    fault_id: str
    site_id: str
    strength_id: str
    history_id: str
    control_id: str
    category: str
    applicable: bool
    eligible: bool
    expected_verdict: str
    ground_truth_owner: str
    ground_truth_module: str
    ground_truth_event: str
    ground_truth_field: str
    ground_truth_source_plane: str

    @classmethod
    def from_row(cls, row: Mapping[str, str]) -> "CaseSpec":
        return cls(
            case_id=row["case_id"],
            canonical_identity=row["canonical_identity"],
            effective_partition=row["effective_partition"],
            subject_id=row["subject_id"],
            fault_id=row["fault_id"],
            site_id=row["site_id"],
            strength_id=row["strength_id"],
            history_id=row["history_id"],
            control_id=row["control_id"],
            category=row["category"],
            applicable=row["applicable"].lower() == "true",
            eligible=row["eligible"].lower() == "true",
            expected_verdict=row["expected_verdict"],
            ground_truth_owner=row["ground_truth_owner"],
            ground_truth_module=row["ground_truth_module"],
            ground_truth_event=row["ground_truth_event"],
            ground_truth_field=row["ground_truth_field"],
            ground_truth_source_plane=row["ground_truth_source_plane"],
        )

    @property
    def strength(self) -> float:
        if self.strength_id not in STRENGTHS:
            return 0.0
        return STRENGTHS[self.strength_id]


def load_case_specs(matrix_path: Path) -> dict[str, CaseSpec]:
    with matrix_path.open("r", encoding="utf-8", newline="") as handle:
        specs = [CaseSpec.from_row(row) for row in csv.DictReader(handle)]
    index = {spec.case_id: spec for spec in specs}
    if len(index) != len(specs):
        raise ValueError("duplicate case ID")
    return index


def finite(values: Iterable[float]) -> bool:
    return all(math.isfinite(float(value)) and abs(float(value)) < FINITE_LIMIT for value in values)


def standard_event(
    sequence: int,
    event_type: str,
    *,
    accepted: bool = False,
    candidate_id: str | None = None,
    owner: str | None = None,
    field_name: str | None = None,
    before_hash: str | None = None,
    after_hash: str | None = None,
    source_plane: str | None = None,
    residual_version: str | None = None,
    tangent_version: str | None = None,
) -> dict[str, Any]:
    return {
        "sequence": sequence,
        "event_type": event_type,
        "accepted": accepted,
        "candidate_id": candidate_id,
        "owner": owner,
        "field_name": field_name,
        "before_hash": before_hash,
        "after_hash": after_hash,
        "source_plane": source_plane,
        "residual_version": residual_version,
        "tangent_version": tangent_version,
    }

