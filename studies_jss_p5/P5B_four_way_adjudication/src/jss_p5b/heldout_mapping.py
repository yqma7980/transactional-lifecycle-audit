from __future__ import annotations

import csv
from pathlib import Path

from .cases import CaseSpec, load_case_matrix
from .model import ContractError
from .runtime_mapping import RuntimeMapping


MAPPING_FILENAME = "P5B3_HELDOUT_RUNTIME_MAPPING.csv"


def _tokens(value: str) -> tuple[str, ...]:
    stripped = value.strip()
    if not stripped or stripped.lower() in {"none", "not_evaluated"}:
        return ()
    return tuple(item.strip() for item in stripped.split(";") if item.strip())


def load_heldout_mapping(root: Path) -> dict[str, RuntimeMapping]:
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
    if len(rows) != 4 or len(mappings) != 4:
        raise ContractError("held-out mapping must contain four unique cases")
    held_out = {
        case.case_id: case
        for case in load_case_matrix(root)
        if case.partition == "HELD_OUT"
    }
    if set(mappings) != set(held_out):
        raise ContractError("held-out mapping differs from the frozen partition")
    for case_id, mapping in mappings.items():
        case = held_out[case_id]
        if mapping.subject_id != case.subject_id:
            raise ContractError(f"runtime subject drift for {case_id}")
        if mapping.formal_partition != "HELD_OUT":
            raise ContractError(f"non-held-out mapping row: {case_id}")
    return mappings


def heldout_mapping_for_case(root: Path, case: CaseSpec) -> RuntimeMapping:
    try:
        return load_heldout_mapping(root)[case.case_id]
    except KeyError as exc:
        raise ContractError(f"case has no frozen held-out mapping: {case.case_id}") from exc
