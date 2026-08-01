"""Frozen L2-D4.0 output-provenance benchmark implementation.

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

from .l2_model import evaluate_element, evaluate_material
from .l2_state import (
    CommittedState,
    ElementData,
    ElementResult,
    MaterialData,
    MaterialResult,
    canonical_hash,
    canonical_json,
)
from .l2_variants import SafeTransactional


DESIGN_VERSION = "L2-D4.0"
HOST_VERSION = "L2-HOST-D4.0"
IMPLEMENTATION_STATUS = "IMPLEMENTED_NOT_EXECUTED"
FREEZE_SHA256 = (
    "1beb45004f7193006275a00f06c05d000dc1056c135e45a580ee90d72910b63b"
)
CASE_MATRIX_SHA256 = (
    "04e0213e7fa343a625284f905083e54655f24debea802e377769bf6c07e77d7a"
)
AUTHORITATIVE_COMMITTED_HASH = (
    "f5045dd74424efe25edaaebfa84802eeba5e8ca376816835f58145764a2efc01"
)
AUTHORITATIVE_ACCEPTED_OUTPUT_HASH = (
    "83434ef7b7f520d2f3f4904122ee77895e46533fec0a2f513d0328092863147b"
)
AUTHORIZED_CASES = ("L2-OP-01", "L2-OP-02")
EXPECTED_CLASSIFICATIONS = {
    "L2-OP-01": "PASS_ACCEPTED_OUTPUT_PROVENANCE",
    "L2-OP-02": "DETECT_OUTPUT_FEEDBACK_DRIFT",
}

EVENT_LOG_COLUMNS = (
    "case_id",
    "run_id",
    "variant",
    "history_id",
    "ordinal",
    "event",
    "attempt_id",
    "candidate_id",
    "u",
    "force",
    "residual",
    "tangent",
    "sigma",
    "candidate_epsilon_p",
    "candidate_kappa",
    "output_source_version",
    "output_source_candidate_id",
    "output_accepted_flag",
    "output_snapshot_fingerprint",
    "declared_replay_fingerprint",
    "observed_replay_fingerprint",
    "committed_fingerprint_before",
    "committed_fingerprint_after",
    "persistent_fingerprint_before",
    "persistent_fingerprint_after",
    "candidate_reachable",
    "accepted",
    "all_values_finite",
    "note",
)

COMPARISON_COLUMNS = (
    "case_id",
    "run_id",
    "left_id",
    "right_id",
    "output_snapshot_exact_equal",
    "accepted_output_payload_exact",
    "output_sources_valid",
    "output_read_no_evaluation",
    "live_trial_candidate_during_output",
    "output_read_committed_unchanged",
    "output_read_persistent_unchanged",
    "trial_candidate_unreachable_after_reject",
    "seed_output_rejected_as_accepted",
    "declared_replay_fingerprint_equal",
    "d1_declared_packet_equal",
    "observed_replay_fingerprint_equal",
    "delta_sigma",
    "delta_residual",
    "delta_tangent",
    "oracle_sigma_match",
    "oracle_residual_match",
    "oracle_tangent_match",
    "committed_states_unchanged",
    "candidates_unreachable",
    "all_values_finite",
    "classification",
    "pass_flag",
)


@dataclass(frozen=True)
class OutputSnapshot:
    accepted_version: int
    epsilon_p: float
    kappa: float
    source_version: str
    source_candidate_id: str
    source_committed_state_hash: str
    output_accepted_flag: bool

    @property
    def payload(self) -> dict[str, Any]:
        return {
            "accepted_version": self.accepted_version,
            "epsilon_p": self.epsilon_p,
            "kappa": self.kappa,
            "source_version": self.source_version,
            "source_candidate_id": self.source_candidate_id,
            "source_committed_state_hash": self.source_committed_state_hash,
        }

    @property
    def fingerprint(self) -> str:
        return canonical_hash(self.payload)

    @property
    def accepted_source_valid(self) -> bool:
        expected = CommittedState(
            epsilon_p=self.epsilon_p,
            kappa=self.kappa,
            accepted_version=self.accepted_version,
        )
        return (
            self.output_accepted_flag
            and self.source_version == f"accepted:{self.accepted_version}"
            and self.source_candidate_id == "NA"
            and self.source_committed_state_hash == expected.fingerprint
        )


@dataclass(frozen=True)
class ReplayContext:
    u: float
    force: float
    committed_state_sha256: str
    accepted_version: int
    residual_definition: str
    tangent_definition: str
    intended_physical_history_source: str

    @property
    def fingerprint(self) -> str:
        return canonical_hash(asdict(self))


@dataclass(frozen=True)
class ReplayObservation:
    history_id: str
    u: float
    force: float
    residual: float
    tangent: float
    sigma: float
    candidate_epsilon_p: float
    candidate_kappa: float
    candidate_state_fingerprint: str
    raw_candidate_fingerprint: str
    declared_replay_context_fingerprint: str
    d1_declared_packet_hash: str
    actual_history_source_version: str
    persistent_output_mirror_fingerprint: str
    observed_replay_fingerprint: str
    committed_fingerprint_before: str
    committed_fingerprint_after: str
    candidate_reachable_after_reject: bool
    all_values_finite: bool


@dataclass(frozen=True)
class OutputEventPacket:
    case_id: str
    run_id: str
    variant: str
    history_id: str
    ordinal: int
    event: str
    attempt_id: str
    candidate_id: str
    u: float | None
    force: float | None
    residual: float | None
    tangent: float | None
    sigma: float | None
    candidate_epsilon_p: float | None
    candidate_kappa: float | None
    output_source_version: str
    output_source_candidate_id: str
    output_accepted_flag: bool | None
    output_snapshot_fingerprint: str
    declared_replay_fingerprint: str
    observed_replay_fingerprint: str
    committed_fingerprint_before: str
    committed_fingerprint_after: str
    persistent_fingerprint_before: str
    persistent_fingerprint_after: str
    candidate_reachable: bool
    accepted: bool
    all_values_finite: bool
    note: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OutputHistory:
    case_id: str
    variant: str
    history_id: str
    output_snapshot: OutputSnapshot | None
    replay: ReplayObservation | None
    events: tuple[OutputEventPacket, ...]
    material_evaluation_count: int
    output_read_material_evaluation_count: int
    committed_fingerprint_before: str
    committed_fingerprint_after: str
    persistent_fingerprint_before: str
    persistent_fingerprint_after: str
    output_read_committed_before: str
    output_read_committed_after: str
    output_read_persistent_before: str
    output_read_persistent_after: str
    live_trial_candidate_during_output: bool
    candidate_unreachable_after_history: bool
    all_values_finite: bool


@dataclass(frozen=True)
class OutputProvenanceComparison:
    case_id: str
    left_id: str
    right_id: str
    output_snapshot_exact_equal: bool | None
    accepted_output_payload_exact: bool | None
    output_sources_valid: bool | None
    output_read_no_evaluation: bool | None
    live_trial_candidate_during_output: bool | None
    output_read_committed_unchanged: bool | None
    output_read_persistent_unchanged: bool | None
    trial_candidate_unreachable_after_reject: bool | None
    seed_output_rejected_as_accepted: bool | None
    declared_replay_fingerprint_equal: bool | None
    d1_declared_packet_equal: bool | None
    observed_replay_fingerprint_equal: bool | None
    delta_sigma: float | None
    delta_residual: float | None
    delta_tangent: float | None
    oracle_sigma_match: bool | None
    oracle_residual_match: bool | None
    oracle_tangent_match: bool | None
    committed_states_unchanged: bool
    candidates_unreachable: bool
    all_values_finite: bool


@dataclass(frozen=True)
class OutputProvenanceCaseResult:
    design_version: str
    host_version: str
    implementation_status: str
    case_id: str
    run_id: str
    variant: str
    left_history: OutputHistory
    right_history: OutputHistory
    comparison: OutputProvenanceComparison
    expected_classification: str
    observed_classification: str
    pass_flag: bool

    @property
    def event_log(self) -> tuple[dict[str, Any], ...]:
        return tuple(
            event.to_dict()
            for event in (*self.left_history.events, *self.right_history.events)
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class UnsafeOutputFeedback:
    """Deliberate negative control: output mirror is read as physical history."""

    name = "unsafe_output_feedback"
    persistent_state_class = "deliberate_output_mirror_feedback"

    def __init__(self, material: MaterialData) -> None:
        self.material = material
        self.committed = CommittedState()
        self._mirror = self.committed

    @property
    def persistent_hash(self) -> str:
        return canonical_hash(self._mirror)

    def begin_attempt(self, attempt_id: str) -> None:
        del attempt_id

    def evaluate(
        self,
        epsilon: float,
        *,
        candidate_id: str,
        attempt_id: str,
        source_call_index: int,
    ) -> MaterialResult:
        return evaluate_material(
            epsilon,
            self._mirror,
            self.material,
            candidate_id=candidate_id,
            attempt_id=attempt_id,
            source_call_index=source_call_index,
            state_version_override=f"mirror:{self.persistent_hash}",
        )

    def reject_attempt(self, attempt_id: str) -> tuple[str, ...]:
        del attempt_id
        return ()

    def candidate_reachable(self, candidate_id: str) -> bool:
        del candidate_id
        return False

    def unsafe_output_read(
        self,
        trigger_u: float,
    ) -> tuple[OutputSnapshot, MaterialResult]:
        result = evaluate_material(
            trigger_u,
            self.committed,
            self.material,
            candidate_id="output_hidden_candidate",
            attempt_id="OUTPUT_READ_SEED",
            source_call_index=1,
            state_version_override="trial_hidden",
        )
        self._mirror = CommittedState(
            epsilon_p=result.candidate.epsilon_p,
            kappa=result.candidate.kappa,
            accepted_version=self.committed.accepted_version,
        )
        snapshot = OutputSnapshot(
            accepted_version=self.committed.accepted_version,
            epsilon_p=self._mirror.epsilon_p,
            kappa=self._mirror.kappa,
            source_version="trial_hidden",
            source_candidate_id=result.candidate.candidate_id,
            source_committed_state_hash=self.committed.fingerprint,
            output_accepted_flag=False,
        )
        return snapshot, result


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fraction(value: str) -> float:
    return float(Fraction(value))


def _finite(values: tuple[float, ...], limit: float) -> bool:
    return all(math.isfinite(value) and abs(value) <= limit for value in values)


def _physical_candidate_fingerprint(result: ElementResult) -> str:
    return canonical_hash(
        {
            "epsilon_p": result.candidate.epsilon_p,
            "kappa": result.candidate.kappa,
        }
    )


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


def load_frozen_design(
    root: str | Path,
) -> tuple[dict[str, Any], tuple[dict[str, str], ...]]:
    benchmark_root = Path(root)
    freeze_path = benchmark_root / "L2_D4_execution_freeze.json"
    matrix_path = benchmark_root / "L2_D4_output_provenance_case_matrix.csv"
    if _sha256_file(freeze_path) != FREEZE_SHA256:
        raise ValueError("L2-D4 freeze hash mismatch")
    if _sha256_file(matrix_path) != CASE_MATRIX_SHA256:
        raise ValueError("L2-D4 case matrix hash mismatch")
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    with matrix_path.open("r", encoding="utf-8-sig", newline="") as stream:
        matrix = tuple(dict(row) for row in csv.DictReader(stream))
    validate_frozen_design(freeze, matrix)
    return freeze, matrix


def validate_frozen_design(
    freeze: dict[str, Any],
    matrix: tuple[dict[str, str], ...],
) -> None:
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
        raise ValueError("Case matrix must contain exactly L2-OP-01/02")
    for row in matrix:
        case_id = row["case_id"]
        if row.get("implementation") not in {
            "safe_transactional",
            "unsafe_output_feedback",
        }:
            raise ValueError(f"Variant mismatch for {case_id}")
        if row.get("expected_classification") != EXPECTED_CLASSIFICATIONS[case_id]:
            raise ValueError(f"Classification mismatch for {case_id}")
        if row.get("execution_authorized", "").lower() != "false":
            raise ValueError(f"Execution unexpectedly authorized for {case_id}")
    frozen_cases = tuple(freeze.get("scope", {}).get("authorized_design_cases", ()))
    if frozen_cases != AUTHORIZED_CASES:
        raise ValueError("Frozen case scope mismatch")

    output_packet = freeze.get("frozen_packets", {}).get(
        "accepted_output_payload", {}
    )
    snapshot = OutputSnapshot(
        accepted_version=0,
        epsilon_p=0.0,
        kappa=0.0,
        source_version="accepted:0",
        source_candidate_id="NA",
        source_committed_state_hash=AUTHORITATIVE_COMMITTED_HASH,
        output_accepted_flag=True,
    )
    if snapshot.fingerprint != AUTHORITATIVE_ACCEPTED_OUTPUT_HASH:
        raise ValueError("D1 output serializer identity mismatch")
    if output_packet.get("sha256") != AUTHORITATIVE_ACCEPTED_OUTPUT_HASH:
        raise ValueError("Frozen accepted-output fingerprint mismatch")

    histories = freeze.get("frozen_histories", {})
    expected_events = {
        "L2-OP-01": {
            "trial_then_output": (
                "BeginAttempt",
                "TrialEvaluate",
                "FormResidual",
                "FormTangent",
                "OutputRead",
                "RejectAttempt",
            ),
            "accepted_output_only": ("OutputRead",),
        },
        "L2-OP-02": {
            "insert_output_read": (
                "OutputRead",
                "BeginAttempt",
                "TrialEvaluate",
                "FormResidual",
                "FormTangent",
                "RejectAttempt",
            ),
            "direct_path": (
                "BeginAttempt",
                "TrialEvaluate",
                "FormResidual",
                "FormTangent",
                "RejectAttempt",
            ),
        },
    }
    for case_id, schedules in expected_events.items():
        for history_id, events in schedules.items():
            observed = tuple(
                item.get("event") for item in histories[case_id][history_id]
            )
            if observed != events:
                raise ValueError(f"Frozen callback schedule drift: {history_id}")

    oracle = freeze.get("analytical_oracle", {})
    if oracle.get("L2-OP-02", {}).get("delta_residual") != "-205/121":
        raise ValueError("OP-02 residual oracle drift")
    if oracle.get("L2-OP-02", {}).get("delta_tangent") != "-1000/11":
        raise ValueError("OP-02 tangent oracle drift")


def read_accepted_output(variant: SafeTransactional) -> OutputSnapshot:
    """Read physical output without material evaluation or state mutation."""

    committed = variant.committed
    return OutputSnapshot(
        accepted_version=committed.accepted_version,
        epsilon_p=committed.epsilon_p,
        kappa=committed.kappa,
        source_version=f"accepted:{committed.accepted_version}",
        source_candidate_id="NA",
        source_committed_state_hash=committed.fingerprint,
        output_accepted_flag=True,
    )


def _declared_replay_context(freeze: dict[str, Any]) -> ReplayContext:
    packet = freeze["frozen_packets"]["replay_packet"]
    return ReplayContext(
        u=_fraction(packet["u"]),
        force=_fraction(packet["force"]),
        committed_state_sha256=packet["committed_state_sha256"],
        accepted_version=freeze["declared_committed_state"]["accepted_version"],
        residual_definition=packet["residual_definition"],
        tangent_definition=packet["tangent_definition"],
        intended_physical_history_source=packet[
            "intended_physical_history_source"
        ],
    )


def _event(
    *,
    case_id: str,
    run_id: str,
    variant: str,
    history_id: str,
    ordinal: int,
    event: str,
    committed_before: str,
    committed_after: str,
    persistent_before: str,
    persistent_after: str,
    attempt_id: str = "NA",
    candidate_id: str = "NA",
    result: ElementResult | None = None,
    snapshot: OutputSnapshot | None = None,
    declared_replay_fingerprint: str = "NA",
    observed_replay_fingerprint: str = "NA",
    candidate_reachable: bool = False,
    accepted: bool = False,
    all_values_finite: bool = True,
    note: str = "ok",
    sigma_override: float | None = None,
    u_override: float | None = None,
    force_override: float | None = None,
    candidate_epsilon_p_override: float | None = None,
    candidate_kappa_override: float | None = None,
) -> OutputEventPacket:
    return OutputEventPacket(
        case_id=case_id,
        run_id=run_id,
        variant=variant,
        history_id=history_id,
        ordinal=ordinal,
        event=event,
        attempt_id=attempt_id,
        candidate_id=candidate_id,
        u=(result.u if result is not None else u_override),
        force=(result.force if result is not None else force_override),
        residual=None if result is None else result.residual,
        tangent=None if result is None else result.tangent,
        sigma=(result.sigma if result is not None else sigma_override),
        candidate_epsilon_p=(
            result.candidate.epsilon_p
            if result is not None
            else candidate_epsilon_p_override
        ),
        candidate_kappa=(
            result.candidate.kappa
            if result is not None
            else candidate_kappa_override
        ),
        output_source_version=("NA" if snapshot is None else snapshot.source_version),
        output_source_candidate_id=(
            "NA" if snapshot is None else snapshot.source_candidate_id
        ),
        output_accepted_flag=(
            None if snapshot is None else snapshot.output_accepted_flag
        ),
        output_snapshot_fingerprint=(
            "NA" if snapshot is None else snapshot.fingerprint
        ),
        declared_replay_fingerprint=declared_replay_fingerprint,
        observed_replay_fingerprint=observed_replay_fingerprint,
        committed_fingerprint_before=committed_before,
        committed_fingerprint_after=committed_after,
        persistent_fingerprint_before=persistent_before,
        persistent_fingerprint_after=persistent_after,
        candidate_reachable=candidate_reachable,
        accepted=accepted,
        all_values_finite=all_values_finite,
        note=note,
    )


def build_trial_then_output_history(
    freeze: dict[str, Any],
    *,
    run_id: str,
    material: MaterialData,
    element: ElementData,
    configuration_hash: str,
) -> OutputHistory:
    del freeze
    case_id = "L2-OP-01"
    history_id = "trial_then_output"
    variant = SafeTransactional(material)
    committed_before = variant.committed.fingerprint
    persistent_before = variant.persistent_hash
    events: list[OutputEventPacket] = []

    begin_persistent = variant.persistent_hash
    variant.begin_attempt("TRIAL_PRESENT")
    events.append(
        _event(
            case_id=case_id,
            run_id=run_id,
            variant=variant.name,
            history_id=history_id,
            ordinal=1,
            event="BeginAttempt",
            attempt_id="TRIAL_PRESENT",
            committed_before=committed_before,
            committed_after=variant.committed.fingerprint,
            persistent_before=begin_persistent,
            persistent_after=variant.persistent_hash,
        )
    )
    result = evaluate_element(
        variant,
        element,
        case_id=case_id,
        history_id=history_id,
        configuration_hash=configuration_hash,
        displacement=3.0 / 100.0,
        force=1.0 / 2.0,
        candidate_id="trial_candidate",
        attempt_id="TRIAL_PRESENT",
        source_call_index=1,
    )
    for ordinal, event_name in ((2, "TrialEvaluate"), (3, "FormResidual"), (4, "FormTangent")):
        events.append(
            _event(
                case_id=case_id,
                run_id=run_id,
                variant=variant.name,
                history_id=history_id,
                ordinal=ordinal,
                event=event_name,
                attempt_id="TRIAL_PRESENT",
                candidate_id="trial_candidate",
                result=result,
                committed_before=variant.committed.fingerprint,
                committed_after=variant.committed.fingerprint,
                persistent_before=variant.persistent_hash,
                persistent_after=variant.persistent_hash,
                candidate_reachable=variant.candidate_reachable("trial_candidate"),
                note=(
                    "single_material_evaluation"
                    if event_name == "TrialEvaluate"
                    else "reuse_same_trial_result"
                ),
            )
        )

    output_committed_before = variant.committed.fingerprint
    output_persistent_before = variant.persistent_hash
    live_candidate = variant.candidate_reachable("trial_candidate")
    snapshot = read_accepted_output(variant)
    output_committed_after = variant.committed.fingerprint
    output_persistent_after = variant.persistent_hash
    events.append(
        _event(
            case_id=case_id,
            run_id=run_id,
            variant=variant.name,
            history_id=history_id,
            ordinal=5,
            event="OutputRead",
            candidate_id=snapshot.source_candidate_id,
            snapshot=snapshot,
            committed_before=output_committed_before,
            committed_after=output_committed_after,
            persistent_before=output_persistent_before,
            persistent_after=output_persistent_after,
            candidate_reachable=live_candidate,
            note="accepted_read_only_while_trial_candidate_live",
        )
    )

    reject_persistent_before = variant.persistent_hash
    variant.reject_attempt("TRIAL_PRESENT")
    candidate_unreachable = not variant.candidate_reachable("trial_candidate")
    events.append(
        _event(
            case_id=case_id,
            run_id=run_id,
            variant=variant.name,
            history_id=history_id,
            ordinal=6,
            event="RejectAttempt",
            attempt_id="TRIAL_PRESENT",
            candidate_id="trial_candidate",
            committed_before=variant.committed.fingerprint,
            committed_after=variant.committed.fingerprint,
            persistent_before=reject_persistent_before,
            persistent_after=variant.persistent_hash,
            candidate_reachable=not candidate_unreachable,
            note="trial_candidate_invalidated",
        )
    )
    limit = 1.0e100
    finite = _finite(result.finite_values, limit)
    return OutputHistory(
        case_id=case_id,
        variant=variant.name,
        history_id=history_id,
        output_snapshot=snapshot,
        replay=None,
        events=tuple(events),
        material_evaluation_count=1,
        output_read_material_evaluation_count=0,
        committed_fingerprint_before=committed_before,
        committed_fingerprint_after=variant.committed.fingerprint,
        persistent_fingerprint_before=persistent_before,
        persistent_fingerprint_after=variant.persistent_hash,
        output_read_committed_before=output_committed_before,
        output_read_committed_after=output_committed_after,
        output_read_persistent_before=output_persistent_before,
        output_read_persistent_after=output_persistent_after,
        live_trial_candidate_during_output=live_candidate,
        candidate_unreachable_after_history=candidate_unreachable,
        all_values_finite=finite,
    )


def build_accepted_output_only_history(
    freeze: dict[str, Any],
    *,
    run_id: str,
    material: MaterialData,
) -> OutputHistory:
    del freeze
    case_id = "L2-OP-01"
    history_id = "accepted_output_only"
    variant = SafeTransactional(material)
    committed_before = variant.committed.fingerprint
    persistent_before = variant.persistent_hash
    snapshot = read_accepted_output(variant)
    event = _event(
        case_id=case_id,
        run_id=run_id,
        variant=variant.name,
        history_id=history_id,
        ordinal=1,
        event="OutputRead",
        candidate_id=snapshot.source_candidate_id,
        snapshot=snapshot,
        committed_before=committed_before,
        committed_after=variant.committed.fingerprint,
        persistent_before=persistent_before,
        persistent_after=variant.persistent_hash,
        note="accepted_read_only",
    )
    return OutputHistory(
        case_id=case_id,
        variant=variant.name,
        history_id=history_id,
        output_snapshot=snapshot,
        replay=None,
        events=(event,),
        material_evaluation_count=0,
        output_read_material_evaluation_count=0,
        committed_fingerprint_before=committed_before,
        committed_fingerprint_after=variant.committed.fingerprint,
        persistent_fingerprint_before=persistent_before,
        persistent_fingerprint_after=variant.persistent_hash,
        output_read_committed_before=committed_before,
        output_read_committed_after=variant.committed.fingerprint,
        output_read_persistent_before=persistent_before,
        output_read_persistent_after=variant.persistent_hash,
        live_trial_candidate_during_output=False,
        candidate_unreachable_after_history=True,
        all_values_finite=True,
    )


def _build_replay_observation(
    *,
    history_id: str,
    context: ReplayContext,
    result: ElementResult,
    persistent_hash: str,
    committed_before: str,
    committed_after: str,
    candidate_reachable_after_reject: bool,
    finite_limit: float,
) -> ReplayObservation:
    candidate_state_fingerprint = _physical_candidate_fingerprint(result)
    observed = canonical_hash(
        {
            "declared_replay_context_fingerprint": context.fingerprint,
            "actual_history_source_version": (
                result.material.residual_state_version
            ),
            "residual": result.residual,
            "tangent": result.tangent,
            "sigma": result.sigma,
            "candidate_state_fingerprint": candidate_state_fingerprint,
            "persistent_output_mirror_fingerprint": persistent_hash,
        }
    )
    return ReplayObservation(
        history_id=history_id,
        u=result.u,
        force=result.force,
        residual=result.residual,
        tangent=result.tangent,
        sigma=result.sigma,
        candidate_epsilon_p=result.candidate.epsilon_p,
        candidate_kappa=result.candidate.kappa,
        candidate_state_fingerprint=candidate_state_fingerprint,
        raw_candidate_fingerprint=result.candidate.fingerprint,
        declared_replay_context_fingerprint=context.fingerprint,
        d1_declared_packet_hash=result.declared_packet_hash,
        actual_history_source_version=result.material.residual_state_version,
        persistent_output_mirror_fingerprint=persistent_hash,
        observed_replay_fingerprint=observed,
        committed_fingerprint_before=committed_before,
        committed_fingerprint_after=committed_after,
        candidate_reachable_after_reject=candidate_reachable_after_reject,
        all_values_finite=_finite(result.finite_values, finite_limit),
    )


def _build_unsafe_replay_history(
    freeze: dict[str, Any],
    *,
    run_id: str,
    history_id: str,
    seed_output: bool,
    material: MaterialData,
    element: ElementData,
    configuration_hash: str,
) -> OutputHistory:
    case_id = "L2-OP-02"
    variant = UnsafeOutputFeedback(material)
    committed_before = variant.committed.fingerprint
    persistent_before = variant.persistent_hash
    context = _declared_replay_context(freeze)
    events: list[OutputEventPacket] = []
    snapshot: OutputSnapshot | None = None
    output_material_count = 0
    ordinal = 1
    output_read_committed_before = "NA"
    output_read_committed_after = "NA"
    output_read_persistent_before = "NA"
    output_read_persistent_after = "NA"
    finite_limit = float(freeze["tolerances"]["finite_absolute_limit"])

    if seed_output:
        output_read_committed_before = variant.committed.fingerprint
        output_read_persistent_before = variant.persistent_hash
        snapshot, seed_result = variant.unsafe_output_read(3.0 / 100.0)
        output_material_count = 1
        output_read_committed_after = variant.committed.fingerprint
        output_read_persistent_after = variant.persistent_hash
        seed_finite = _finite(
            (
                seed_result.sigma,
                seed_result.E_alg,
                seed_result.delta_gamma,
                seed_result.candidate.epsilon_p,
                seed_result.candidate.kappa,
            ),
            finite_limit,
        )
        events.append(
            _event(
                case_id=case_id,
                run_id=run_id,
                variant=variant.name,
                history_id=history_id,
                ordinal=ordinal,
                event="OutputRead",
                attempt_id="OUTPUT_READ_SEED",
                candidate_id=seed_result.candidate.candidate_id,
                snapshot=snapshot,
                committed_before=output_read_committed_before,
                committed_after=output_read_committed_after,
                persistent_before=output_read_persistent_before,
                persistent_after=output_read_persistent_after,
                all_values_finite=seed_finite,
                note="deliberate_invalid_trial_evaluation_and_mirror_write",
                sigma_override=seed_result.sigma,
                u_override=3.0 / 100.0,
                candidate_epsilon_p_override=seed_result.candidate.epsilon_p,
                candidate_kappa_override=seed_result.candidate.kappa,
            )
        )
        ordinal += 1

    attempt_id = "FEEDBACK_REPLAY" if seed_output else "DIRECT_REPLAY"
    variant.begin_attempt(attempt_id)
    events.append(
        _event(
            case_id=case_id,
            run_id=run_id,
            variant=variant.name,
            history_id=history_id,
            ordinal=ordinal,
            event="BeginAttempt",
            attempt_id=attempt_id,
            committed_before=variant.committed.fingerprint,
            committed_after=variant.committed.fingerprint,
            persistent_before=variant.persistent_hash,
            persistent_after=variant.persistent_hash,
        )
    )
    ordinal += 1
    result = evaluate_element(
        variant,
        element,
        case_id=case_id,
        history_id=history_id,
        configuration_hash=configuration_hash,
        displacement=context.u,
        force=context.force,
        candidate_id="replay_candidate",
        attempt_id=attempt_id,
        source_call_index=2 if seed_output else 1,
    )
    replay_persistent = variant.persistent_hash
    replay_committed = variant.committed.fingerprint
    candidate_id = result.candidate.candidate_id
    for event_name in ("TrialEvaluate", "FormResidual", "FormTangent"):
        events.append(
            _event(
                case_id=case_id,
                run_id=run_id,
                variant=variant.name,
                history_id=history_id,
                ordinal=ordinal,
                event=event_name,
                attempt_id=attempt_id,
                candidate_id=candidate_id,
                result=result,
                declared_replay_fingerprint=context.fingerprint,
                committed_before=replay_committed,
                committed_after=replay_committed,
                persistent_before=replay_persistent,
                persistent_after=replay_persistent,
                note=(
                    "single_material_evaluation"
                    if event_name == "TrialEvaluate"
                    else "reuse_same_trial_result"
                ),
            )
        )
        ordinal += 1

    variant.reject_attempt(attempt_id)
    candidate_unreachable = not variant.candidate_reachable(candidate_id)
    replay = _build_replay_observation(
        history_id=history_id,
        context=context,
        result=result,
        persistent_hash=variant.persistent_hash,
        committed_before=committed_before,
        committed_after=variant.committed.fingerprint,
        candidate_reachable_after_reject=not candidate_unreachable,
        finite_limit=finite_limit,
    )
    events.append(
        _event(
            case_id=case_id,
            run_id=run_id,
            variant=variant.name,
            history_id=history_id,
            ordinal=ordinal,
            event="RejectAttempt",
            attempt_id=attempt_id,
            candidate_id=candidate_id,
            committed_before=replay_committed,
            committed_after=variant.committed.fingerprint,
            persistent_before=replay_persistent,
            persistent_after=variant.persistent_hash,
            declared_replay_fingerprint=context.fingerprint,
            observed_replay_fingerprint=replay.observed_replay_fingerprint,
            candidate_reachable=not candidate_unreachable,
            note="candidate_unreachable_committed_state_unchanged",
        )
    )
    return OutputHistory(
        case_id=case_id,
        variant=variant.name,
        history_id=history_id,
        output_snapshot=snapshot,
        replay=replay,
        events=tuple(events),
        material_evaluation_count=1 + output_material_count,
        output_read_material_evaluation_count=output_material_count,
        committed_fingerprint_before=committed_before,
        committed_fingerprint_after=variant.committed.fingerprint,
        persistent_fingerprint_before=persistent_before,
        persistent_fingerprint_after=variant.persistent_hash,
        output_read_committed_before=output_read_committed_before,
        output_read_committed_after=output_read_committed_after,
        output_read_persistent_before=output_read_persistent_before,
        output_read_persistent_after=output_read_persistent_after,
        live_trial_candidate_during_output=False,
        candidate_unreachable_after_history=candidate_unreachable,
        all_values_finite=(
            replay.all_values_finite
            and all(event.all_values_finite for event in events)
        ),
    )


def build_insert_output_read_history(
    freeze: dict[str, Any],
    *,
    run_id: str,
    material: MaterialData,
    element: ElementData,
    configuration_hash: str,
) -> OutputHistory:
    return _build_unsafe_replay_history(
        freeze,
        run_id=run_id,
        history_id="insert_output_read",
        seed_output=True,
        material=material,
        element=element,
        configuration_hash=configuration_hash,
    )


def build_direct_history(
    freeze: dict[str, Any],
    *,
    run_id: str,
    material: MaterialData,
    element: ElementData,
    configuration_hash: str,
) -> OutputHistory:
    return _build_unsafe_replay_history(
        freeze,
        run_id=run_id,
        history_id="direct_path",
        seed_output=False,
        material=material,
        element=element,
        configuration_hash=configuration_hash,
    )


def _within_tolerance(
    actual: float,
    expected: float,
    absolute: float,
    relative: float,
) -> bool:
    return math.isclose(actual, expected, abs_tol=absolute, rel_tol=relative)


def compare_output_histories(
    freeze: dict[str, Any],
    *,
    case_id: str,
    left: OutputHistory,
    right: OutputHistory,
) -> OutputProvenanceComparison:
    committed_unchanged = (
        left.committed_fingerprint_before == left.committed_fingerprint_after
        and right.committed_fingerprint_before == right.committed_fingerprint_after
        and left.committed_fingerprint_before == right.committed_fingerprint_before
    )
    candidates_unreachable = (
        left.candidate_unreachable_after_history
        and right.candidate_unreachable_after_history
    )
    all_finite = left.all_values_finite and right.all_values_finite

    if case_id == "L2-OP-01":
        if left.output_snapshot is None or right.output_snapshot is None:
            raise ValueError("OP-01 requires two output snapshots")
        output_equal = left.output_snapshot.fingerprint == right.output_snapshot.fingerprint
        payload_exact = (
            left.output_snapshot.fingerprint == AUTHORITATIVE_ACCEPTED_OUTPUT_HASH
            and right.output_snapshot.fingerprint == AUTHORITATIVE_ACCEPTED_OUTPUT_HASH
        )
        return OutputProvenanceComparison(
            case_id=case_id,
            left_id=left.history_id,
            right_id=right.history_id,
            output_snapshot_exact_equal=output_equal,
            accepted_output_payload_exact=payload_exact,
            output_sources_valid=(
                left.output_snapshot.accepted_source_valid
                and right.output_snapshot.accepted_source_valid
            ),
            output_read_no_evaluation=(
                left.output_read_material_evaluation_count == 0
                and right.output_read_material_evaluation_count == 0
            ),
            live_trial_candidate_during_output=(
                left.live_trial_candidate_during_output
            ),
            output_read_committed_unchanged=(
                left.output_read_committed_before == left.output_read_committed_after
                and right.output_read_committed_before
                == right.output_read_committed_after
            ),
            output_read_persistent_unchanged=(
                left.output_read_persistent_before == left.output_read_persistent_after
                and right.output_read_persistent_before
                == right.output_read_persistent_after
            ),
            trial_candidate_unreachable_after_reject=(
                left.candidate_unreachable_after_history
            ),
            seed_output_rejected_as_accepted=None,
            declared_replay_fingerprint_equal=None,
            d1_declared_packet_equal=None,
            observed_replay_fingerprint_equal=None,
            delta_sigma=None,
            delta_residual=None,
            delta_tangent=None,
            oracle_sigma_match=None,
            oracle_residual_match=None,
            oracle_tangent_match=None,
            committed_states_unchanged=committed_unchanged,
            candidates_unreachable=candidates_unreachable,
            all_values_finite=all_finite,
        )

    if left.replay is None or right.replay is None or left.output_snapshot is None:
        raise ValueError("OP-02 requires seeded/direct replays and seed output")
    delta_sigma = left.replay.sigma - right.replay.sigma
    delta_residual = left.replay.residual - right.replay.residual
    delta_tangent = left.replay.tangent - right.replay.tangent
    tolerance = freeze["tolerances"]
    absolute = float(tolerance["analytical_absolute"])
    relative = float(tolerance["analytical_relative"])
    oracle = freeze["analytical_oracle"]["L2-OP-02"]
    return OutputProvenanceComparison(
        case_id=case_id,
        left_id=left.history_id,
        right_id=right.history_id,
        output_snapshot_exact_equal=None,
        accepted_output_payload_exact=None,
        output_sources_valid=None,
        output_read_no_evaluation=None,
        live_trial_candidate_during_output=None,
        output_read_committed_unchanged=None,
        output_read_persistent_unchanged=None,
        trial_candidate_unreachable_after_reject=None,
        seed_output_rejected_as_accepted=(
            not left.output_snapshot.output_accepted_flag
            and left.output_snapshot.source_version == "trial_hidden"
            and left.output_snapshot.source_candidate_id == "output_hidden_candidate"
        ),
        declared_replay_fingerprint_equal=(
            left.replay.declared_replay_context_fingerprint
            == right.replay.declared_replay_context_fingerprint
        ),
        d1_declared_packet_equal=(
            left.replay.d1_declared_packet_hash == right.replay.d1_declared_packet_hash
        ),
        observed_replay_fingerprint_equal=(
            left.replay.observed_replay_fingerprint
            == right.replay.observed_replay_fingerprint
        ),
        delta_sigma=delta_sigma,
        delta_residual=delta_residual,
        delta_tangent=delta_tangent,
        oracle_sigma_match=_within_tolerance(
            delta_sigma,
            _fraction(oracle["delta_sigma"]),
            absolute,
            relative,
        ),
        oracle_residual_match=_within_tolerance(
            delta_residual,
            _fraction(oracle["delta_residual"]),
            absolute,
            relative,
        ),
        oracle_tangent_match=_within_tolerance(
            delta_tangent,
            _fraction(oracle["delta_tangent"]),
            absolute,
            relative,
        ),
        committed_states_unchanged=committed_unchanged,
        candidates_unreachable=candidates_unreachable,
        all_values_finite=all_finite,
    )


def classify_output_provenance_case(
    case_id: str,
    comparison: OutputProvenanceComparison,
    *,
    unsafe_drift_floor: float,
) -> tuple[str, bool]:
    if case_id == "L2-OP-01":
        passed = all(
            (
                comparison.output_snapshot_exact_equal,
                comparison.accepted_output_payload_exact,
                comparison.output_sources_valid,
                comparison.output_read_no_evaluation,
                comparison.live_trial_candidate_during_output,
                comparison.output_read_committed_unchanged,
                comparison.output_read_persistent_unchanged,
                comparison.trial_candidate_unreachable_after_reject,
                comparison.committed_states_unchanged,
                comparison.candidates_unreachable,
                comparison.all_values_finite,
            )
        )
        return (
            EXPECTED_CLASSIFICATIONS[case_id]
            if passed
            else "FAIL_ACCEPTED_OUTPUT_PROVENANCE",
            passed,
        )

    passed = all(
        (
            comparison.seed_output_rejected_as_accepted,
            comparison.declared_replay_fingerprint_equal,
            comparison.d1_declared_packet_equal,
            comparison.observed_replay_fingerprint_equal is False,
            comparison.delta_residual is not None
            and abs(comparison.delta_residual) >= unsafe_drift_floor,
            comparison.oracle_sigma_match,
            comparison.oracle_residual_match,
            comparison.oracle_tangent_match,
            comparison.committed_states_unchanged,
            comparison.candidates_unreachable,
            comparison.all_values_finite,
        )
    )
    return (
        EXPECTED_CLASSIFICATIONS[case_id]
        if passed
        else "UNSAFE_OUTPUT_FEEDBACK_NOT_DETECTED",
        passed,
    )


def execute_output_provenance_case(
    root: str | Path,
    case_id: str,
    run_id: str,
) -> OutputProvenanceCaseResult:
    """Execute one future-authorized in-memory case without writing outputs."""

    if case_id not in AUTHORIZED_CASES:
        raise ValueError(f"Unauthorized L2-D4 case: {case_id}")
    if not run_id or not run_id.strip():
        raise ValueError("run_id must be a non-empty independent-process label")
    freeze, matrix = load_frozen_design(root)
    row = next(item for item in matrix if item["case_id"] == case_id)
    if row["expected_classification"] != EXPECTED_CLASSIFICATIONS[case_id]:
        raise ValueError("Case classification differs from the freeze")

    material = MaterialData()
    element = ElementData()
    configuration_hash = _configuration_hash(material, element)
    if case_id == "L2-OP-01":
        left = build_trial_then_output_history(
            freeze,
            run_id=run_id,
            material=material,
            element=element,
            configuration_hash=configuration_hash,
        )
        right = build_accepted_output_only_history(
            freeze,
            run_id=run_id,
            material=material,
        )
    else:
        left = build_insert_output_read_history(
            freeze,
            run_id=run_id,
            material=material,
            element=element,
            configuration_hash=configuration_hash,
        )
        right = build_direct_history(
            freeze,
            run_id=run_id,
            material=material,
            element=element,
            configuration_hash=configuration_hash,
        )
    comparison = compare_output_histories(
        freeze,
        case_id=case_id,
        left=left,
        right=right,
    )
    observed, passed = classify_output_provenance_case(
        case_id,
        comparison,
        unsafe_drift_floor=float(
            freeze["tolerances"]["unsafe_minimum_finite_drift"]
        ),
    )
    return OutputProvenanceCaseResult(
        design_version=DESIGN_VERSION,
        host_version=HOST_VERSION,
        implementation_status=IMPLEMENTATION_STATUS,
        case_id=case_id,
        run_id=run_id,
        variant=row["implementation"],
        left_history=left,
        right_history=right,
        comparison=comparison,
        expected_classification=EXPECTED_CLASSIFICATIONS[case_id],
        observed_classification=observed,
        pass_flag=passed,
    )


__all__ = [
    "AUTHORIZED_CASES",
    "COMPARISON_COLUMNS",
    "DESIGN_VERSION",
    "EVENT_LOG_COLUMNS",
    "HOST_VERSION",
    "OutputEventPacket",
    "OutputHistory",
    "OutputProvenanceCaseResult",
    "OutputProvenanceComparison",
    "OutputSnapshot",
    "ReplayContext",
    "ReplayObservation",
    "UnsafeOutputFeedback",
    "build_accepted_output_only_history",
    "build_direct_history",
    "build_insert_output_read_history",
    "build_trial_then_output_history",
    "classify_output_provenance_case",
    "compare_output_histories",
    "execute_output_provenance_case",
    "load_frozen_design",
    "read_accepted_output",
    "validate_frozen_design",
]
