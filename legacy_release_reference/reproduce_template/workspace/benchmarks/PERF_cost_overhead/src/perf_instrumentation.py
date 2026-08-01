"""Cumulative, observation-only audit layers for PERF-D1."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import time
from typing import Any

from benchmarks.L6_external_host.src.l6_state import canonical_json


MODE_FLAGS: dict[str, dict[str, bool]] = {
    "C0": {
        "transaction": False,
        "fingerprint": False,
        "event_log": False,
        "full_provenance": False,
    },
    "C1": {
        "transaction": True,
        "fingerprint": False,
        "event_log": False,
        "full_provenance": False,
    },
    "C2": {
        "transaction": True,
        "fingerprint": True,
        "event_log": False,
        "full_provenance": False,
    },
    "C3": {
        "transaction": True,
        "fingerprint": False,
        "event_log": True,
        "full_provenance": False,
    },
    "C4": {
        "transaction": True,
        "fingerprint": True,
        "event_log": True,
        "full_provenance": True,
    },
}


@dataclass(frozen=True)
class AuditMetrics:
    mode_id: str
    candidate_count: int
    commit_count: int
    accepted_callback_count: int
    event_count: int
    fingerprint_count: int
    serialized_audit_bytes: int
    serialization_time_ns: int
    hashing_time_ns: int
    audit_payload_sha256: str
    accepted_output_provenance_sha256: str


class AuditCollector:
    """Observe a numerical path without changing any accepted numerical value."""

    def __init__(self, mode_id: str) -> None:
        if mode_id not in MODE_FLAGS:
            raise ValueError(f"unknown mode: {mode_id}")
        self.mode_id = mode_id
        self.flags = MODE_FLAGS[mode_id]
        self.candidate_count = 0
        self.commit_count = 0
        self.accepted_callback_count = 0
        self.fingerprint_count = 0
        self.serialization_time_ns = 0
        self.hashing_time_ns = 0
        self.events: list[dict[str, Any]] = []
        self._ordinal = 0

    def _serialize(self, value: Any) -> bytes:
        start = time.perf_counter_ns()
        payload = canonical_json(value).encode("utf-8")
        self.serialization_time_ns += time.perf_counter_ns() - start
        return payload

    def _hash(self, value: Any) -> str:
        payload = self._serialize(value)
        start = time.perf_counter_ns()
        digest = hashlib.sha256(payload).hexdigest()
        self.hashing_time_ns += time.perf_counter_ns() - start
        self.fingerprint_count += 1
        return digest

    def _record(self, event: str, payload: dict[str, Any]) -> None:
        if not self.flags["event_log"]:
            return
        self._ordinal += 1
        self.events.append(
            {
                "ordinal": self._ordinal,
                "event": event,
                "payload": payload,
            }
        )

    def begin_attempt(self, payload: dict[str, Any]) -> None:
        if not self.flags["transaction"]:
            return
        self._record("BeginAttempt", payload)

    def observe_candidate(self, payload: dict[str, Any]) -> None:
        if not self.flags["transaction"]:
            return
        self.candidate_count += 1
        row = dict(payload)
        if self.flags["fingerprint"]:
            row["candidate_fingerprint"] = self._hash(payload)
        self._record("TrialEvaluate", row)

    def observe_tangent(self, payload: dict[str, Any]) -> None:
        if not self.flags["transaction"]:
            return
        row = dict(payload)
        if self.flags["fingerprint"]:
            row["tangent_fingerprint"] = self._hash(payload)
        self._record("FormTangent", row)

    def accepted_callback(self, payload: dict[str, Any]) -> None:
        if not self.flags["transaction"]:
            return
        self.accepted_callback_count += 1
        row = dict(payload)
        if self.flags["fingerprint"]:
            row["accepted_callback_fingerprint"] = self._hash(payload)
        self._record("HostAcceptedCallback", row)

    def commit(self, payload: dict[str, Any]) -> None:
        if not self.flags["transaction"]:
            return
        self.commit_count += 1
        row = dict(payload)
        if self.flags["fingerprint"]:
            row["committed_fingerprint"] = self._hash(payload)
        self._record("Commit", row)

    def finalize(self, accepted_output: dict[str, Any]) -> AuditMetrics:
        provenance_sha = ""
        if self.flags["full_provenance"]:
            provenance = {
                "source": "accepted_state_after_commit",
                "commit_count": self.commit_count,
                "accepted_output": accepted_output,
            }
            provenance_sha = self._hash(provenance)
            self._record(
                "OutputAcceptedState",
                {
                    "source": "accepted_state_after_commit",
                    "provenance_sha256": provenance_sha,
                },
            )

        payload_bytes = b""
        if self.flags["event_log"]:
            payload_bytes = self._serialize(self.events)
        payload_sha = ""
        if self.flags["full_provenance"]:
            start = time.perf_counter_ns()
            payload_sha = hashlib.sha256(payload_bytes).hexdigest()
            self.hashing_time_ns += time.perf_counter_ns() - start
            self.fingerprint_count += 1

        return AuditMetrics(
            mode_id=self.mode_id,
            candidate_count=self.candidate_count,
            commit_count=self.commit_count,
            accepted_callback_count=self.accepted_callback_count,
            event_count=len(self.events),
            fingerprint_count=self.fingerprint_count,
            serialized_audit_bytes=len(payload_bytes),
            serialization_time_ns=self.serialization_time_ns,
            hashing_time_ns=self.hashing_time_ns,
            audit_payload_sha256=payload_sha,
            accepted_output_provenance_sha256=provenance_sha,
        )


__all__ = ["AuditCollector", "AuditMetrics", "MODE_FLAGS"]