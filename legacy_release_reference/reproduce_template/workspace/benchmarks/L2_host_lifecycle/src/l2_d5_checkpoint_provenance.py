"""L2-D5.0a accepted-state checkpoint-provenance benchmark.

Importing this module performs no execution, file creation, logging, process
launch or environment mutation.
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

from .l2_host import NewtonHost
from .l2_state import (
    AcceptedCheckpoint,
    CommittedState,
    ElementData,
    MaterialData,
    canonical_hash,
    canonical_json,
)
from .l2_variants import SafeTransactional


DESIGN_VERSION = "L2-D5.0a"
HOST_VERSION = "L2-HOST-D5.0a"
IMPLEMENTATION_STATUS = "IMPLEMENTED_NOT_EXECUTED"
FREEZE_SHA256 = "90a5df3527b285a424b6a72a5fd75370e9216d1eb34164c163f50a48fb665e63"
CASE_MATRIX_SHA256 = "9b932cb0329be838057469af6395062cdb6a0fe125206f0e02667b35f0b2ccca"
AUTHORIZED_CASES = ("L2-CP-01",)
EXPECTED_CLASSIFICATION = "PASS_CHECKPOINT_ROUND_TRIP"
CHECKPOINT_SCHEMA = "L2-D5-CHECKPOINT-1.0"
ENVELOPE_SCHEMA = "L2-D5-ENVELOPE-1.0"
RESIDUAL_DEFINITION = "L2-R-D1.0"
TANGENT_DEFINITION = "L2-K-D1.0"

EVENT_LOG_COLUMNS = (
    "case_id",
    "run_id",
    "variant",
    "history_id",
    "ordinal",
    "event",
    "accepted_version",
    "force",
    "displacement",
    "reaction",
    "stress",
    "epsilon_p",
    "kappa",
    "committed_state_fingerprint",
    "physical_checkpoint_fingerprint",
    "payload_fingerprint",
    "envelope_sha256",
    "configuration_hash",
    "source_state_unchanged",
    "restored_from_checkpoint",
    "candidate_reachable",
    "all_values_finite",
    "note",
)

COMPARISON_COLUMNS = (
    "case_id",
    "run_id",
    "checkpoint_schema_valid",
    "checkpoint_payload_hash_valid",
    "checkpoint_configuration_valid",
    "checkpoint_bytes_deterministic",
    "source_state_unchanged",
    "restored_committed_fingerprint_exact",
    "restored_primary_state_exact",
    "restored_physical_checkpoint_exact",
    "restored_registry_empty",
    "final_fields_within_tolerance",
    "final_committed_fingerprint_exact",
    "final_physical_checkpoint_exact",
    "analytical_checkpoint_match",
    "analytical_continuation_match",
    "candidates_unreachable",
    "all_values_finite",
    "delta_displacement",
    "delta_reaction",
    "delta_stress",
    "delta_epsilon_p",
    "delta_kappa",
    "classification",
    "pass_flag",
)


@dataclass(frozen=True)
class CheckpointPayload:
    schema_version: str
    design_version: str
    source_host_version: str
    configuration_hash: str
    material_fingerprint: str
    element_fingerprint: str
    residual_definition: str
    tangent_definition: str
    accepted_force_hex: str
    accepted_displacement_hex: str
    accepted_reaction_hex: str
    accepted_stress_hex: str
    accepted_version: int
    epsilon_p_hex: str
    kappa_hex: str
    committed_state_fingerprint: str
    physical_checkpoint_fingerprint: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def fingerprint(self) -> str:
        return canonical_hash(self.to_dict())


@dataclass(frozen=True)
class CheckpointObservation:
    force: float
    displacement: float
    reaction: float
    stress: float
    epsilon_p: float
    kappa: float
    accepted_version: int
    committed_state_fingerprint: str
    physical_checkpoint_fingerprint: str

    @classmethod
    def from_checkpoint(cls, value: AcceptedCheckpoint) -> "CheckpointObservation":
        return cls(
            force=value.force,
            displacement=value.displacement,
            reaction=value.reaction,
            stress=value.stress,
            epsilon_p=value.epsilon_p,
            kappa=value.kappa,
            accepted_version=value.accepted_version,
            committed_state_fingerprint=value.committed_state_hash,
            physical_checkpoint_fingerprint=value.physical_hash,
        )

    @property
    def finite_values(self) -> tuple[float, ...]:
        return (
            self.force,
            self.displacement,
            self.reaction,
            self.stress,
            self.epsilon_p,
            self.kappa,
        )


@dataclass(frozen=True)
class CheckpointEvent:
    case_id: str
    run_id: str
    variant: str
    history_id: str
    ordinal: int
    event: str
    accepted_version: int | None
    force: float | None
    displacement: float | None
    reaction: float | None
    stress: float | None
    epsilon_p: float | None
    kappa: float | None
    committed_state_fingerprint: str
    physical_checkpoint_fingerprint: str
    payload_fingerprint: str
    envelope_sha256: str
    configuration_hash: str
    source_state_unchanged: bool | None
    restored_from_checkpoint: bool
    candidate_reachable: bool
    all_values_finite: bool
    note: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CheckpointComparison:
    checkpoint_schema_valid: bool
    checkpoint_payload_hash_valid: bool
    checkpoint_configuration_valid: bool
    checkpoint_bytes_deterministic: bool
    source_state_unchanged: bool
    restored_committed_fingerprint_exact: bool
    restored_primary_state_exact: bool
    restored_physical_checkpoint_exact: bool
    restored_registry_empty: bool
    final_fields_within_tolerance: bool
    final_committed_fingerprint_exact: bool
    final_physical_checkpoint_exact: bool
    analytical_checkpoint_match: bool
    analytical_continuation_match: bool
    candidates_unreachable: bool
    all_values_finite: bool
    delta_displacement: float
    delta_reaction: float
    delta_stress: float
    delta_epsilon_p: float
    delta_kappa: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CheckpointCaseResult:
    design_version: str
    host_version: str
    implementation_status: str
    case_id: str
    run_id: str
    variant: str
    expected_classification: str
    observed_classification: str
    pass_flag: bool
    configuration_hash: str
    checkpoint_payload: CheckpointPayload
    checkpoint_payload_fingerprint: str
    checkpoint_envelope_sha256: str
    checkpoint_byte_count: int
    reference_source: CheckpointObservation
    restored_source: CheckpointObservation
    reference_final: CheckpointObservation
    restored_final: CheckpointObservation
    source_host_event_count: int
    restored_host_event_count: int
    events: tuple[CheckpointEvent, ...]
    comparison: CheckpointComparison

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _finite(values: tuple[float, ...], limit: float) -> bool:
    return all(math.isfinite(value) and abs(value) <= limit for value in values)


def _configuration_hash(material: MaterialData, element: ElementData) -> str:
    return canonical_hash(
        {
            "design_version": DESIGN_VERSION,
            "host_version": HOST_VERSION,
            "material": material,
            "element": element,
            "residual_version": RESIDUAL_DEFINITION,
            "tangent_version": TANGENT_DEFINITION,
        }
    )


def load_frozen_design(root: Path) -> tuple[dict[str, Any], tuple[dict[str, str], ...]]:
    freeze_path = root / "L2_D5_execution_freeze.json"
    matrix_path = root / "L2_D5_checkpoint_provenance_case_matrix.csv"
    if _sha256_file(freeze_path) != FREEZE_SHA256:
        raise ValueError("L2-D5 freeze hash mismatch")
    if _sha256_file(matrix_path) != CASE_MATRIX_SHA256:
        raise ValueError("L2-D5 case-matrix hash mismatch")
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    with matrix_path.open("r", encoding="utf-8", newline="") as handle:
        matrix = tuple(csv.DictReader(handle))
    validate_frozen_design(freeze, matrix)
    return freeze, matrix


def validate_frozen_design(freeze: dict[str, Any], matrix: tuple[dict[str, str], ...]) -> None:
    if freeze.get("design_version") != DESIGN_VERSION:
        raise ValueError("D5 design version mismatch")
    if freeze.get("design_status") != "FROZEN_NOT_IMPLEMENTED":
        raise ValueError("D5 design status mismatch")
    if freeze.get("execution_authorized") is not False or freeze.get("results_exist") is not False:
        raise ValueError("D5 frozen execution boundary mismatch")
    if freeze.get("extension_version_if_implemented") != HOST_VERSION:
        raise ValueError("D5 host version mismatch")
    if freeze.get("runtime_configuration_hash") != "c4e3373b1ec484567f7c0cdd75727e636282847c6ebc8577f278720069efb0ca":
        raise ValueError("D5 configuration fingerprint mismatch")
    if len(matrix) != 1 or matrix[0].get("case_id") != "L2-CP-01":
        raise ValueError("D5 case matrix mismatch")
    if matrix[0].get("expected_classification") != EXPECTED_CLASSIFICATION:
        raise ValueError("D5 expected classification mismatch")


def build_checkpoint_payload(
    checkpoint: AcceptedCheckpoint,
    *,
    configuration_hash: str,
    material: MaterialData,
    element: ElementData,
) -> CheckpointPayload:
    return CheckpointPayload(
        schema_version=CHECKPOINT_SCHEMA,
        design_version=DESIGN_VERSION,
        source_host_version=HOST_VERSION,
        configuration_hash=configuration_hash,
        material_fingerprint=material.fingerprint,
        element_fingerprint=element.fingerprint,
        residual_definition=RESIDUAL_DEFINITION,
        tangent_definition=TANGENT_DEFINITION,
        accepted_force_hex=checkpoint.force.hex(),
        accepted_displacement_hex=checkpoint.displacement.hex(),
        accepted_reaction_hex=checkpoint.reaction.hex(),
        accepted_stress_hex=checkpoint.stress.hex(),
        accepted_version=checkpoint.accepted_version,
        epsilon_p_hex=checkpoint.epsilon_p.hex(),
        kappa_hex=checkpoint.kappa.hex(),
        committed_state_fingerprint=checkpoint.committed_state_hash,
        physical_checkpoint_fingerprint=checkpoint.physical_hash,
    )


def serialize_checkpoint(payload: CheckpointPayload) -> bytes:
    envelope = {
        "envelope_version": ENVELOPE_SCHEMA,
        "payload": payload.to_dict(),
        "payload_sha256": payload.fingerprint,
    }
    return canonical_json(envelope).encode("ascii")


def deserialize_checkpoint(
    serialized: bytes,
    *,
    expected_configuration_hash: str,
    material: MaterialData,
    element: ElementData,
) -> tuple[CheckpointPayload, CommittedState, AcceptedCheckpoint]:
    try:
        envelope = json.loads(serialized.decode("ascii"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Checkpoint envelope is not canonical ASCII JSON") from exc
    if set(envelope) != {"envelope_version", "payload", "payload_sha256"}:
        raise ValueError("Checkpoint envelope fields mismatch")
    if envelope["envelope_version"] != ENVELOPE_SCHEMA:
        raise ValueError("Checkpoint envelope version mismatch")
    payload_data = envelope["payload"]
    required = set(CheckpointPayload.__dataclass_fields__)
    if not isinstance(payload_data, dict) or set(payload_data) != required:
        raise ValueError("Checkpoint payload fields mismatch")
    payload = CheckpointPayload(**payload_data)
    if payload.fingerprint != envelope["payload_sha256"]:
        raise ValueError("Checkpoint payload hash mismatch")
    if payload.schema_version != CHECKPOINT_SCHEMA or payload.design_version != DESIGN_VERSION:
        raise ValueError("Checkpoint payload schema/design mismatch")
    if payload.source_host_version != HOST_VERSION:
        raise ValueError("Checkpoint source host mismatch")
    if payload.configuration_hash != expected_configuration_hash:
        raise ValueError("Checkpoint configuration mismatch")
    if payload.material_fingerprint != material.fingerprint or payload.element_fingerprint != element.fingerprint:
        raise ValueError("Checkpoint model identity mismatch")
    if payload.residual_definition != RESIDUAL_DEFINITION or payload.tangent_definition != TANGENT_DEFINITION:
        raise ValueError("Checkpoint operator identity mismatch")

    committed = CommittedState(
        epsilon_p=float.fromhex(payload.epsilon_p_hex),
        kappa=float.fromhex(payload.kappa_hex),
        accepted_version=payload.accepted_version,
    )
    if committed.fingerprint != payload.committed_state_fingerprint:
        raise ValueError("Checkpoint committed-state fingerprint mismatch")
    checkpoint = AcceptedCheckpoint(
        force=float.fromhex(payload.accepted_force_hex),
        displacement=float.fromhex(payload.accepted_displacement_hex),
        reaction=float.fromhex(payload.accepted_reaction_hex),
        stress=float.fromhex(payload.accepted_stress_hex),
        epsilon_p=committed.epsilon_p,
        kappa=committed.kappa,
        accepted_version=committed.accepted_version,
        committed_state_hash=committed.fingerprint,
    )
    if checkpoint.physical_hash != payload.physical_checkpoint_fingerprint:
        raise ValueError("Checkpoint physical fingerprint mismatch")
    return payload, committed, checkpoint


def _within(value: float, expected: Fraction, *, atol: float, rtol: float) -> bool:
    return math.isclose(value, float(expected), abs_tol=atol, rel_tol=rtol)


def _analytical_match(observation: CheckpointObservation, *, final: bool, atol: float, rtol: float) -> bool:
    expected = {
        "force": Fraction(6, 5) if final else Fraction(11, 10),
        "displacement": Fraction(4, 125) if final else Fraction(21, 1000),
        "reaction": Fraction(6, 5) if final else Fraction(11, 10),
        "stress": Fraction(6, 5) if final else Fraction(11, 10),
        "epsilon_p": Fraction(1, 50) if final else Fraction(1, 100),
        "kappa": Fraction(1, 50) if final else Fraction(1, 100),
    }
    return all(_within(getattr(observation, key), value, atol=atol, rtol=rtol) for key, value in expected.items())


def _event(
    *,
    case_id: str,
    run_id: str,
    history_id: str,
    ordinal: int,
    event: str,
    observation: CheckpointObservation | None,
    payload_fingerprint: str,
    envelope_sha256: str,
    configuration_hash: str,
    source_state_unchanged: bool | None,
    restored: bool,
    candidate_reachable: bool,
    all_values_finite: bool,
    note: str,
) -> CheckpointEvent:
    return CheckpointEvent(
        case_id=case_id,
        run_id=run_id,
        variant="safe_transactional",
        history_id=history_id,
        ordinal=ordinal,
        event=event,
        accepted_version=None if observation is None else observation.accepted_version,
        force=None if observation is None else observation.force,
        displacement=None if observation is None else observation.displacement,
        reaction=None if observation is None else observation.reaction,
        stress=None if observation is None else observation.stress,
        epsilon_p=None if observation is None else observation.epsilon_p,
        kappa=None if observation is None else observation.kappa,
        committed_state_fingerprint="NA" if observation is None else observation.committed_state_fingerprint,
        physical_checkpoint_fingerprint="NA" if observation is None else observation.physical_checkpoint_fingerprint,
        payload_fingerprint=payload_fingerprint,
        envelope_sha256=envelope_sha256,
        configuration_hash=configuration_hash,
        source_state_unchanged=source_state_unchanged,
        restored_from_checkpoint=restored,
        candidate_reachable=candidate_reachable,
        all_values_finite=all_values_finite,
        note=note,
    )


def classify_checkpoint_case(comparison: CheckpointComparison) -> tuple[str, bool]:
    passed = all(
        (
            comparison.checkpoint_schema_valid,
            comparison.checkpoint_payload_hash_valid,
            comparison.checkpoint_configuration_valid,
            comparison.checkpoint_bytes_deterministic,
            comparison.source_state_unchanged,
            comparison.restored_committed_fingerprint_exact,
            comparison.restored_primary_state_exact,
            comparison.restored_physical_checkpoint_exact,
            comparison.restored_registry_empty,
            comparison.final_fields_within_tolerance,
            comparison.final_committed_fingerprint_exact,
            comparison.final_physical_checkpoint_exact,
            comparison.analytical_checkpoint_match,
            comparison.analytical_continuation_match,
            comparison.candidates_unreachable,
            comparison.all_values_finite,
        )
    )
    return (EXPECTED_CLASSIFICATION if passed else "FAIL_CHECKPOINT_ROUND_TRIP", passed)


def execute_checkpoint_provenance_case(root: Path, case_id: str, run_id: str) -> CheckpointCaseResult:
    if case_id not in AUTHORIZED_CASES:
        raise ValueError(f"Unauthorized L2-D5 case: {case_id}")
    freeze, _ = load_frozen_design(root)
    tolerance = freeze["tolerances"]
    atol = float(tolerance["analytical_absolute"])
    rtol = float(tolerance["analytical_relative"])
    finite_limit = float(tolerance["finite_absolute_limit"])

    material = MaterialData()
    element = ElementData()
    configuration_hash = _configuration_hash(material, element)
    if configuration_hash != freeze["runtime_configuration_hash"]:
        raise ValueError("Runtime configuration hash differs from freeze")

    source_variant = SafeTransactional(material)
    source_host = NewtonHost(
        run_id=run_id,
        case_id=case_id,
        history_id="uninterrupted_reference",
        variant=source_variant,
        configuration_hash=configuration_hash,
    )
    source_checkpoint = source_host.solve_increment(target_force=1.1, attempt_id="SOURCE_ACCEPT_1")
    reference_source = CheckpointObservation.from_checkpoint(source_checkpoint)

    source_before = (
        source_variant.committed.fingerprint,
        source_variant.persistent_hash,
        source_host.accepted_displacement.hex(),
        len(source_host.events),
    )
    payload = build_checkpoint_payload(
        source_checkpoint,
        configuration_hash=configuration_hash,
        material=material,
        element=element,
    )
    serialized = serialize_checkpoint(payload)
    serialized_repeat = serialize_checkpoint(payload)
    source_after = (
        source_variant.committed.fingerprint,
        source_variant.persistent_hash,
        source_host.accepted_displacement.hex(),
        len(source_host.events),
    )
    source_state_unchanged = source_before == source_after

    restored_payload, restored_committed, restored_checkpoint = deserialize_checkpoint(
        serialized,
        expected_configuration_hash=configuration_hash,
        material=material,
        element=element,
    )
    restored_source = CheckpointObservation.from_checkpoint(restored_checkpoint)
    restored_variant = SafeTransactional(material)
    empty_registry_hash = restored_variant.persistent_hash
    restored_variant.committed = restored_committed
    restored_registry_empty = restored_variant.persistent_hash == empty_registry_hash
    restored_host = NewtonHost(
        run_id=run_id,
        case_id=case_id,
        history_id="checkpoint_restore",
        variant=restored_variant,
        configuration_hash=configuration_hash,
    )
    restored_host.accepted_displacement = restored_checkpoint.displacement

    reference_final_checkpoint = source_host.solve_increment(target_force=1.2, attempt_id="REFERENCE_CONTINUE_2")
    restored_final_checkpoint = restored_host.solve_increment(target_force=1.2, attempt_id="RESTORED_CONTINUE_2")
    reference_final = CheckpointObservation.from_checkpoint(reference_final_checkpoint)
    restored_final = CheckpointObservation.from_checkpoint(restored_final_checkpoint)

    deltas = {
        key: getattr(restored_final, key) - getattr(reference_final, key)
        for key in ("displacement", "reaction", "stress", "epsilon_p", "kappa")
    }
    final_fields_within_tolerance = all(
        math.isclose(getattr(restored_final, key), getattr(reference_final, key), abs_tol=atol, rel_tol=rtol)
        for key in deltas
    )
    all_values_finite = all(
        _finite(observation.finite_values, finite_limit)
        for observation in (reference_source, restored_source, reference_final, restored_final)
    )
    candidates_unreachable = (
        restored_registry_empty
        and source_variant.persistent_hash == empty_registry_hash
        and restored_variant.persistent_hash == empty_registry_hash
    )
    comparison = CheckpointComparison(
        checkpoint_schema_valid=restored_payload.schema_version == CHECKPOINT_SCHEMA,
        checkpoint_payload_hash_valid=restored_payload.fingerprint == payload.fingerprint,
        checkpoint_configuration_valid=restored_payload.configuration_hash == configuration_hash,
        checkpoint_bytes_deterministic=serialized == serialized_repeat,
        source_state_unchanged=source_state_unchanged,
        restored_committed_fingerprint_exact=restored_committed.fingerprint == source_checkpoint.committed_state_hash,
        restored_primary_state_exact=restored_checkpoint.displacement.hex() == source_checkpoint.displacement.hex(),
        restored_physical_checkpoint_exact=restored_checkpoint.physical_hash == source_checkpoint.physical_hash,
        restored_registry_empty=restored_registry_empty,
        final_fields_within_tolerance=final_fields_within_tolerance,
        final_committed_fingerprint_exact=restored_final.committed_state_fingerprint == reference_final.committed_state_fingerprint,
        final_physical_checkpoint_exact=restored_final.physical_checkpoint_fingerprint == reference_final.physical_checkpoint_fingerprint,
        analytical_checkpoint_match=_analytical_match(reference_source, final=False, atol=atol, rtol=rtol),
        analytical_continuation_match=(
            _analytical_match(reference_final, final=True, atol=atol, rtol=rtol)
            and _analytical_match(restored_final, final=True, atol=atol, rtol=rtol)
        ),
        candidates_unreachable=candidates_unreachable,
        all_values_finite=all_values_finite,
        delta_displacement=deltas["displacement"],
        delta_reaction=deltas["reaction"],
        delta_stress=deltas["stress"],
        delta_epsilon_p=deltas["epsilon_p"],
        delta_kappa=deltas["kappa"],
    )
    observed_classification, pass_flag = classify_checkpoint_case(comparison)
    envelope_sha256 = _sha256_bytes(serialized)

    events = (
        _event(case_id=case_id, run_id=run_id, history_id="uninterrupted_reference", ordinal=1, event="AcceptCheckpointSource", observation=reference_source, payload_fingerprint=payload.fingerprint, envelope_sha256=envelope_sha256, configuration_hash=configuration_hash, source_state_unchanged=None, restored=False, candidate_reachable=False, all_values_finite=_finite(reference_source.finite_values, finite_limit), note="accepted_version_1_source"),
        _event(case_id=case_id, run_id=run_id, history_id="uninterrupted_reference", ordinal=2, event="CheckpointWrite", observation=reference_source, payload_fingerprint=payload.fingerprint, envelope_sha256=envelope_sha256, configuration_hash=configuration_hash, source_state_unchanged=source_state_unchanged, restored=False, candidate_reachable=False, all_values_finite=True, note="canonical_accepted_state_only"),
        _event(case_id=case_id, run_id=run_id, history_id="checkpoint_restore", ordinal=1, event="CheckpointRead", observation=restored_source, payload_fingerprint=restored_payload.fingerprint, envelope_sha256=envelope_sha256, configuration_hash=configuration_hash, source_state_unchanged=None, restored=True, candidate_reachable=False, all_values_finite=_finite(restored_source.finite_values, finite_limit), note="schema_hash_and_configuration_validated"),
        _event(case_id=case_id, run_id=run_id, history_id="checkpoint_restore", ordinal=2, event="RestoreFreshHost", observation=restored_source, payload_fingerprint=restored_payload.fingerprint, envelope_sha256=envelope_sha256, configuration_hash=configuration_hash, source_state_unchanged=None, restored=True, candidate_reachable=False, all_values_finite=True, note="committed_and_primary_state_restored"),
        _event(case_id=case_id, run_id=run_id, history_id="uninterrupted_reference", ordinal=3, event="ReferenceContinuationAccepted", observation=reference_final, payload_fingerprint=payload.fingerprint, envelope_sha256=envelope_sha256, configuration_hash=configuration_hash, source_state_unchanged=None, restored=False, candidate_reachable=False, all_values_finite=_finite(reference_final.finite_values, finite_limit), note="accepted_version_2_reference"),
        _event(case_id=case_id, run_id=run_id, history_id="checkpoint_restore", ordinal=3, event="RestoredContinuationAccepted", observation=restored_final, payload_fingerprint=restored_payload.fingerprint, envelope_sha256=envelope_sha256, configuration_hash=configuration_hash, source_state_unchanged=None, restored=True, candidate_reachable=False, all_values_finite=_finite(restored_final.finite_values, finite_limit), note="accepted_version_2_restored"),
        _event(case_id=case_id, run_id=run_id, history_id="comparison", ordinal=1, event="CompareRoundTrip", observation=restored_final, payload_fingerprint=payload.fingerprint, envelope_sha256=envelope_sha256, configuration_hash=configuration_hash, source_state_unchanged=source_state_unchanged, restored=True, candidate_reachable=False, all_values_finite=all_values_finite, note=observed_classification),
    )

    return CheckpointCaseResult(
        design_version=DESIGN_VERSION,
        host_version=HOST_VERSION,
        implementation_status=IMPLEMENTATION_STATUS,
        case_id=case_id,
        run_id=run_id,
        variant="safe_transactional",
        expected_classification=EXPECTED_CLASSIFICATION,
        observed_classification=observed_classification,
        pass_flag=pass_flag,
        configuration_hash=configuration_hash,
        checkpoint_payload=payload,
        checkpoint_payload_fingerprint=payload.fingerprint,
        checkpoint_envelope_sha256=envelope_sha256,
        checkpoint_byte_count=len(serialized),
        reference_source=reference_source,
        restored_source=restored_source,
        reference_final=reference_final,
        restored_final=restored_final,
        source_host_event_count=len(source_host.events),
        restored_host_event_count=len(restored_host.events),
        events=events,
        comparison=comparison,
    )


__all__ = [
    "AUTHORIZED_CASES",
    "CASE_MATRIX_SHA256",
    "CHECKPOINT_SCHEMA",
    "COMPARISON_COLUMNS",
    "CheckpointCaseResult",
    "CheckpointComparison",
    "CheckpointEvent",
    "CheckpointObservation",
    "CheckpointPayload",
    "DESIGN_VERSION",
    "ENVELOPE_SCHEMA",
    "EVENT_LOG_COLUMNS",
    "EXPECTED_CLASSIFICATION",
    "FREEZE_SHA256",
    "HOST_VERSION",
    "build_checkpoint_payload",
    "classify_checkpoint_case",
    "deserialize_checkpoint",
    "execute_checkpoint_provenance_case",
    "load_frozen_design",
    "serialize_checkpoint",
    "validate_frozen_design",
]
