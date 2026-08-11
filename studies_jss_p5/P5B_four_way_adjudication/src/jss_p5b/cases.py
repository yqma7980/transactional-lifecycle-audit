from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from .model import ContractError, PrecomparisonRelation, Verdict


MATRIX_RELATIVE_PATH = Path(
    "00_frozen_inputs/P5A/02_four_way/P5B_four_way_case_matrix.csv"
)
EXPECTED_DESIGN_VERSION = "JSS-P5B.0"
EXPECTED_IMPLEMENTATION_STATUS = "FROZEN_NOT_IMPLEMENTED"
EXPECTED_CASE_COUNT = 20


@dataclass(frozen=True)
class CaseSpec:
    case_id: str
    design_version: str
    partition: str
    subject_id: str
    target_verdict: Verdict
    case_role: str
    fault_or_control: str
    history_a: str
    history_b: str
    precomparison_relation: PrecomparisonRelation
    required_observable: str
    ground_truth: str
    applicability_gate: str
    implementation_status: str
    execution_authorized: bool


def _parse_bool(value: str) -> bool:
    lowered = value.strip().lower()
    if lowered not in {"true", "false"}:
        raise ContractError(f"invalid frozen boolean: {value!r}")
    return lowered == "true"


def _parse_row(row: dict[str, str]) -> CaseSpec:
    return CaseSpec(
        case_id=row["case_id"],
        design_version=row["design_version"],
        partition=row["partition"],
        subject_id=row["subject_id"],
        target_verdict=Verdict(row["target_verdict"]),
        case_role=row["case_role"],
        fault_or_control=row["fault_or_control"],
        history_a=row["history_A"],
        history_b=row["history_B"],
        precomparison_relation=PrecomparisonRelation(row["precomparison_relation"]),
        required_observable=row["required_observable"],
        ground_truth=row["ground_truth"],
        applicability_gate=row["applicability_gate"],
        implementation_status=row["implementation_status"],
        execution_authorized=_parse_bool(row["execution_authorized"]),
    )


def validate_case_matrix(cases: tuple[CaseSpec, ...]) -> None:
    if len(cases) != EXPECTED_CASE_COUNT:
        raise ContractError(f"expected 20 frozen cases, found {len(cases)}")
    if len({case.case_id for case in cases}) != len(cases):
        raise ContractError("frozen case IDs are not unique")
    if any(case.design_version != EXPECTED_DESIGN_VERSION for case in cases):
        raise ContractError("design version drift")
    if any(case.implementation_status != EXPECTED_IMPLEMENTATION_STATUS for case in cases):
        raise ContractError("implementation status is not frozen")
    if any(case.execution_authorized for case in cases):
        raise ContractError("formal execution is unexpectedly authorized")
    counts = {verdict: 0 for verdict in Verdict}
    held_out = {verdict: 0 for verdict in Verdict}
    for case in cases:
        counts[case.target_verdict] += 1
        if case.partition == "HELD_OUT":
            held_out[case.target_verdict] += 1
        elif case.partition != "DEVELOPMENT":
            raise ContractError(f"unknown partition: {case.partition}")
    if any(count != 5 for count in counts.values()):
        raise ContractError(f"four-way allocation drift: {counts}")
    if any(count != 1 for count in held_out.values()):
        raise ContractError(f"held-out allocation drift: {held_out}")


def load_case_matrix(root: Path) -> tuple[CaseSpec, ...]:
    path = root / MATRIX_RELATIVE_PATH
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = tuple(_parse_row(row) for row in csv.DictReader(handle))
    validate_case_matrix(rows)
    return rows


def case_by_id(cases: tuple[CaseSpec, ...], case_id: str) -> CaseSpec:
    matches = [case for case in cases if case.case_id == case_id]
    if len(matches) != 1:
        raise ContractError(f"unknown or duplicate frozen case ID: {case_id}")
    return matches[0]
