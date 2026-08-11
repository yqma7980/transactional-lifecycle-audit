from __future__ import annotations

from typing import Any

from .model import ContractError, PrecomparisonRelation
from .runtime import RUNTIME_IMPLEMENTATION_REVISION, RUNTIME_SCHEMA_VERSION


RUNTIME_REQUIRED_KEYS = frozenset(
    {
        "schema_version",
        "implementation_revision",
        "case_id",
        "run_id",
        "subject_id",
        "runtime_mode",
        "raw_observation",
        "events",
        "measurements",
        "environment",
        "semantic_fingerprint",
        "event_count",
    }
)


def validate_runtime_observation_payload(payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict) or frozenset(payload) != RUNTIME_REQUIRED_KEYS:
        raise ContractError("runtime observation keys differ from the frozen schema")
    if payload["schema_version"] != RUNTIME_SCHEMA_VERSION:
        raise ContractError("runtime observation schema version drift")
    if payload["implementation_revision"] != RUNTIME_IMPLEMENTATION_REVISION:
        raise ContractError("runtime implementation revision drift")
    if payload["run_id"] not in {"run_1", "run_2"}:
        raise ContractError("runtime run ID is outside the formal contract")
    if payload["subject_id"] not in {"JSS-S01", "JSS-S02", "JSS-S03"}:
        raise ContractError("runtime subject is outside the frozen matrix")
    if not isinstance(payload["events"], list):
        raise ContractError("runtime events must be a list")
    if payload["event_count"] != len(payload["events"]):
        raise ContractError("runtime event count does not match the ledger")
    for key in ("measurements", "environment", "raw_observation"):
        if not isinstance(payload[key], dict):
            raise ContractError(f"runtime {key} must be an object")
    raw = payload["raw_observation"]
    required_raw = {
        "packet_a",
        "packet_b",
        "precomparison_relation",
        "lifecycle_signals",
        "evidence_tokens",
        "execution_error",
    }
    if set(raw) != required_raw:
        raise ContractError("raw observation keys differ from the frozen schema")
    PrecomparisonRelation(raw["precomparison_relation"])
    fingerprint = payload["semantic_fingerprint"]
    if not isinstance(fingerprint, str) or len(fingerprint) != 64:
        raise ContractError("runtime semantic fingerprint is not SHA-256")
    try:
        int(fingerprint, 16)
    except ValueError as exc:
        raise ContractError("runtime semantic fingerprint is not hexadecimal") from exc
