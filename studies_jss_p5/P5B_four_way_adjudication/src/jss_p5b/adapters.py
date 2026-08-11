from __future__ import annotations

from dataclasses import dataclass, field

from .cases import CaseSpec
from .model import (
    AdjudicationRequest,
    CapabilityReport,
    ContractError,
    LifecycleSignals,
    PrecomparisonRelation,
    ReplayPacket,
    Verdict,
)


MECHANISM_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "DECLARED_VERSIONED_TANGENT_LAG": ("OPERATOR_PACKET_VERSIONS",),
    "DIAGNOSTIC_ONLY_PERSISTENT_STATE": (
        "DIAGNOSTIC_FIELD_OWNERSHIP",
        "SEMANTIC_PERSISTENT_PROJECTION",
    ),
    "LEGAL_CALLBACK_ORDER_VARIATION": ("CALLBACK_LEDGER", "REPLAY_PACKET"),
    "LEGITIMATE_CHECKPOINT_RESTART": ("ACCEPTED_OUTPUT", "CHECKPOINT_STATE"),
    "POST_COMMIT_OUTPUT_ONLY": ("COMMIT_REACHABILITY", "OUTPUT_CANDIDATE"),
    "F03_PREMATURE_COMMIT": (
        "COMMIT_BOUNDARY",
        "COMMITTED_FINGERPRINT",
        "REJECT_EVENT",
    ),
    "F05_OUTPUT_FEEDBACK": ("LATER_OPERATOR", "OUTPUT_SOURCE"),
    "F07_CALLBACK_ORDER_BIAS": ("CALLBACK_LEDGER", "PERSISTENT_FINGERPRINT"),
    "F08_WITHIN_HISTORY_VERSION_VIOLATION": ("WITHIN_HISTORY_OPERATOR_VERSIONS",),
    "F05_REJECTED_CANDIDATE_OUTPUT": ("CANDIDATE_REACHABILITY", "OUTPUT_SOURCE"),
    "PRIMARY_STATE_MISMATCH": ("PRIMARY_STATE_FINGERPRINTS",),
    "COMMITTED_PROJECTION_MISMATCH": (
        "COMMITTED_FINGERPRINT",
        "SEMANTIC_PERSISTENT_PROJECTION",
    ),
    "LOAD_MISMATCH": ("LOAD_PACKET_HASHES",),
    "PRECOMPARISON_VERSION_MISMATCH": ("PRE_REPLAY_OPERATOR_VERSIONS",),
    "BOUNDARY_CONTROL_MISMATCH": ("BOUNDARY_CONTROL_HASHES",),
    "NATIVE_CHECKPOINT_PATH": ("NATIVE_CHECKPOINT_EVENT",),
    "NATIVE_OPERATOR_VERSION_METADATA": ("NATIVE_OPERATOR_VERSION_FIELDS",),
    "NATIVE_REJECTED_LINESEARCH_EVENT": ("NATIVE_REJECTED_LINESEARCH_EVENT",),
    "UNSELECTED_NATIVE_LINESEARCH_CANDIDATE": (
        "UNSELECTED_NATIVE_LINESEARCH_CANDIDATE",
    ),
    "PARALLEL_CALLBACK_OWNERSHIP": ("PARALLEL_CALLBACK_OWNERSHIP",),
}


SUBJECT_CAPABILITIES: dict[str, frozenset[str]] = {
    "JSS-S01": frozenset(
        {
            "ACCEPTED_OUTPUT",
            "BOUNDARY_CONTROL_HASHES",
            "CANDIDATE_REACHABILITY",
            "CHECKPOINT_STATE",
            "COMMIT_BOUNDARY",
            "COMMIT_REACHABILITY",
            "COMMITTED_FINGERPRINT",
            "OUTPUT_CANDIDATE",
            "OUTPUT_SOURCE",
            "REJECT_EVENT",
            "SEMANTIC_PERSISTENT_PROJECTION",
        }
    ),
    "JSS-S02": frozenset(
        {
            "LATER_OPERATOR",
            "LOAD_PACKET_HASHES",
            "OPERATOR_PACKET_VERSIONS",
            "OUTPUT_SOURCE",
            "PRE_REPLAY_OPERATOR_VERSIONS",
            "PRIMARY_STATE_FINGERPRINTS",
            "WITHIN_HISTORY_OPERATOR_VERSIONS",
        }
    ),
    "JSS-S03": frozenset(
        {
            "CALLBACK_LEDGER",
            "DIAGNOSTIC_FIELD_OWNERSHIP",
            "LOAD_PACKET_HASHES",
            "PERSISTENT_FINGERPRINT",
            "REPLAY_PACKET",
            "SEMANTIC_PERSISTENT_PROJECTION",
        }
    ),
}


EVENT_TOKENS = frozenset(
    {
        "CALLBACK_LEDGER",
        "CHECKPOINT_STATE",
        "NATIVE_CHECKPOINT_EVENT",
        "NATIVE_REJECTED_LINESEARCH_EVENT",
        "PARALLEL_CALLBACK_OWNERSHIP",
        "REJECT_EVENT",
        "UNSELECTED_NATIVE_LINESEARCH_CANDIDATE",
    }
)


FROZEN_PACKET_MISMATCH_FIELDS: dict[str, tuple[str, ...]] = {
    "DECLARED_VERSIONED_TANGENT_LAG": ("tangent_version",),
    "PRIMARY_STATE_MISMATCH": ("primary_state_hash",),
    "COMMITTED_PROJECTION_MISMATCH": (
        "committed_state_hash",
        "persistent_projection_hash",
    ),
    "LOAD_MISMATCH": ("load_hash",),
    "PRECOMPARISON_VERSION_MISMATCH": ("tangent_version",),
    "BOUNDARY_CONTROL_MISMATCH": ("environment_hash",),
}


@dataclass(frozen=True)
class RawObservation:
    packet_a: ReplayPacket
    packet_b: ReplayPacket
    precomparison_relation: PrecomparisonRelation
    lifecycle_signals: LifecycleSignals = field(default_factory=LifecycleSignals)
    evidence_tokens: tuple[str, ...] = field(default_factory=tuple)
    execution_error: str | None = None


class FrozenSubjectAdapter:
    def __init__(self, subject_id: str) -> None:
        if subject_id not in SUBJECT_CAPABILITIES:
            raise ContractError(f"unknown frozen subject: {subject_id}")
        self.subject_id = subject_id

    def adapt(
        self,
        case: CaseSpec,
        raw: RawObservation,
        *,
        run_id: str,
    ) -> AdjudicationRequest:
        if case.subject_id != self.subject_id:
            raise ContractError(
                f"case {case.case_id} belongs to {case.subject_id}, not {self.subject_id}"
            )
        if raw.execution_error is None:
            if raw.precomparison_relation is not case.precomparison_relation:
                raise ContractError(
                    f"case {case.case_id} reported {raw.precomparison_relation.value}, "
                    f"but the frozen relation is {case.precomparison_relation.value}"
                )
            expected_mismatch = FROZEN_PACKET_MISMATCH_FIELDS.get(
                case.fault_or_control,
                (),
            )
            observed_mismatch = raw.packet_a.differing_fields(raw.packet_b)
            if observed_mismatch != expected_mismatch:
                raise ContractError(
                    f"case {case.case_id} packet mismatch drift: "
                    f"observed={observed_mismatch}, expected={expected_mismatch}"
                )
        try:
            required = MECHANISM_REQUIREMENTS[case.fault_or_control]
        except KeyError as exc:
            raise ContractError(
                f"unfrozen mechanism: {case.fault_or_control}"
            ) from exc
        structural = SUBJECT_CAPABILITIES[self.subject_id]
        emitted = frozenset(raw.evidence_tokens)
        available = tuple(sorted(structural.intersection(emitted)))
        missing = tuple(sorted(set(required).difference(available)))
        missing_events = tuple(item for item in missing if item in EVENT_TOKENS)
        missing_fields = tuple(item for item in missing if item not in EVENT_TOKENS)
        capability = CapabilityReport(
            observable=not missing,
            required_tokens=tuple(sorted(required)),
            available_tokens=available,
            missing_fields=missing_fields,
            missing_events=missing_events,
        )
        return AdjudicationRequest(
            case_id=case.case_id,
            run_id=run_id,
            subject_id=case.subject_id,
            partition=case.partition,
            expected_verdict=case.target_verdict,
            capability=capability,
            packet_a=raw.packet_a,
            packet_b=raw.packet_b,
            precomparison_relation=raw.precomparison_relation,
            lifecycle_signals=raw.lifecycle_signals,
            execution_error=raw.execution_error,
        )


def adapter_for_subject(subject_id: str) -> FrozenSubjectAdapter:
    return FrozenSubjectAdapter(subject_id)


def safe_null_request(subject_id: str, run_id: str) -> AdjudicationRequest:
    if subject_id not in SUBJECT_CAPABILITIES:
        raise ContractError(f"unknown frozen subject: {subject_id}")
    packet = ReplayPacket(
        primary_state_hash="SAFE-PRIMARY-0",
        committed_state_hash="SAFE-COMMITTED-0",
        persistent_projection_hash="SAFE-PERSISTENT-0",
        load_hash="SAFE-LOAD-0",
        residual_version="SAFE-R-1",
        tangent_version="SAFE-J-1",
        environment_hash="SAFE-ENV-1",
    )
    return AdjudicationRequest(
        case_id=f"P5B-PREFLIGHT-SAFE-NULL-{subject_id.removeprefix('JSS-')}",
        run_id=run_id,
        subject_id=subject_id,
        partition="PREFLIGHT_ONLY",
        expected_verdict=Verdict.PASS_INVARIANT,
        capability=CapabilityReport(
            observable=True,
            required_tokens=("SAFE_NULL",),
            available_tokens=("SAFE_NULL",),
        ),
        packet_a=packet,
        packet_b=packet,
        precomparison_relation=PrecomparisonRelation.COMPATIBLE,
        lifecycle_signals=LifecycleSignals(),
    )
