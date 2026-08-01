"""Frozen L2-D3.0 tangent-path benchmark implementation.

Importing this module performs no benchmark execution, file creation, logging,
environment mutation, or process/thread initialization.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import csv
import hashlib
import json
import math
from typing import Any

from .l2_model import evaluate_element
from .l2_state import (
    CommittedState,
    ElementData,
    ElementResult,
    MaterialData,
    canonical_hash,
    canonical_json,
)
from .l2_variants import VARIANTS


DESIGN_VERSION = "L2-D3.0"
HOST_VERSION = "L2-HOST-D3.0"
IMPLEMENTATION_STATUS = "IMPLEMENTED_NOT_EXECUTED"
FREEZE_SHA256 = (
    "03ebd4eb92fca4cb9300be4192cdd73b5575f9798b9c46f90bd618f7dc85cbcc"
)
CASE_MATRIX_SHA256 = (
    "665576bd3e9f66c0ed8152a4fde4cc69d1b82ab810202e666340f234ec2f5c64"
)
AUTHORITATIVE_COMMITTED_HASH = (
    "f5045dd74424efe25edaaebfa84802eeba5e8ca376816835f58145764a2efc01"
)
AUTHORIZED_CASES = ("L2-TG-01", "L2-TG-02", "L2-TG-03")
EXPECTED_CLASSIFICATIONS = {
    "L2-TG-01": "PASS_SAME_TRACK_REPEATABILITY",
    "L2-TG-02": "PASS_DECLARED_LAGGED_TANGENT_PARITY",
    "L2-TG-03": "REJECT_VERSION_MISMATCH_BEFORE_LIFECYCLE_VERDICT",
}
EVENT_LOG_COLUMNS = (
    "case_id",
    "run_id",
    "path_id",
    "event",
    "evaluation",
    "u",
    "force",
    "residual",
    "current_tangent",
    "used_tangent",
    "correction",
    "candidate_fingerprint",
    "residual_state_version",
    "tangent_state_version",
    "version_relation",
    "version_compatible",
    "committed_fingerprint",
    "candidate_reachable",
    "accepted",
    "all_values_finite",
)
PATH_COMPARISON_COLUMNS = (
    "case_id",
    "run_id",
    "left_id",
    "right_id",
    "left_evaluation_count",
    "right_evaluation_count",
    "packet_semantic_equal",
    "accepted_field_equal",
    "accepted_fingerprint_equal",
    "iteration_count_equal",
    "matched_version_compatible",
    "mismatched_version_compatible",
    "numeric_residual_delta",
    "numeric_tangent_delta",
    "committed_state_unchanged",
    "committed_transition_valid",
    "candidates_unreachable",
    "all_values_finite",
    "classification",
    "pass_flag",
)


@dataclass(frozen=True)
class TangentEvaluationPacket:
    evaluation: int
    u: float
    force: float
    residual: float
    current_tangent: float
    used_tangent: float
    correction: float | None
    candidate_epsilon_p: float
    candidate_kappa: float
    candidate_fingerprint: str
    residual_state_version: str
    tangent_state_version: str
    version_relation: str
    version_compatible: bool
    accepted: bool
    all_values_finite: bool

    @property
    def semantic_fingerprint(self) -> str:
        """Hash physical iteration content without path-specific labels."""

        return canonical_hash(
            {
                "evaluation": self.evaluation,
                "u": self.u,
                "force": self.force,
                "residual": self.residual,
                "current_tangent": self.current_tangent,
                "used_tangent": self.used_tangent,
                "correction": self.correction,
                "candidate_epsilon_p": self.candidate_epsilon_p,
                "candidate_kappa": self.candidate_kappa,
                "candidate_fingerprint": self.candidate_fingerprint,
                "version_relation": self.version_relation,
                "version_compatible": self.version_compatible,
                "accepted": self.accepted,
            }
        )


@dataclass(frozen=True)
class TangentPath:
    case_id: str
    path_id: str
    tangent_contract: str
    packets: tuple[TangentEvaluationPacket, ...]
    evaluation_count: int
    correction_count: int
    committed_fingerprint_before: str
    committed_fingerprint_after: str
    accepted_u: float
    accepted_force: float
    accepted_sigma: float
    accepted_epsilon_p: float
    accepted_kappa: float
    accepted_fingerprint: str
    candidates_unreachable_after_accept: bool
    all_values_finite: bool

    @property
    def semantic_ledger(self) -> tuple[str, ...]:
        return tuple(packet.semantic_fingerprint for packet in self.packets)


@dataclass(frozen=True)
class VersionedOperatorPacket:
    case_id: str
    history_id: str
    u: float
    force: float
    residual: float
    tangent: float
    sigma: float
    candidate_epsilon_p: float
    candidate_kappa: float
    candidate_fingerprint: str
    residual_state_version: str
    tangent_state_version: str
    declared_version_relation: str
    version_compatible: bool
    correction_applied: bool
    committed_fingerprint_before: str
    committed_fingerprint_after: str
    candidate_reachable_after_reject: bool
    accepted_output_reachable: bool
    all_values_finite: bool

    @property
    def numeric_fingerprint(self) -> str:
        return canonical_hash(
            {
                "u": self.u,
                "force": self.force,
                "residual": self.residual,
                "tangent": self.tangent,
                "sigma": self.sigma,
                "candidate_epsilon_p": self.candidate_epsilon_p,
                "candidate_kappa": self.candidate_kappa,
            }
        )


@dataclass(frozen=True)
class TangentPathComparison:
    case_id: str
    left_id: str
    right_id: str
    left_evaluation_count: int
    right_evaluation_count: int
    packet_semantic_equal: bool
    accepted_field_equal: bool
    accepted_fingerprint_equal: bool
    iteration_count_equal: bool
    matched_version_compatible: bool | None
    mismatched_version_compatible: bool | None
    numeric_residual_delta: float | None
    numeric_tangent_delta: float | None
    committed_state_unchanged: bool
    committed_transition_valid: bool
    candidates_unreachable: bool
    all_values_finite: bool


@dataclass(frozen=True)
class TangentPathCaseResult:
    design_version: str
    host_version: str
    case_id: str
    run_id: str
    left_path: TangentPath | None
    right_path: TangentPath | None
    matched_operator: VersionedOperatorPacket | None
    mismatched_operator: VersionedOperatorPacket | None
    comparison: TangentPathComparison
    event_log: tuple[dict[str, Any], ...]
    expected_classification: str
    observed_classification: str
    pass_flag: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_frozen_design(
    root: str | Path,
) -> tuple[dict[str, Any], tuple[dict[str, str], ...]]:
    """Load the immutable D3 freeze without executing a benchmark case."""

    benchmark_root = Path(root)
    freeze_path = benchmark_root / "L2_D3_execution_freeze.json"
    matrix_path = benchmark_root / "L2_D3_tangent_path_case_matrix.csv"
    if _sha256_file(freeze_path) != FREEZE_SHA256:
        raise ValueError("L2-D3 freeze hash mismatch")
    if _sha256_file(matrix_path) != CASE_MATRIX_SHA256:
        raise ValueError("L2-D3 case matrix hash mismatch")
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    with matrix_path.open("r", encoding="utf-8-sig", newline="") as stream:
        matrix = tuple(dict(row) for row in csv.DictReader(stream))
    validate_frozen_design(freeze, matrix)
    return freeze, matrix


def validate_frozen_design(
    freeze: dict[str, Any],
    matrix: tuple[dict[str, str], ...],
) -> None:
    """Reject any design drift from the authorized L2-D3.0 freeze."""

    required = {
        "design_version": DESIGN_VERSION,
        "host_version_reused": "L2-HOST-D1.0",
        "extension_version_if_implemented": HOST_VERSION,
        "design_status": "FROZEN_NOT_IMPLEMENTED",
        "execution_authorized": False,
        "abaqus_used": False,
        "results_exist": False,
        "committed_state_serializer": (
            "src.l2_state.canonical_json(CommittedState())"
        ),
    }
    for key, expected in required.items():
        if freeze.get(key) != expected:
            raise ValueError(f"Frozen design mismatch for {key!r}")

    committed = CommittedState()
    declared = freeze.get("declared_committed_state", {})
    if canonical_json(committed) != declared.get("canonical_payload_utf8"):
        raise ValueError("Committed-state canonical payload mismatch")
    if committed.fingerprint != AUTHORITATIVE_COMMITTED_HASH:
        raise ValueError("D1 committed-state serializer identity mismatch")
    if declared.get("sha256") != AUTHORITATIVE_COMMITTED_HASH:
        raise ValueError("Frozen committed-state fingerprint mismatch")

    case_ids = tuple(row.get("case_id", "") for row in matrix)
    if case_ids != AUTHORIZED_CASES or len(set(case_ids)) != len(case_ids):
        raise ValueError("Case matrix must contain exactly L2-TG-01/02/03")
    for row in matrix:
        case_id = row["case_id"]
        if row.get("expected_classification") != EXPECTED_CLASSIFICATIONS[case_id]:
            raise ValueError(f"Classification mismatch for {case_id}")
        if row.get("execution_authorized", "").lower() != "false":
            raise ValueError(f"Execution unexpectedly authorized for {case_id}")
    frozen_cases = tuple(freeze.get("scope", {}).get("authorized_design_cases", ()))
    if frozen_cases != AUTHORIZED_CASES:
        raise ValueError("Frozen case scope mismatch")

    oracle = freeze.get("analytical_oracle", {})
    if oracle.get("L2-TG-02", {}).get("exact_evaluation_count") != 3:
        raise ValueError("TG-02 exact path count drift")
    if oracle.get("L2-TG-02", {}).get("declared_lagged_evaluation_count") != 4:
        raise ValueError("TG-02 lagged path count drift")
    if oracle.get("L2-TG-03", {}).get("residual") != "15/22":
        raise ValueError("TG-03 residual oracle drift")
    if oracle.get("L2-TG-03", {}).get("tangent") != "100/11":
        raise ValueError("TG-03 tangent oracle drift")


def _physical_candidate_fingerprint(result: ElementResult) -> str:
    return canonical_hash(
        {
            "epsilon_p": result.candidate.epsilon_p,
            "kappa": result.candidate.kappa,
        }
    )


def _finite(values: tuple[float, ...], limit: float) -> bool:
    return all(math.isfinite(value) and abs(value) <= limit for value in values)


def _configuration_hash(material: MaterialData, element: ElementData) -> str:
    return canonical_hash(
        {
            "design_version": DESIGN_VERSION,
            "host_version": HOST_VERSION,
            "material_fingerprint": material.fingerprint,
            "element_fingerprint": element.fingerprint,
            "committed_state_fingerprint": CommittedState().fingerprint,
        }
    )


def _build_path(
    freeze: dict[str, Any],
    *,
    case_id: str,
    path_id: str,
    tangent_contract: str,
    material: MaterialData,
    element: ElementData,
    configuration_hash: str,
) -> TangentPath:
    if case_id not in {"L2-TG-01", "L2-TG-02"}:
        raise ValueError("A Newton path is only defined for TG-01/02")
    if tangent_contract not in {"EXACT_CURRENT", "DECLARED_ONE_ITERATION_LAG"}:
        raise ValueError("Unsupported tangent contract")

    variant = VARIANTS["safe_transactional"](material)
    committed_before = variant.committed.fingerprint
    if committed_before != AUTHORITATIVE_COMMITTED_HASH:
        raise ValueError("Path did not start from the authoritative state")
    attempt_id = f"{case_id}:{path_id}:attempt"
    variant.begin_attempt(attempt_id)

    target = freeze["common_equilibrium_target"]
    force = float(target["force"].split("/")[0]) / float(
        target["force"].split("/")[1]
    )
    tolerance = float(freeze["host"]["absolute_residual_tolerance"])
    tangent_floor = float(freeze["host"]["tangent_floor"])
    finite_limit = float(freeze["tolerances"]["finite_absolute_limit"])
    maximum = int(freeze["host"]["max_newton_evaluations"])
    u = float(target["initial_primary_state_u"].split("/")[0]) / float(
        target["initial_primary_state_u"].split("/")[1]
    )
    previous_current_tangent = material.E
    packets: list[TangentEvaluationPacket] = []
    candidate_ids: list[str] = []
    accepted_result: ElementResult | None = None

    for evaluation in range(1, maximum + 1):
        candidate_id = f"{case_id}:{path_id}:candidate:{evaluation}"
        result = evaluate_element(
            variant,
            element,
            case_id=case_id,
            history_id=path_id,
            configuration_hash=configuration_hash,
            displacement=u,
            force=force,
            candidate_id=candidate_id,
            attempt_id=attempt_id,
            source_call_index=evaluation,
        )
        candidate_ids.append(candidate_id)
        current_tangent = result.tangent
        current_version = f"{path_id}:trial:{evaluation}"
        if tangent_contract == "EXACT_CURRENT":
            used_tangent = current_tangent
            tangent_version = current_version
            relation = "MATCHED_SAME_STATE"
        else:
            used_tangent = previous_current_tangent
            tangent_version = (
                "accepted:0"
                if evaluation == 1
                else f"{path_id}:trial:{evaluation - 1}"
            )
            relation = "EXPLICITLY_DECLARED_LAG1"
        if abs(used_tangent) <= tangent_floor:
            variant.reject_attempt(attempt_id)
            raise ZeroDivisionError("Frozen tangent floor violated")

        converged = abs(result.residual) <= tolerance
        correction = None if converged else -result.residual / used_tangent
        values = (
            result.u,
            result.force,
            result.residual,
            current_tangent,
            used_tangent,
            result.sigma,
            result.candidate.epsilon_p,
            result.candidate.kappa,
        )
        packet = TangentEvaluationPacket(
            evaluation=evaluation,
            u=result.u,
            force=result.force,
            residual=result.residual,
            current_tangent=current_tangent,
            used_tangent=used_tangent,
            correction=correction,
            candidate_epsilon_p=result.candidate.epsilon_p,
            candidate_kappa=result.candidate.kappa,
            candidate_fingerprint=_physical_candidate_fingerprint(result),
            residual_state_version=current_version,
            tangent_state_version=tangent_version,
            version_relation=relation,
            version_compatible=(
                current_version == tangent_version
                or relation == "EXPLICITLY_DECLARED_LAG1"
            ),
            accepted=converged,
            all_values_finite=_finite(values, finite_limit),
        )
        packets.append(packet)
        if not packet.all_values_finite:
            variant.reject_attempt(attempt_id)
            raise FloatingPointError("Non-finite tangent-path packet")
        if converged:
            accepted, reason = variant.accept(result.candidate)
            if not accepted:
                raise RuntimeError(f"Final candidate was not accepted: {reason}")
            accepted_result = result
            break
        previous_current_tangent = current_tangent
        u += correction
    else:
        variant.reject_attempt(attempt_id)
        raise RuntimeError("Frozen Newton path did not converge")

    if accepted_result is None:
        raise RuntimeError("Accepted result missing")
    committed_after = variant.committed.fingerprint
    candidates_unreachable = all(
        not variant.candidate_reachable(candidate_id)
        for candidate_id in candidate_ids
    )
    accepted_fingerprint = canonical_hash(
        {
            "u": accepted_result.u,
            "force": accepted_result.force,
            "sigma": accepted_result.sigma,
            "epsilon_p": variant.committed.epsilon_p,
            "kappa": variant.committed.kappa,
            "accepted_version": variant.committed.accepted_version,
            "committed_fingerprint": committed_after,
        }
    )
    return TangentPath(
        case_id=case_id,
        path_id=path_id,
        tangent_contract=tangent_contract,
        packets=tuple(packets),
        evaluation_count=len(packets),
        correction_count=sum(packet.correction is not None for packet in packets),
        committed_fingerprint_before=committed_before,
        committed_fingerprint_after=committed_after,
        accepted_u=accepted_result.u,
        accepted_force=accepted_result.force,
        accepted_sigma=accepted_result.sigma,
        accepted_epsilon_p=variant.committed.epsilon_p,
        accepted_kappa=variant.committed.kappa,
        accepted_fingerprint=accepted_fingerprint,
        candidates_unreachable_after_accept=candidates_unreachable,
        all_values_finite=all(packet.all_values_finite for packet in packets),
    )


def build_exact_path(
    freeze: dict[str, Any],
    *,
    case_id: str,
    path_id: str,
    material: MaterialData | None = None,
    element: ElementData | None = None,
    configuration_hash: str | None = None,
) -> TangentPath:
    material = material or MaterialData()
    element = element or ElementData()
    return _build_path(
        freeze,
        case_id=case_id,
        path_id=path_id,
        tangent_contract="EXACT_CURRENT",
        material=material,
        element=element,
        configuration_hash=configuration_hash or _configuration_hash(material, element),
    )


def build_declared_lagged_path(
    freeze: dict[str, Any],
    *,
    case_id: str,
    path_id: str,
    material: MaterialData | None = None,
    element: ElementData | None = None,
    configuration_hash: str | None = None,
) -> TangentPath:
    material = material or MaterialData()
    element = element or ElementData()
    return _build_path(
        freeze,
        case_id=case_id,
        path_id=path_id,
        tangent_contract="DECLARED_ONE_ITERATION_LAG",
        material=material,
        element=element,
        configuration_hash=configuration_hash or _configuration_hash(material, element),
    )


def validate_operator_versions(packet: VersionedOperatorPacket) -> bool:
    if packet.residual_state_version == packet.tangent_state_version:
        return True
    return packet.declared_version_relation == "EXPLICITLY_DECLARED_LAG1"


def _build_tg03_packet(
    *,
    history_id: str,
    residual_state_version: str,
    tangent_state_version: str,
    declared_relation: str,
    material: MaterialData,
    element: ElementData,
    configuration_hash: str,
    finite_limit: float,
) -> VersionedOperatorPacket:
    variant = VARIANTS["safe_transactional"](material)
    committed_before = variant.committed.fingerprint
    attempt_id = f"L2-TG-03:{history_id}:attempt"
    candidate_id = f"L2-TG-03:{history_id}:candidate:1"
    variant.begin_attempt(attempt_id)
    result = evaluate_element(
        variant,
        element,
        case_id="L2-TG-03",
        history_id=history_id,
        configuration_hash=configuration_hash,
        displacement=3.0 / 100.0,
        force=1.0 / 2.0,
        candidate_id=candidate_id,
        attempt_id=attempt_id,
        source_call_index=1,
    )
    variant.reject_attempt(attempt_id)
    packet_values = (
        result.u,
        result.force,
        result.residual,
        result.tangent,
        result.sigma,
        result.candidate.epsilon_p,
        result.candidate.kappa,
    )
    provisional = VersionedOperatorPacket(
        case_id="L2-TG-03",
        history_id=history_id,
        u=result.u,
        force=result.force,
        residual=result.residual,
        tangent=result.tangent,
        sigma=result.sigma,
        candidate_epsilon_p=result.candidate.epsilon_p,
        candidate_kappa=result.candidate.kappa,
        candidate_fingerprint=_physical_candidate_fingerprint(result),
        residual_state_version=residual_state_version,
        tangent_state_version=tangent_state_version,
        declared_version_relation=declared_relation,
        version_compatible=False,
        correction_applied=False,
        committed_fingerprint_before=committed_before,
        committed_fingerprint_after=variant.committed.fingerprint,
        candidate_reachable_after_reject=variant.candidate_reachable(candidate_id),
        accepted_output_reachable=False,
        all_values_finite=_finite(packet_values, finite_limit),
    )
    return VersionedOperatorPacket(
        **{
            **asdict(provisional),
            "version_compatible": validate_operator_versions(provisional),
        }
    )


def build_tg03_packets(
    freeze: dict[str, Any],
    *,
    material: MaterialData | None = None,
    element: ElementData | None = None,
    configuration_hash: str | None = None,
) -> tuple[VersionedOperatorPacket, VersionedOperatorPacket]:
    material = material or MaterialData()
    element = element or ElementData()
    configuration_hash = configuration_hash or _configuration_hash(material, element)
    finite_limit = float(freeze["tolerances"]["finite_absolute_limit"])
    matched = _build_tg03_packet(
        history_id="TG03_MATCHED",
        residual_state_version="trial:TG03:1",
        tangent_state_version="trial:TG03:1",
        declared_relation="MATCHED_SAME_STATE",
        material=material,
        element=element,
        configuration_hash=configuration_hash,
        finite_limit=finite_limit,
    )
    mismatched = _build_tg03_packet(
        history_id="TG03_MISMATCH",
        residual_state_version="trial:TG03:1",
        tangent_state_version="trial:TG03:seeded_other",
        declared_relation="NONE",
        material=material,
        element=element,
        configuration_hash=configuration_hash,
        finite_limit=finite_limit,
    )
    return matched, mismatched


def _within_tolerance(actual: float, expected: float, tolerance: float) -> bool:
    return abs(actual - expected) <= tolerance


def compare_tangent_paths(
    left: TangentPath,
    right: TangentPath,
    *,
    case_id: str,
    tolerance: float,
) -> TangentPathComparison:
    accepted_deltas = (
        left.accepted_u - right.accepted_u,
        left.accepted_force - right.accepted_force,
        left.accepted_sigma - right.accepted_sigma,
        left.accepted_epsilon_p - right.accepted_epsilon_p,
        left.accepted_kappa - right.accepted_kappa,
    )
    accepted_equal = all(
        _within_tolerance(delta, 0.0, tolerance) for delta in accepted_deltas
    )
    return TangentPathComparison(
        case_id=case_id,
        left_id=left.path_id,
        right_id=right.path_id,
        left_evaluation_count=left.evaluation_count,
        right_evaluation_count=right.evaluation_count,
        packet_semantic_equal=left.semantic_ledger == right.semantic_ledger,
        accepted_field_equal=accepted_equal,
        accepted_fingerprint_equal=(
            left.accepted_fingerprint == right.accepted_fingerprint
        ),
        iteration_count_equal=left.evaluation_count == right.evaluation_count,
        matched_version_compatible=None,
        mismatched_version_compatible=None,
        numeric_residual_delta=None,
        numeric_tangent_delta=None,
        committed_state_unchanged=(
            left.committed_fingerprint_before
            == left.committed_fingerprint_after
            and right.committed_fingerprint_before
            == right.committed_fingerprint_after
        ),
        committed_transition_valid=(
            left.committed_fingerprint_before == AUTHORITATIVE_COMMITTED_HASH
            and right.committed_fingerprint_before == AUTHORITATIVE_COMMITTED_HASH
            and left.committed_fingerprint_after
            == right.committed_fingerprint_after
            and left.committed_fingerprint_after != AUTHORITATIVE_COMMITTED_HASH
        ),
        candidates_unreachable=(
            left.candidates_unreachable_after_accept
            and right.candidates_unreachable_after_accept
        ),
        all_values_finite=left.all_values_finite and right.all_values_finite,
    )


def _compare_tg03(
    matched: VersionedOperatorPacket,
    mismatched: VersionedOperatorPacket,
) -> TangentPathComparison:
    return TangentPathComparison(
        case_id="L2-TG-03",
        left_id=matched.history_id,
        right_id=mismatched.history_id,
        left_evaluation_count=1,
        right_evaluation_count=1,
        packet_semantic_equal=(
            matched.numeric_fingerprint == mismatched.numeric_fingerprint
        ),
        accepted_field_equal=False,
        accepted_fingerprint_equal=False,
        iteration_count_equal=True,
        matched_version_compatible=matched.version_compatible,
        mismatched_version_compatible=mismatched.version_compatible,
        numeric_residual_delta=mismatched.residual - matched.residual,
        numeric_tangent_delta=mismatched.tangent - matched.tangent,
        committed_state_unchanged=(
            matched.committed_fingerprint_before
            == matched.committed_fingerprint_after
            == mismatched.committed_fingerprint_before
            == mismatched.committed_fingerprint_after
            == AUTHORITATIVE_COMMITTED_HASH
        ),
        committed_transition_valid=(
            matched.committed_fingerprint_before
            == matched.committed_fingerprint_after
            == mismatched.committed_fingerprint_before
            == mismatched.committed_fingerprint_after
            == AUTHORITATIVE_COMMITTED_HASH
        ),
        candidates_unreachable=(
            not matched.candidate_reachable_after_reject
            and not mismatched.candidate_reachable_after_reject
            and not matched.accepted_output_reachable
            and not mismatched.accepted_output_reachable
        ),
        all_values_finite=(
            matched.all_values_finite and mismatched.all_values_finite
        ),
    )


def classify_tangent_case(
    case_id: str,
    comparison: TangentPathComparison,
) -> tuple[str, bool]:
    if case_id == "L2-TG-01":
        passed = (
            comparison.packet_semantic_equal
            and comparison.accepted_field_equal
            and comparison.accepted_fingerprint_equal
            and comparison.iteration_count_equal
            and comparison.left_evaluation_count == 3
            and comparison.right_evaluation_count == 3
            and comparison.committed_transition_valid
            and comparison.candidates_unreachable
            and comparison.all_values_finite
        )
        return (
            "PASS_SAME_TRACK_REPEATABILITY"
            if passed
            else "FAIL_SAME_TRACK_REPEATABILITY",
            passed,
        )
    if case_id == "L2-TG-02":
        passed = (
            comparison.accepted_field_equal
            and comparison.accepted_fingerprint_equal
            and not comparison.iteration_count_equal
            and comparison.left_evaluation_count == 3
            and comparison.right_evaluation_count == 4
            and comparison.committed_transition_valid
            and comparison.candidates_unreachable
            and comparison.all_values_finite
        )
        return (
            "PASS_DECLARED_LAGGED_TANGENT_PARITY"
            if passed
            else "FAIL_DECLARED_LAGGED_TANGENT_PARITY",
            passed,
        )
    if case_id == "L2-TG-03":
        passed = (
            comparison.packet_semantic_equal
            and comparison.matched_version_compatible is True
            and comparison.mismatched_version_compatible is False
            and comparison.numeric_residual_delta == 0.0
            and comparison.numeric_tangent_delta == 0.0
            and comparison.committed_state_unchanged
            and comparison.committed_transition_valid
            and comparison.candidates_unreachable
            and comparison.all_values_finite
        )
        return (
            (
                "REJECT_VERSION_MISMATCH_BEFORE_LIFECYCLE_VERDICT"
                if passed
                else "FAIL_TO_REJECT_VERSION_MISMATCH"
            ),
            passed,
        )
    raise ValueError(f"Unauthorized L2-D3 case: {case_id}")


def _path_event_rows(
    case_id: str,
    run_id: str,
    path: TangentPath,
) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    for packet in path.packets:
        rows.append(
            {
                "case_id": case_id,
                "run_id": run_id,
                "path_id": path.path_id,
                "event": "TrialEvaluateAndFormOperators",
                "evaluation": packet.evaluation,
                "u": packet.u,
                "force": packet.force,
                "residual": packet.residual,
                "current_tangent": packet.current_tangent,
                "used_tangent": packet.used_tangent,
                "correction": packet.correction,
                "candidate_fingerprint": packet.candidate_fingerprint,
                "residual_state_version": packet.residual_state_version,
                "tangent_state_version": packet.tangent_state_version,
                "version_relation": packet.version_relation,
                "version_compatible": packet.version_compatible,
                "committed_fingerprint": (
                    path.committed_fingerprint_after
                    if packet.accepted
                    else path.committed_fingerprint_before
                ),
                "candidate_reachable": False,
                "accepted": packet.accepted,
                "all_values_finite": packet.all_values_finite,
            }
        )
    return tuple(rows)


def _operator_event_row(
    run_id: str,
    packet: VersionedOperatorPacket,
) -> dict[str, Any]:
    return {
        "case_id": packet.case_id,
        "run_id": run_id,
        "path_id": packet.history_id,
        "event": (
            "RejectBeforeCorrection"
            if not packet.version_compatible
            else "ValidateVersionCompatibility"
        ),
        "evaluation": 1,
        "u": packet.u,
        "force": packet.force,
        "residual": packet.residual,
        "current_tangent": packet.tangent,
        "used_tangent": packet.tangent,
        "correction": None,
        "candidate_fingerprint": packet.candidate_fingerprint,
        "residual_state_version": packet.residual_state_version,
        "tangent_state_version": packet.tangent_state_version,
        "version_relation": packet.declared_version_relation,
        "version_compatible": packet.version_compatible,
        "committed_fingerprint": packet.committed_fingerprint_after,
        "candidate_reachable": packet.candidate_reachable_after_reject,
        "accepted": False,
        "all_values_finite": packet.all_values_finite,
    }


def execute_tangent_path_case(
    root: str | Path,
    case_id: str,
    run_id: str,
) -> TangentPathCaseResult:
    """Execute one future-authorized in-memory case without writing outputs."""

    if case_id not in AUTHORIZED_CASES:
        raise ValueError(f"Unauthorized L2-D3 case: {case_id}")
    if not run_id or not run_id.strip():
        raise ValueError("run_id must be a non-empty independent-process label")
    freeze, matrix = load_frozen_design(root)
    row = next(item for item in matrix if item["case_id"] == case_id)
    if row["expected_classification"] != EXPECTED_CLASSIFICATIONS[case_id]:
        raise ValueError("Case classification differs from the freeze")

    material = MaterialData()
    element = ElementData()
    configuration_hash = _configuration_hash(material, element)
    tolerance = float(freeze["tolerances"]["analytical_absolute"])
    left_path: TangentPath | None = None
    right_path: TangentPath | None = None
    matched: VersionedOperatorPacket | None = None
    mismatched: VersionedOperatorPacket | None = None

    if case_id == "L2-TG-01":
        left_path = build_exact_path(
            freeze,
            case_id=case_id,
            path_id="EXACT_A",
            material=material,
            element=element,
            configuration_hash=configuration_hash,
        )
        right_path = build_exact_path(
            freeze,
            case_id=case_id,
            path_id="EXACT_B",
            material=material,
            element=element,
            configuration_hash=configuration_hash,
        )
        comparison = compare_tangent_paths(
            left_path,
            right_path,
            case_id=case_id,
            tolerance=tolerance,
        )
        event_log = (
            *_path_event_rows(case_id, run_id, left_path),
            *_path_event_rows(case_id, run_id, right_path),
        )
    elif case_id == "L2-TG-02":
        left_path = build_exact_path(
            freeze,
            case_id=case_id,
            path_id="EXACT_CURRENT",
            material=material,
            element=element,
            configuration_hash=configuration_hash,
        )
        right_path = build_declared_lagged_path(
            freeze,
            case_id=case_id,
            path_id="DECLARED_LAG1",
            material=material,
            element=element,
            configuration_hash=configuration_hash,
        )
        comparison = compare_tangent_paths(
            left_path,
            right_path,
            case_id=case_id,
            tolerance=tolerance,
        )
        event_log = (
            *_path_event_rows(case_id, run_id, left_path),
            *_path_event_rows(case_id, run_id, right_path),
        )
    else:
        matched, mismatched = build_tg03_packets(
            freeze,
            material=material,
            element=element,
            configuration_hash=configuration_hash,
        )
        comparison = _compare_tg03(matched, mismatched)
        event_log = (
            _operator_event_row(run_id, matched),
            _operator_event_row(run_id, mismatched),
        )

    observed, passed = classify_tangent_case(case_id, comparison)
    return TangentPathCaseResult(
        design_version=DESIGN_VERSION,
        host_version=HOST_VERSION,
        case_id=case_id,
        run_id=run_id,
        left_path=left_path,
        right_path=right_path,
        matched_operator=matched,
        mismatched_operator=mismatched,
        comparison=comparison,
        event_log=tuple(event_log),
        expected_classification=EXPECTED_CLASSIFICATIONS[case_id],
        observed_classification=observed,
        pass_flag=passed,
    )
