from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Mapping

LEVEL_COUNT = 15
SEPARATION_RATIO = 10.0


@dataclass(frozen=True)
class SweepRow:
    index: int
    eta: float
    conventional_quiet: bool
    lifecycle_violation_present: bool
    all_values_finite: bool
    z_residual: float
    z_tangent: float

    @property
    def z_family(self) -> float:
        return max(self.z_residual, self.z_tangent)


@dataclass(frozen=True)
class SelectionResult:
    status: str
    selected_index: int | None
    selected_eta: float | None
    next_index: int | None
    next_eta: float | None


def select_strength(rows: Iterable[SweepRow]) -> SelectionResult:
    ordered = sorted(rows, key=lambda row: row.index)
    if [row.index for row in ordered] != list(range(LEVEL_COUNT)):
        raise ValueError("all 15 frozen strength levels are required")
    if any(not math.isfinite(row.eta) or not math.isfinite(row.z_family) for row in ordered):
        raise ValueError("strength sweep contains non-finite values")
    for index in range(LEVEL_COUNT - 1):
        prefix = ordered[:index + 2]
        current, following = ordered[index], ordered[index + 1]
        if (
            all(row.conventional_quiet and row.all_values_finite for row in prefix)
            and current.lifecycle_violation_present
            and following.lifecycle_violation_present
            and current.z_family >= SEPARATION_RATIO
            and following.z_family >= SEPARATION_RATIO
        ):
            return SelectionResult("SELECTED_PENDING_FRESH_VERIFICATION", index, current.eta, index + 1, following.eta)
    if any(not row.conventional_quiet for row in ordered):
        return SelectionResult("NOT_SUPPORTED_DISTINCTIVE_REGION_EMPTY", None, None, None, None)
    return SelectionResult("NOT_SUPPORTED_AT_FROZEN_SCALE", None, None, None, None)


def verify_fresh_repetitions(result: SelectionResult, repetitions: Mapping[int, list[Mapping[str, object]]]) -> str:
    if result.selected_index is None or result.next_index is None:
        raise ValueError("a selected adjacent pair is required")
    for index in (result.selected_index, result.next_index):
        records = repetitions.get(index, [])
        if len(records) != 2:
            return "BLOCKED_FRESH_PROCESS_NONREPEATABILITY"
        normalized = [{key: value for key, value in row.items() if key not in {"run_id", "wall_clock_timestamp", "absolute_path"}} for row in records]
        if normalized[0] != normalized[1]:
            return "BLOCKED_FRESH_PROCESS_NONREPEATABILITY"
        if not all(bool(row.get("conventional_quiet")) and bool(row.get("lifecycle_violation_present")) and float(row.get("z_family", 0.0)) >= 10.0 for row in records):
            return "BLOCKED_FRESH_PROCESS_NONREPEATABILITY"
    return "PASS_FRESH_PROCESS_VERIFICATION"
