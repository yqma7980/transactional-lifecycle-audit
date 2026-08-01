"""Frozen L2-D2.0a callback-order lifecycle implementation.

Importing this module performs no benchmark execution, file creation, logging,
environment mutation, or process/thread initialization.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from fractions import Fraction
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


DESIGN_VERSION = "L2-D2.0a"
HOST_VERSION = "L2-HOST-D2.0"
IMPLEMENTATION_STATUS = "IMPLEMENTED_NOT_EXECUTED"
AUTHORITATIVE_COMMITTED_HASH = (
    "f5045dd74424efe25edaaebfa84802eeba5e8ca376816835f58145764a2efc01"
)
CASE_MATRIX_SHA256 = (
    "62cdbb90454cea75f9ad6af9ede1d0b444cbdf28ed83abdf51a3658296c77ca5"
)
AUTHORIZED_CASES = ("L2-CO-01", "L2-CO-02")
CASE_VARIANTS = {
    "L2-CO-01": "safe_transactional",
    "L2-CO-02": "unsafe_trial_cache",
}
EXPECTED_CLASSIFICATIONS = {
    "L2-CO-01": "PASS_CALLBACK_INVARIANCE",
    "L2-CO-02": "DETECT_CALLBACK_HISTORY_DRIFT",
}
FORBIDDEN_EVENTS = frozenset(
    {
        "AcceptIncrement",
        "OutputAcceptedState",
        "CheckpointWrite",
        "RestartWrite",
        "RestartRead",
        "CutbackAndRetry",
        "TerminalOrZeroIncrementCall",
    }
)

EVENT_LOG_COLUMNS = (
    "ordinal",
    "history_id",
    "event",
    "attempt_id",
    "candidate_id",
    "u",
    "force",
    "residual",
    "tangent",
    "candidate_fingerprint",
    "persistent_fingerprint",
    "committed_fingerprint",
    "candidate_reachable",
)
REPLAY_COMPARISON_COLUMNS = (
    "case_id",
    "run_id",
    "variant",
    "direct_declared_fingerprint",
    "extra_declared_fingerprint",
    "direct_observed_fingerprint",
    "extra_observed_fingerprint",
    "direct_residual",
    "extra_residual",
    "delta_residual",
    "direct_tangent",
    "extra_tangent",
    "delta_tangent",
    "classification",
    "pass_flag",
)


@dataclass(frozen=True)
class CallbackPacket:
    ordinal: int
    event: str
    attempt_id: str | None = None
    u: Fraction | None = None
    force: Fraction | None = None
    residual_version: str | None = None
    tangent_version: str | None = None
    declared_committed_state_sha256: str | None = None
    accepted_output_reachable: bool | None = None


@dataclass(frozen=True)
class CallbackHistory:
    history_id: str
    packets: tuple[CallbackPacket, ...]


@dataclass(frozen=True)
class ReplayContext:
    u: float
    force: float
    committed_state_fingerprint: str
    residual_version: str
    tangent_version: str

    @property
    def fingerprint(self) -> str:
        return canonical_hash(
            {
                "u": self.u,
                "force": self.force,
                "committed_state_fingerprint": self.committed_state_fingerprint,
                "residual_version": self.residual_version,
                "tangent_version": self.tangent_version,
            }
        )


@dataclass(frozen=True)
class ReplayObservation:
    history_id: str
    attempt_id: str
    declared_context: ReplayContext
    declared_replay_context_fingerprint: str
    observed_replay_fingerprint: str
    residual: float
    tangent: float
    residual_state_version: str
    tangent_state_version: str
    candidate_state_fingerprint: str
    raw_candidate_state_fingerprint: str
    persistent_state_fingerprint: str
    committed_fingerprint_before: str
    committed_fingerprint_after: str
    candidate_reachable_after_reject: bool
    all_values_finite: bool


@dataclass(frozen=True)
class HistoryExecution:
    case_id: str
    variant: str
    history: CallbackHistory
    replay: ReplayObservation
    event_log: tuple[dict[str, Any], ...]
    trial_evaluation_count: int
    committed_fingerprint_before: str
    committed_fingerprint_after: str
    persistent_fingerprint_before: str
    persistent_fingerprint_after: str
    rejected_candidate_ids: tuple[str, ...]
    candidate_reachability_after_reject: tuple[tuple[str, bool], ...]
    accepted_output_candidate_ids: tuple[str, ...]


@dataclass(frozen=True)
class CallbackOrderCaseResult:
    design_version: str
    host_version: str
    case_id: str
    run_id: str
    variant: str
    direct: HistoryExecution
    extra: HistoryExecution
    comparison: dict[str, Any]
    expected_classification: str
    observed_classification: str
    pass_flag: bool

    def to_dict(self) -> dict[str, Any]:
        return _json_ready(asdict(self))


def _json_ready(value: Any) -> Any:
    if isinstance(value, Fraction):
        return f"{value.numerator}/{value.denominator}"
    if isinstance(value, float):
        return value
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fraction(value: str | None) -> Fraction | None:
    return None if value is None else Fraction(value)


def load_frozen_design(
    root: str | Path,
) -> tuple[dict[str, Any], tuple[dict[str, str], ...]]:
    """Load and validate the frozen design without executing a case."""

    benchmark_root = Path(root)
    freeze_path = benchmark_root / "L2_D2_execution_freeze.json"
    matrix_path = benchmark_root / "L2_D2_callback_order_case_matrix.csv"
    if _sha256_file(matrix_path) != CASE_MATRIX_SHA256:
        raise ValueError("L2-D2 case matrix hash does not match the freeze")
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    with matrix_path.open("r", encoding="utf-8-sig", newline="") as stream:
        matrix = tuple(dict(row) for row in csv.DictReader(stream))
    validate_frozen_design(freeze, matrix)
    return freeze, matrix


def validate_frozen_design(
    freeze: dict[str, Any],
    matrix: tuple[dict[str, str], ...],
) -> None:
    """Reject any design that differs from the authorized L2-D2.0a freeze."""

    required = {
        "design_version": DESIGN_VERSION,
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
    if (
        freeze.get("common_replay_context", {}).get("committed_state_sha256")
        != AUTHORITATIVE_COMMITTED_HASH
    ):
        raise ValueError("Replay committed-state fingerprint mismatch")

    case_ids = tuple(row.get("case_id", "") for row in matrix)
    if case_ids != AUTHORIZED_CASES or len(set(case_ids)) != len(case_ids):
        raise ValueError("Case matrix must contain exactly L2-CO-01/02")
    for row in matrix:
        case_id = row["case_id"]
        if row.get("implementation") != CASE_VARIANTS[case_id]:
            raise ValueError(f"Variant mismatch for {case_id}")
        if row.get("expected_classification") != EXPECTED_CLASSIFICATIONS[case_id]:
            raise ValueError(f"Classification mismatch for {case_id}")
        if row.get("execution_authorized", "").lower() != "false":
            raise ValueError(f"Execution unexpectedly authorized for {case_id}")

    frozen_cases = tuple(freeze.get("scope", {}).get("authorized_design_cases", ()))
    if frozen_cases != AUTHORIZED_CASES:
        raise ValueError("Frozen case scope mismatch")
    forbidden = frozenset(freeze.get("histories", {}).get("forbidden_events", ()))
    if forbidden != FORBIDDEN_EVENTS:
        raise ValueError("Frozen forbidden-event set mismatch")


def _packet_from_entry(entry: dict[str, Any]) -> CallbackPacket:
    committed_hash = entry.get("committed_state_sha256")
    if committed_hash is None:
        committed_hash = entry.get("declared_committed_state_sha256")
    return CallbackPacket(
        ordinal=int(entry["ordinal"]),
        event=str(entry["event"]),
        attempt_id=entry.get("attempt_id"),
        u=_fraction(entry.get("u")),
        force=_fraction(entry.get("force")),
        residual_version=entry.get("residual_version"),
        tangent_version=entry.get("tangent_version"),
        declared_committed_state_sha256=committed_hash,
        accepted_output_reachable=entry.get("accepted_output_reachable"),
    )


def _packet_signature(packet: CallbackPacket) -> tuple[Any, ...]:
    return (
        packet.ordinal,
        packet.event,
        packet.attempt_id,
        None if packet.u is None else str(packet.u),
        None if packet.force is None else str(packet.force),
        packet.residual_version,
        packet.tangent_version,
        packet.accepted_output_reachable,
    )


_DIRECT_SIGNATURE = (
    (1, "BeginAttempt", "DIRECT_REPLAY", None, None, None, None, None),
    (2, "TrialEvaluate", None, "1/200", "1/2", None, None, None),
    (3, "FormResidual", None, None, None, "L2-R-D1.0", None, None),
    (4, "FormTangent", None, None, None, None, "L2-K-D1.0", None),
    (5, "RejectAttempt", "DIRECT_REPLAY", None, None, None, None, False),
)

_EXTRA_SIGNATURE = (
    (1, "BeginAttempt", "EXTRA_CALLBACK_BATCH", None, None, None, None, None),
    (2, "TrialEvaluate", None, "3/100", "1/2", None, None, None),
    (3, "FormResidual", None, None, None, "L2-R-D1.0", None, None),
    (4, "TrialEvaluate", None, "-3/100", "1/2", None, None, None),
    (5, "FormResidual", None, None, None, "L2-R-D1.0", None, None),
    (6, "RejectAttempt", "EXTRA_CALLBACK_BATCH", None, None, None, None, False),
    (7, "BeginAttempt", "EXTRA_REPLAY", None, None, None, None, None),
    (8, "TrialEvaluate", None, "1/200", "1/2", None, None, None),
    (9, "FormResidual", None, None, None, "L2-R-D1.0", None, None),
    (10, "FormTangent", None, None, None, None, "L2-K-D1.0", None),
    (11, "RejectAttempt", "EXTRA_REPLAY", None, None, None, None, False),
)


def _build_history(
    freeze: dict[str, Any],
    history_id: str,
    expected_signature: tuple[tuple[Any, ...], ...],
) -> CallbackHistory:
    entries = freeze.get("histories", {}).get(history_id)
    if not isinstance(entries, list):
        raise ValueError(f"Missing frozen callback history: {history_id}")
    packets = tuple(_packet_from_entry(entry) for entry in entries)
    signature = tuple(_packet_signature(packet) for packet in packets)
    if signature != expected_signature:
        raise ValueError(f"Callback schedule mismatch: {history_id}")
    if any(packet.event in FORBIDDEN_EVENTS for packet in packets):
        raise ValueError(f"Forbidden callback in history: {history_id}")
    for packet in packets:
        if packet.event == "TrialEvaluate":
            if packet.declared_committed_state_sha256 != AUTHORITATIVE_COMMITTED_HASH:
                raise ValueError("TrialEvaluate committed-state identity mismatch")
    return CallbackHistory(history_id=history_id, packets=packets)


def build_direct_history(freeze: dict[str, Any]) -> CallbackHistory:
    return _build_history(freeze, "direct_callbacks", _DIRECT_SIGNATURE)


def build_extra_history(freeze: dict[str, Any]) -> CallbackHistory:
    return _build_history(
        freeze,
        "extra_nonaccepting_callbacks",
        _EXTRA_SIGNATURE,
    )


def _physical_candidate_fingerprint(result: ElementResult) -> str:
    """Fingerprint physical candidate fields without algorithmic labels."""

    return canonical_hash(
        {
            "epsilon_p": result.candidate.epsilon_p,
            "kappa": result.candidate.kappa,
        }
    )


def _values_are_finite(result: ElementResult, absolute_limit: float) -> bool:
    return all(
        math.isfinite(value) and abs(value) <= absolute_limit
        for value in result.finite_values
    )


def _event_record(
    *,
    packet: CallbackPacket,
    history_id: str,
    attempt_id: str | None,
    result: ElementResult | None,
    variant: object,
    candidate_reachable: bool | None = None,
) -> dict[str, Any]:
    return {
        "ordinal": packet.ordinal,
        "history_id": history_id,
        "event": packet.event,
        "attempt_id": attempt_id or "",
        "candidate_id": "" if result is None else result.candidate.candidate_id,
        "u": None if result is None else result.u,
        "force": None if result is None else result.force,
        "residual": None if result is None else result.residual,
        "tangent": None if result is None else result.tangent,
        "candidate_fingerprint": (
            "" if result is None else _physical_candidate_fingerprint(result)
        ),
        "persistent_fingerprint": variant.persistent_hash,
        "committed_fingerprint": variant.committed.fingerprint,
        "candidate_reachable": candidate_reachable,
    }


def _make_replay_observation(
    *,
    history_id: str,
    attempt_id: str,
    context: ReplayContext,
    result: ElementResult,
    persistent_state_fingerprint: str,
    committed_before: str,
    committed_after: str,
    candidate_reachable_after_reject: bool,
    finite_absolute_limit: float,
) -> ReplayObservation:
    physical_candidate_hash = _physical_candidate_fingerprint(result)
    observed_hash = canonical_hash(
        {
            "declared_replay_context_fingerprint": context.fingerprint,
            "residual_float_hex": result.residual.hex(),
            "tangent_float_hex": result.tangent.hex(),
            "candidate_state_fingerprint": physical_candidate_hash,
            "persistent_state_fingerprint": persistent_state_fingerprint,
        }
    )
    return ReplayObservation(
        history_id=history_id,
        attempt_id=attempt_id,
        declared_context=context,
        declared_replay_context_fingerprint=context.fingerprint,
        observed_replay_fingerprint=observed_hash,
        residual=result.residual,
        tangent=result.tangent,
        residual_state_version=result.material.residual_state_version,
        tangent_state_version=result.material.tangent_state_version,
        candidate_state_fingerprint=physical_candidate_hash,
        raw_candidate_state_fingerprint=result.candidate.fingerprint,
        persistent_state_fingerprint=persistent_state_fingerprint,
        committed_fingerprint_before=committed_before,
        committed_fingerprint_after=committed_after,
        candidate_reachable_after_reject=candidate_reachable_after_reject,
        all_values_finite=_values_are_finite(result, finite_absolute_limit),
    )


def run_callback_history(
    *,
    case_id: str,
    variant: object,
    material: MaterialData,
    element: ElementData,
    history: CallbackHistory,
    configuration_hash: str,
    residual_version: str,
    tangent_version: str,
    finite_absolute_limit: float,
) -> HistoryExecution:
    """Replay one frozen history without accepting any candidate state."""

    if case_id not in AUTHORIZED_CASES:
        raise ValueError(f"Unauthorized L2-D2 case: {case_id}")
    if variant.material.fingerprint != material.fingerprint:
        raise ValueError("Variant and declared material differ")
    committed_before = variant.committed.fingerprint
    persistent_before = variant.persistent_hash
    if committed_before != AUTHORITATIVE_COMMITTED_HASH:
        raise ValueError("History did not start from the authoritative state")

    event_log: list[dict[str, Any]] = []
    rejected_candidate_ids: list[str] = []
    reachability: list[tuple[str, bool]] = []
    current_attempt: str | None = None
    current_candidates: list[str] = []
    active_result: ElementResult | None = None
    replay_result: ElementResult | None = None
    replay_context: ReplayContext | None = None
    replay_observation: ReplayObservation | None = None
    source_call_index = 0

    for packet in history.packets:
        if packet.event in FORBIDDEN_EVENTS:
            raise RuntimeError(f"Forbidden callback reached: {packet.event}")

        if packet.event == "BeginAttempt":
            if current_attempt is not None or packet.attempt_id is None:
                raise RuntimeError("Invalid BeginAttempt ordering")
            current_attempt = packet.attempt_id
            current_candidates = []
            active_result = None
            variant.begin_attempt(current_attempt)
            event_log.append(
                _event_record(
                    packet=packet,
                    history_id=history.history_id,
                    attempt_id=current_attempt,
                    result=None,
                    variant=variant,
                )
            )
            continue

        if packet.event == "TrialEvaluate":
            if current_attempt is None or packet.u is None or packet.force is None:
                raise RuntimeError("TrialEvaluate without an active attempt")
            source_call_index += 1
            candidate_id = (
                f"{case_id}:{history.history_id}:{current_attempt}:"
                f"trial:{source_call_index}"
            )
            active_result = evaluate_element(
                variant,
                element,
                case_id=case_id,
                history_id=history.history_id,
                configuration_hash=configuration_hash,
                displacement=float(packet.u),
                force=float(packet.force),
                candidate_id=candidate_id,
                attempt_id=current_attempt,
                source_call_index=source_call_index,
            )
            current_candidates.append(candidate_id)
            if current_attempt in {"DIRECT_REPLAY", "EXTRA_REPLAY"}:
                replay_result = active_result
                replay_context = ReplayContext(
                    u=active_result.u,
                    force=active_result.force,
                    committed_state_fingerprint=variant.committed.fingerprint,
                    residual_version=residual_version,
                    tangent_version=tangent_version,
                )
            event_log.append(
                _event_record(
                    packet=packet,
                    history_id=history.history_id,
                    attempt_id=current_attempt,
                    result=active_result,
                    variant=variant,
                    candidate_reachable=variant.candidate_reachable(candidate_id),
                )
            )
            continue

        if packet.event == "FormResidual":
            if active_result is None or packet.residual_version != residual_version:
                raise RuntimeError("FormResidual lacks the frozen trial result/version")
            event_log.append(
                _event_record(
                    packet=packet,
                    history_id=history.history_id,
                    attempt_id=current_attempt,
                    result=active_result,
                    variant=variant,
                    candidate_reachable=variant.candidate_reachable(
                        active_result.candidate.candidate_id
                    ),
                )
            )
            continue

        if packet.event == "FormTangent":
            if active_result is None or packet.tangent_version != tangent_version:
                raise RuntimeError("FormTangent lacks the frozen trial result/version")
            event_log.append(
                _event_record(
                    packet=packet,
                    history_id=history.history_id,
                    attempt_id=current_attempt,
                    result=active_result,
                    variant=variant,
                    candidate_reachable=variant.candidate_reachable(
                        active_result.candidate.candidate_id
                    ),
                )
            )
            continue

        if packet.event == "RejectAttempt":
            if current_attempt is None or packet.attempt_id != current_attempt:
                raise RuntimeError("RejectAttempt does not match the active attempt")
            variant.reject_attempt(current_attempt)
            rejected_candidate_ids.extend(current_candidates)
            for candidate_id in current_candidates:
                reachability.append(
                    (candidate_id, variant.candidate_reachable(candidate_id))
                )
            if variant.committed.fingerprint != committed_before:
                raise RuntimeError("RejectAttempt mutated committed state")
            replay_candidate_reachable = False
            if active_result is not None:
                replay_candidate_reachable = variant.candidate_reachable(
                    active_result.candidate.candidate_id
                )
            event_log.append(
                _event_record(
                    packet=packet,
                    history_id=history.history_id,
                    attempt_id=current_attempt,
                    result=active_result,
                    variant=variant,
                    candidate_reachable=replay_candidate_reachable,
                )
            )
            if current_attempt in {"DIRECT_REPLAY", "EXTRA_REPLAY"}:
                if replay_result is None or replay_context is None:
                    raise RuntimeError("Replay attempt has no evaluated result")
                replay_observation = _make_replay_observation(
                    history_id=history.history_id,
                    attempt_id=current_attempt,
                    context=replay_context,
                    result=replay_result,
                    persistent_state_fingerprint=variant.persistent_hash,
                    committed_before=committed_before,
                    committed_after=variant.committed.fingerprint,
                    candidate_reachable_after_reject=(
                        replay_candidate_reachable
                    ),
                    finite_absolute_limit=finite_absolute_limit,
                )
            current_attempt = None
            current_candidates = []
            active_result = None
            continue

        raise RuntimeError(f"Unsupported callback event: {packet.event}")

    if current_attempt is not None or replay_observation is None:
        raise RuntimeError("Callback history ended without a rejected replay")
    committed_after = variant.committed.fingerprint
    if committed_after != committed_before:
        raise RuntimeError("Callback history changed committed state")
    return HistoryExecution(
        case_id=case_id,
        variant=variant.name,
        history=history,
        replay=replay_observation,
        event_log=tuple(event_log),
        trial_evaluation_count=source_call_index,
        committed_fingerprint_before=committed_before,
        committed_fingerprint_after=committed_after,
        persistent_fingerprint_before=persistent_before,
        persistent_fingerprint_after=variant.persistent_hash,
        rejected_candidate_ids=tuple(rejected_candidate_ids),
        candidate_reachability_after_reject=tuple(reachability),
        accepted_output_candidate_ids=(),
    )


def _within_tolerance(
    actual: float,
    expected: float,
    absolute_tolerance: float,
    relative_tolerance: float,
) -> bool:
    return abs(actual - expected) <= max(
        absolute_tolerance,
        relative_tolerance * abs(expected),
    )


def compare_replays(
    direct: HistoryExecution,
    extra: HistoryExecution,
    *,
    expected_delta_residual: float,
    expected_delta_tangent: float,
    analytical_absolute: float,
    analytical_relative: float,
    unsafe_minimum_finite_drift: float,
    finite_absolute_limit: float,
) -> dict[str, Any]:
    """Compare replay observations while keeping declared and observed identity separate."""

    delta_residual = extra.replay.residual - direct.replay.residual
    delta_tangent = extra.replay.tangent - direct.replay.tangent
    values = (
        direct.replay.residual,
        extra.replay.residual,
        delta_residual,
        direct.replay.tangent,
        extra.replay.tangent,
        delta_tangent,
    )
    all_values_finite = (
        direct.replay.all_values_finite
        and extra.replay.all_values_finite
        and all(
            math.isfinite(value) and abs(value) <= finite_absolute_limit
            for value in values
        )
    )
    direct_unreachable = not any(
        reachable for _, reachable in direct.candidate_reachability_after_reject
    )
    extra_unreachable = not any(
        reachable for _, reachable in extra.candidate_reachability_after_reject
    )
    return {
        "direct_history_id": direct.history.history_id,
        "extra_history_id": extra.history.history_id,
        "declared_replay_context_equal": (
            direct.replay.declared_replay_context_fingerprint
            == extra.replay.declared_replay_context_fingerprint
        ),
        "observed_replay_fingerprint_equal": (
            direct.replay.observed_replay_fingerprint
            == extra.replay.observed_replay_fingerprint
        ),
        "direct_declared_replay_context_fingerprint": (
            direct.replay.declared_replay_context_fingerprint
        ),
        "extra_declared_replay_context_fingerprint": (
            extra.replay.declared_replay_context_fingerprint
        ),
        "direct_observed_replay_fingerprint": (
            direct.replay.observed_replay_fingerprint
        ),
        "extra_observed_replay_fingerprint": (
            extra.replay.observed_replay_fingerprint
        ),
        "direct_residual": direct.replay.residual,
        "extra_residual": extra.replay.residual,
        "delta_residual": delta_residual,
        "direct_tangent": direct.replay.tangent,
        "extra_tangent": extra.replay.tangent,
        "delta_tangent": delta_tangent,
        "expected_delta_residual": expected_delta_residual,
        "expected_delta_tangent": expected_delta_tangent,
        "analytical_residual_match": _within_tolerance(
            delta_residual,
            expected_delta_residual,
            analytical_absolute,
            analytical_relative,
        ),
        "analytical_tangent_match": _within_tolerance(
            delta_tangent,
            expected_delta_tangent,
            analytical_absolute,
            analytical_relative,
        ),
        "unsafe_residual_drift_floor_met": (
            abs(delta_residual) >= unsafe_minimum_finite_drift
        ),
        "committed_state_unchanged": (
            direct.committed_fingerprint_before
            == direct.committed_fingerprint_after
            == extra.committed_fingerprint_before
            == extra.committed_fingerprint_after
        ),
        "rejected_candidates_unreachable": (
            direct_unreachable and extra_unreachable
        ),
        "accepted_output_unreachable": (
            not direct.accepted_output_candidate_ids
            and not extra.accepted_output_candidate_ids
        ),
        "all_values_finite": all_values_finite,
        "direct_trial_evaluation_count": direct.trial_evaluation_count,
        "extra_trial_evaluation_count": extra.trial_evaluation_count,
        "no_accept_event": all(
            row["event"] != "AcceptIncrement"
            for row in (*direct.event_log, *extra.event_log)
        ),
    }


def classify_callback_order_case(
    case_id: str,
    comparison: dict[str, Any],
) -> tuple[str, bool]:
    """Apply the frozen case gate without widening any tolerance."""

    common = (
        comparison["declared_replay_context_equal"]
        and comparison["committed_state_unchanged"]
        and comparison["rejected_candidates_unreachable"]
        and comparison["accepted_output_unreachable"]
        and comparison["all_values_finite"]
        and comparison["no_accept_event"]
        and comparison["direct_trial_evaluation_count"] == 1
        and comparison["extra_trial_evaluation_count"] == 3
    )
    if case_id == "L2-CO-01":
        passed = (
            common
            and comparison["delta_residual"] == 0.0
            and comparison["delta_tangent"] == 0.0
            and comparison["observed_replay_fingerprint_equal"]
            and comparison["analytical_residual_match"]
            and comparison["analytical_tangent_match"]
        )
        return (
            "PASS_CALLBACK_INVARIANCE" if passed else "FAIL_CALLBACK_INVARIANCE",
            passed,
        )
    if case_id == "L2-CO-02":
        passed = (
            common
            and not comparison["observed_replay_fingerprint_equal"]
            and comparison["unsafe_residual_drift_floor_met"]
            and comparison["analytical_residual_match"]
            and comparison["analytical_tangent_match"]
        )
        return (
            (
                "DETECT_CALLBACK_HISTORY_DRIFT"
                if passed
                else "FAIL_TO_DETECT_CALLBACK_HISTORY_DRIFT"
            ),
            passed,
        )
    raise ValueError(f"Unauthorized L2-D2 case: {case_id}")


def execute_callback_order_case(
    root: str | Path,
    case_id: str,
    run_id: str,
) -> CallbackOrderCaseResult:
    """Execute one future-authorized case in memory without writing outputs.

    This entry point is intentionally inert until explicitly called by the
    separately locked runner. It never runs during module import.
    """

    if case_id not in AUTHORIZED_CASES:
        raise ValueError(f"Unauthorized L2-D2 case: {case_id}")
    if not run_id or not run_id.strip():
        raise ValueError("run_id must be a non-empty independent-process label")
    freeze, matrix = load_frozen_design(root)
    row = next(item for item in matrix if item["case_id"] == case_id)
    variant_name = row["implementation"]
    if variant_name != CASE_VARIANTS[case_id]:
        raise ValueError("Case variant differs from the frozen matrix")

    material = MaterialData()
    element = ElementData()
    committed = CommittedState()
    if committed.fingerprint != AUTHORITATIVE_COMMITTED_HASH:
        raise ValueError("Authoritative committed state changed")
    configuration_hash = canonical_hash(
        {
            "design_version": DESIGN_VERSION,
            "host_version": HOST_VERSION,
            "material_fingerprint": material.fingerprint,
            "element_fingerprint": element.fingerprint,
            "committed_state_fingerprint": committed.fingerprint,
        }
    )

    variant_class = VARIANTS[variant_name]
    direct_variant = variant_class(material)
    extra_variant = variant_class(material)
    if direct_variant is extra_variant:
        raise RuntimeError("Direct and extra histories must not share a variant")
    if variant_name == "unsafe_trial_cache":
        if (
            direct_variant.persistent_hash != committed.fingerprint
            or extra_variant.persistent_hash != committed.fingerprint
        ):
            raise ValueError("Unsafe hidden cache seed differs from committed state")

    context = freeze["common_replay_context"]
    tolerances = freeze["tolerances"]
    direct = run_callback_history(
        case_id=case_id,
        variant=direct_variant,
        material=material,
        element=element,
        history=build_direct_history(freeze),
        configuration_hash=configuration_hash,
        residual_version=context["residual_version"],
        tangent_version=context["tangent_version"],
        finite_absolute_limit=float(tolerances["finite_absolute_limit"]),
    )
    extra = run_callback_history(
        case_id=case_id,
        variant=extra_variant,
        material=material,
        element=element,
        history=build_extra_history(freeze),
        configuration_hash=configuration_hash,
        residual_version=context["residual_version"],
        tangent_version=context["tangent_version"],
        finite_absolute_limit=float(tolerances["finite_absolute_limit"]),
    )

    oracle_key = variant_name
    oracle = freeze["analytical_oracle"][oracle_key]
    comparison = compare_replays(
        direct,
        extra,
        expected_delta_residual=float(Fraction(oracle["expected_delta_residual"])),
        expected_delta_tangent=float(Fraction(oracle["expected_delta_tangent"])),
        analytical_absolute=float(tolerances["analytical_absolute"]),
        analytical_relative=float(tolerances["analytical_relative"]),
        unsafe_minimum_finite_drift=float(
            tolerances["unsafe_minimum_finite_drift"]
        ),
        finite_absolute_limit=float(tolerances["finite_absolute_limit"]),
    )
    classification, pass_flag = classify_callback_order_case(case_id, comparison)
    return CallbackOrderCaseResult(
        design_version=DESIGN_VERSION,
        host_version=HOST_VERSION,
        case_id=case_id,
        run_id=run_id,
        variant=variant_name,
        direct=direct,
        extra=extra,
        comparison=comparison,
        expected_classification=EXPECTED_CLASSIFICATIONS[case_id],
        observed_classification=classification,
        pass_flag=pass_flag,
    )
