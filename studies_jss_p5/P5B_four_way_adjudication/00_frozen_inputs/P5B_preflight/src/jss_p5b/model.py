from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .canonical import canonical_sha256


class ContractError(ValueError):
    pass


class Verdict(str, Enum):
    PASS_INVARIANT = "PASS_INVARIANT"
    DETECT_LIFECYCLE_DRIFT = "DETECT_LIFECYCLE_DRIFT"
    INVALID = "INVALID"
    NOT_SUPPORTED = "NOT_SUPPORTED"


class Outcome(str, Enum):
    PASS_INVARIANT = "PASS_INVARIANT"
    DETECT_LIFECYCLE_DRIFT = "DETECT_LIFECYCLE_DRIFT"
    INVALID = "INVALID"
    NOT_SUPPORTED = "NOT_SUPPORTED"
    EXECUTION_ERROR = "EXECUTION_ERROR"


class PrecomparisonRelation(str, Enum):
    COMPATIBLE = "compatible"
    INCOMPATIBLE = "incompatible"
    NOT_EVALUATED = "not_evaluated"


def _require_token(name: str, value: str) -> None:
    if not value or not value.isascii():
        raise ContractError(f"{name} must be nonempty ASCII")
    if "\n" in value or "\r" in value or "|" in value:
        raise ContractError(f"{name} contains a forbidden delimiter")


@dataclass(frozen=True)
class ReplayPacket:
    primary_state_hash: str
    committed_state_hash: str
    persistent_projection_hash: str
    load_hash: str
    residual_version: str
    tangent_version: str
    environment_hash: str

    def __post_init__(self) -> None:
        for name, value in self.__dict__.items():
            _require_token(name, value)

    def differing_fields(self, other: "ReplayPacket") -> tuple[str, ...]:
        return tuple(
            name
            for name in self.__dict__
            if getattr(self, name) != getattr(other, name)
        )

    @property
    def fingerprint(self) -> str:
        return canonical_sha256(self)


@dataclass(frozen=True)
class CapabilityReport:
    observable: bool
    required_tokens: tuple[str, ...] = field(default_factory=tuple)
    available_tokens: tuple[str, ...] = field(default_factory=tuple)
    missing_fields: tuple[str, ...] = field(default_factory=tuple)
    missing_events: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        for collection in (
            self.required_tokens,
            self.available_tokens,
            self.missing_fields,
            self.missing_events,
        ):
            for value in collection:
                _require_token("capability token", value)
        if self.observable and (self.missing_fields or self.missing_events):
            raise ContractError("observable capability report cannot contain missing evidence")
        if not self.observable and not (self.missing_fields or self.missing_events):
            raise ContractError("unsupported capability report must identify missing evidence")
        if self.observable and not set(self.required_tokens).issubset(self.available_tokens):
            raise ContractError("observable capability report must provide every required token")


@dataclass(frozen=True)
class LifecycleSignals:
    operator_replay_drift: bool = False
    authoritative_state_mutation: bool = False
    ownership_violation: bool = False
    commit_violation: bool = False
    output_provenance_violation: bool = False
    within_history_version_violation: bool = False

    @property
    def detected(self) -> bool:
        return any(self.__dict__.values())

    @property
    def active_names(self) -> tuple[str, ...]:
        return tuple(name for name, active in self.__dict__.items() if active)


@dataclass(frozen=True)
class AdjudicationRequest:
    case_id: str
    run_id: str
    subject_id: str
    partition: str
    expected_verdict: Verdict
    capability: CapabilityReport
    packet_a: ReplayPacket
    packet_b: ReplayPacket
    precomparison_relation: PrecomparisonRelation
    lifecycle_signals: LifecycleSignals
    execution_error: str | None = None

    def __post_init__(self) -> None:
        for name in ("case_id", "run_id", "subject_id", "partition"):
            _require_token(name, getattr(self, name))
        if self.execution_error is not None:
            _require_token("execution_error", self.execution_error)


@dataclass(frozen=True)
class AdjudicationResult:
    schema_version: str
    implementation_version: str
    case_id: str
    run_id: str
    subject_id: str
    partition: str
    expected_verdict: Verdict
    verdict: Verdict | None
    outcome: Outcome
    stage: str
    pass_flag: bool
    applicability_evaluated: bool
    eligibility_evaluated: bool
    lifecycle_evaluated: bool
    capability: CapabilityReport
    packet_a_fingerprint: str
    packet_b_fingerprint: str
    mismatch_fields: tuple[str, ...]
    active_signals: tuple[str, ...]
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "implementation_version": self.implementation_version,
            "case_id": self.case_id,
            "run_id": self.run_id,
            "subject_id": self.subject_id,
            "partition": self.partition,
            "expected_verdict": self.expected_verdict.value,
            "observed_outcome": self.outcome.value,
            "four_way_verdict": self.verdict.value if self.verdict else None,
            "stage": self.stage,
            "pass_flag": self.pass_flag,
            "applicability_evaluated": self.applicability_evaluated,
            "eligibility_evaluated": self.eligibility_evaluated,
            "lifecycle_evaluated": self.lifecycle_evaluated,
            "capability": {
                "observable": self.capability.observable,
                "required_tokens": list(self.capability.required_tokens),
                "available_tokens": list(self.capability.available_tokens),
                "missing_fields": list(self.capability.missing_fields),
                "missing_events": list(self.capability.missing_events),
            },
            "packet_a_fingerprint": self.packet_a_fingerprint,
            "packet_b_fingerprint": self.packet_b_fingerprint,
            "mismatch_fields": list(self.mismatch_fields),
            "active_signals": list(self.active_signals),
            "reasons": list(self.reasons),
        }

    def semantic_projection(self) -> dict[str, Any]:
        payload = self.to_dict()
        payload.pop("run_id")
        return payload

    @property
    def semantic_fingerprint(self) -> str:
        return canonical_sha256(self.semantic_projection())
