from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from .cases import CaseSpec, load_case_matrix
from .model import ContractError


MAPPING_FILENAME = "P5B1_CASE_RUNTIME_MAPPING.csv"
EXPECTED_MAPPING_ID = "JSS-P5B1-RUNTIME-MAPPING-1.0"


@dataclass(frozen=True)
class RuntimeMapping:
    case_id: str
    subject_id: str
    runtime_mode: str
    numeric_parameter: str
    history_a_runtime: str
    history_b_runtime: str
    evidence_tokens: tuple[str, ...]
    lifecycle_signals: tuple[str, ...]
    expected_packet_mismatch: tuple[str, ...]
    formal_partition: str


def _tokens(value: str) -> tuple[str, ...]:
    stripped = value.strip()
    if not stripped or stripped.lower() in {"none", "not_evaluated"}:
        return ()
    return tuple(item.strip() for item in stripped.split(";") if item.strip())


def load_runtime_mapping(root: Path) -> dict[str, RuntimeMapping]:
    path = root / MAPPING_FILENAME
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = tuple(csv.DictReader(handle))
    mappings = {
        row["case_id"]: RuntimeMapping(
            case_id=row["case_id"],
            subject_id=row["subject_id"],
            runtime_mode=row["runtime_mode"],
            numeric_parameter=row["numeric_parameter"],
            history_a_runtime=row["history_A_runtime"],
            history_b_runtime=row["history_B_runtime"],
            evidence_tokens=_tokens(row["evidence_tokens"]),
            lifecycle_signals=_tokens(row["lifecycle_signal"]),
            expected_packet_mismatch=_tokens(row["expected_packet_mismatch"]),
            formal_partition=row["formal_partition"],
        )
        for row in rows
    }
    if len(rows) != 16 or len(mappings) != 16:
        raise ContractError("runtime mapping must contain 16 unique DEVELOPMENT cases")
    cases = load_case_matrix(root)
    development = {case.case_id: case for case in cases if case.partition == "DEVELOPMENT"}
    if set(mappings) != set(development):
        raise ContractError("runtime mapping differs from the frozen DEVELOPMENT partition")
    for case_id, mapping in mappings.items():
        case = development[case_id]
        if mapping.subject_id != case.subject_id:
            raise ContractError(f"runtime subject drift for {case_id}")
        if mapping.formal_partition != "DEVELOPMENT":
            raise ContractError(f"runtime mapping contains a non-DEVELOPMENT row: {case_id}")
    return mappings


def mapping_for_case(root: Path, case: CaseSpec) -> RuntimeMapping:
    try:
        return load_runtime_mapping(root)[case.case_id]
    except KeyError as exc:
        raise ContractError(f"case has no frozen runtime mapping: {case.case_id}") from exc
