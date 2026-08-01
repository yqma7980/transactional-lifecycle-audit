"""Corrected L2-D3.0b TG-02 implementation contract.

Importing this module performs no case execution or file-system writes.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json
import math
from typing import Any

from .l2_d3_tangent_path import (
    AUTHORITATIVE_COMMITTED_HASH,
    EVENT_LOG_COLUMNS,
    TangentEvaluationPacket,
    TangentPath,
    TangentPathComparison,
    classify_tangent_case as classify_original_d3_case,
    execute_tangent_path_case as execute_original_d3_case,
    load_frozen_design,
)
from .l2_state import CommittedState


DESIGN_VERSION = "L2-D3.0"
IMPLEMENTATION_REVISION = "L2-D3.0b"
HOST_VERSION = "L2-HOST-D3.0b"
IMPLEMENTATION_STATUS = (
    "CORRECTED_IMPLEMENTED_UNIT_TESTED_NOT_FORMALLY_EXECUTED"
)
AUTHORIZED_CASES = ("L2-TG-02",)
EXPECTED_CLASSIFICATION = "PASS_DECLARED_LAGGED_TANGENT_PARITY"
CORRECTIVE_REPLAY_CLASSIFICATION = "CORRECTIVE_REPLAY_EXPECTED_PASS"
ABSOLUTE_TOLERANCE = 1e-12
RELATIVE_TOLERANCE = 1e-12
FINITE_LIMIT = 1e100
CORRECTION_FREEZE_NAME = "L2_D3b_correction_freeze.json"


@dataclass(frozen=True)
class AcceptedFieldAudit:
    u_delta: float
    sigma_delta: float
    epsilon_p_delta: float
    kappa_delta: float
    force_delta: float
    u_equal: bool
    sigma_equal: bool
    epsilon_p_equal: bool
    kappa_equal: bool
    force_equal: bool

    @property
    def all_equal(self) -> bool:
        return all(
            (
                self.u_equal,
                self.sigma_equal,
                self.epsilon_p_equal,
                self.kappa_equal,
                self.force_equal,
            )
        )


@dataclass(frozen=True)
class CorrectedTangentPathComparison:
    case_id: str
    left_id: str
    right_id: str
    left_evaluation_count: int
    right_evaluation_count: int
    accepted_fields: AcceptedFieldAudit
    accepted_field_equal: bool
    accepted_fingerprint_equal: bool
    iteration_count_equal: bool
    left_expected_committed_after: str
    right_expected_committed_after: str
    left_committed_transition_valid: bool
    right_committed_transition_valid: bool
    cross_path_committed_fingerprint_equal: bool
    committed_transition_valid: bool
    candidates_unreachable: bool
    all_values_finite: bool
    original_comparison: TangentPathComparison | None


@dataclass(frozen=True)
class CorrectedTangentPathCaseResult:
    design_version: str
    implementation_revision: str
    host_version: str
    case_id: str
    run_id: str
    left_path: TangentPath
    right_path: TangentPath
    comparison: CorrectedTangentPathComparison
    event_log: tuple[dict[str, Any], ...]
    expected_classification: str
    observed_classification: str
    pass_flag: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_correction_freeze(root: str | Path) -> dict[str, Any]:
    benchmark_root = Path(root)
    freeze = json.loads(
        (benchmark_root / CORRECTION_FREEZE_NAME).read_text(encoding="utf-8")
    )
    if freeze.get("design_version") != DESIGN_VERSION:
        raise ValueError("D3b design version mismatch")
    if freeze.get("implementation_revision") != IMPLEMENTATION_REVISION:
        raise ValueError("D3b implementation revision mismatch")
    if freeze.get("host_version") != HOST_VERSION:
        raise ValueError("D3b host version mismatch")
    if freeze.get("execution_authorized") is not False:
        raise ValueError("D3b execution unexpectedly authorized")
    if tuple(freeze.get("supported_formal_cases", ())) != AUTHORIZED_CASES:
        raise ValueError("D3b case allowlist mismatch")
    load_frozen_design(benchmark_root)
    return freeze


def _field_close(left: float, right: float) -> bool:
    return math.isclose(
        left,
        right,
        rel_tol=RELATIVE_TOLERANCE,
        abs_tol=ABSOLUTE_TOLERANCE,
    )


def compare_accepted_fields(
    left: TangentPath,
    right: TangentPath,
) -> AcceptedFieldAudit:
    return AcceptedFieldAudit(
        u_delta=right.accepted_u - left.accepted_u,
        sigma_delta=right.accepted_sigma - left.accepted_sigma,
        epsilon_p_delta=right.accepted_epsilon_p - left.accepted_epsilon_p,
        kappa_delta=right.accepted_kappa - left.accepted_kappa,
        force_delta=right.accepted_force - left.accepted_force,
        u_equal=_field_close(left.accepted_u, right.accepted_u),
        sigma_equal=_field_close(left.accepted_sigma, right.accepted_sigma),
        epsilon_p_equal=_field_close(
            left.accepted_epsilon_p,
            right.accepted_epsilon_p,
        ),
        kappa_equal=_field_close(left.accepted_kappa, right.accepted_kappa),
        force_equal=_field_close(left.accepted_force, right.accepted_force),
    )


def expected_committed_after(path: TangentPath) -> str:
    return CommittedState(
        epsilon_p=path.accepted_epsilon_p,
        kappa=path.accepted_kappa,
        accepted_version=1,
    ).fingerprint


def path_committed_transition_valid(path: TangentPath) -> bool:
    accepted_packets = tuple(packet for packet in path.packets if packet.accepted)
    accepted_candidate_committed = (
        len(accepted_packets) == 1
        and path.packets[-1].accepted
        and path.committed_fingerprint_after == expected_committed_after(path)
    )
    return (
        path.committed_fingerprint_before == AUTHORITATIVE_COMMITTED_HASH
        and accepted_candidate_committed
        and path.candidates_unreachable_after_accept
    )


def compare_tg02_paths(
    left: TangentPath,
    right: TangentPath,
    *,
    original_comparison: TangentPathComparison | None = None,
) -> CorrectedTangentPathComparison:
    if left.case_id != "L2-TG-02" or right.case_id != "L2-TG-02":
        raise ValueError("D3b comparison only supports L2-TG-02")
    fields = compare_accepted_fields(left, right)
    left_valid = path_committed_transition_valid(left)
    right_valid = path_committed_transition_valid(right)
    candidates_unreachable = (
        left.candidates_unreachable_after_accept
        and right.candidates_unreachable_after_accept
    )
    return CorrectedTangentPathComparison(
        case_id="L2-TG-02",
        left_id=left.path_id,
        right_id=right.path_id,
        left_evaluation_count=left.evaluation_count,
        right_evaluation_count=right.evaluation_count,
        accepted_fields=fields,
        accepted_field_equal=fields.all_equal,
        accepted_fingerprint_equal=(
            left.accepted_fingerprint == right.accepted_fingerprint
        ),
        iteration_count_equal=left.evaluation_count == right.evaluation_count,
        left_expected_committed_after=expected_committed_after(left),
        right_expected_committed_after=expected_committed_after(right),
        left_committed_transition_valid=left_valid,
        right_committed_transition_valid=right_valid,
        cross_path_committed_fingerprint_equal=(
            left.committed_fingerprint_after
            == right.committed_fingerprint_after
        ),
        committed_transition_valid=left_valid and right_valid,
        candidates_unreachable=candidates_unreachable,
        all_values_finite=(
            left.all_values_finite
            and right.all_values_finite
            and all(
                math.isfinite(value) and abs(value) <= FINITE_LIMIT
                for value in (
                    fields.u_delta,
                    fields.sigma_delta,
                    fields.epsilon_p_delta,
                    fields.kappa_delta,
                    fields.force_delta,
                )
            )
        ),
        original_comparison=original_comparison,
    )


def classify_tg02(
    comparison: CorrectedTangentPathComparison,
) -> tuple[str, bool]:
    passed = (
        comparison.accepted_field_equal
        and comparison.left_evaluation_count == 3
        and comparison.right_evaluation_count == 4
        and not comparison.iteration_count_equal
        and comparison.left_committed_transition_valid
        and comparison.right_committed_transition_valid
        and comparison.candidates_unreachable
        and comparison.all_values_finite
    )
    return (
        EXPECTED_CLASSIFICATION
        if passed
        else "FAIL_DECLARED_LAGGED_TANGENT_PARITY",
        passed,
    )


def original_tg01_exact_rule_is_unchanged(
    comparison: TangentPathComparison,
) -> bool:
    _, passed = classify_original_d3_case("L2-TG-01", comparison)
    return passed


def _path_from_dict(payload: dict[str, Any]) -> TangentPath:
    packets = tuple(
        TangentEvaluationPacket(**packet) for packet in payload["packets"]
    )
    return TangentPath(
        case_id=payload["case_id"],
        path_id=payload["path_id"],
        tangent_contract=payload["tangent_contract"],
        packets=packets,
        evaluation_count=payload["evaluation_count"],
        correction_count=payload["correction_count"],
        committed_fingerprint_before=payload["committed_fingerprint_before"],
        committed_fingerprint_after=payload["committed_fingerprint_after"],
        accepted_u=payload["accepted_u"],
        accepted_force=payload["accepted_force"],
        accepted_sigma=payload["accepted_sigma"],
        accepted_epsilon_p=payload["accepted_epsilon_p"],
        accepted_kappa=payload["accepted_kappa"],
        accepted_fingerprint=payload["accepted_fingerprint"],
        candidates_unreachable_after_accept=(
            payload["candidates_unreachable_after_accept"]
        ),
        all_values_finite=payload["all_values_finite"],
    )


def corrective_replay_from_payload(
    payload: dict[str, Any],
) -> CorrectedTangentPathCaseResult:
    if payload.get("case_id") != "L2-TG-02":
        raise ValueError("Corrective replay only accepts preserved TG-02")
    left = _path_from_dict(payload["left_path"])
    right = _path_from_dict(payload["right_path"])
    original = TangentPathComparison(**payload["comparison"])
    comparison = compare_tg02_paths(
        left,
        right,
        original_comparison=original,
    )
    _, passed = classify_tg02(comparison)
    observed = (
        CORRECTIVE_REPLAY_CLASSIFICATION
        if passed
        else "CORRECTIVE_REPLAY_EXPECTED_FAIL"
    )
    return CorrectedTangentPathCaseResult(
        design_version=DESIGN_VERSION,
        implementation_revision=IMPLEMENTATION_REVISION,
        host_version=HOST_VERSION,
        case_id="L2-TG-02",
        run_id=payload["run_id"],
        left_path=left,
        right_path=right,
        comparison=comparison,
        event_log=tuple(payload.get("event_log", ())),
        expected_classification=EXPECTED_CLASSIFICATION,
        observed_classification=observed,
        pass_flag=passed,
    )


def execute_tangent_path_case(
    root: str | Path,
    case_id: str,
    run_id: str,
) -> CorrectedTangentPathCaseResult:
    if case_id not in AUTHORIZED_CASES:
        raise ValueError(f"Unauthorized L2-D3b case: {case_id}")
    if not run_id or not run_id.strip():
        raise ValueError("run_id must be non-empty")
    load_correction_freeze(root)
    original = execute_original_d3_case(root, case_id, run_id)
    if original.left_path is None or original.right_path is None:
        raise RuntimeError("TG-02 paths are missing")
    comparison = compare_tg02_paths(
        original.left_path,
        original.right_path,
        original_comparison=original.comparison,
    )
    observed, passed = classify_tg02(comparison)
    return CorrectedTangentPathCaseResult(
        design_version=DESIGN_VERSION,
        implementation_revision=IMPLEMENTATION_REVISION,
        host_version=HOST_VERSION,
        case_id=case_id,
        run_id=run_id,
        left_path=original.left_path,
        right_path=original.right_path,
        comparison=comparison,
        event_log=original.event_log,
        expected_classification=EXPECTED_CLASSIFICATION,
        observed_classification=observed,
        pass_flag=passed,
    )
