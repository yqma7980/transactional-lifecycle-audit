from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import platform
import sys
from typing import Any, Iterable, Mapping

from .adapters import RawObservation
from .canonical import canonical_sha256
from .model import LifecycleSignals, PrecomparisonRelation, ReplayPacket


RUNTIME_SCHEMA_VERSION = "JSS-P5B-RUNTIME-OBSERVATION-1.0"
RUNTIME_IMPLEMENTATION_REVISION = "JSS-P5B1-RUNTIME-1.0"


def jsonable(value: Any) -> Any:
    """Convert frozen subject values to ordinary JSON-compatible objects."""
    if hasattr(value, "item") and callable(value.item):
        try:
            return jsonable(value.item())
        except ValueError:
            pass
    if hasattr(value, "tolist") and callable(value.tolist):
        return jsonable(value.tolist())
    if isinstance(value, Mapping):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return [jsonable(item) for item in sorted(value, key=str)]
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("runtime evidence cannot contain a non-finite float")
        return value
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if hasattr(value, "__dataclass_fields__"):
        return jsonable(asdict(value))
    raise TypeError(f"unsupported runtime evidence type: {type(value).__name__}")


def semantic_hash(label: str, value: Any) -> str:
    return canonical_sha256({"label": label, "value": jsonable(value)})


def replay_packet(
    *,
    primary: Any,
    committed: Any,
    persistent: Any,
    load: Any,
    residual_version: str,
    tangent_version: str,
    environment: Any,
) -> ReplayPacket:
    return ReplayPacket(
        primary_state_hash=semantic_hash("primary", primary),
        committed_state_hash=semantic_hash("committed", committed),
        persistent_projection_hash=semantic_hash("persistent", persistent),
        load_hash=semantic_hash("load", load),
        residual_version=residual_version,
        tangent_version=tangent_version,
        environment_hash=semantic_hash("environment", environment),
    )


_VOLATILE_EVENT_KEYS = frozenset(
    {
        "run_id",
        "path_id",
        "attempt_id",
        "solve_id",
        "event_id",
        "candidate_id",
        "candidate_source_event_id",
        "accepted_residual_event_id",
        "source_event_id",
        "rejected_candidate",
        "direct_candidate",
        "perturbed_candidate",
    }
)


def _semanticize(value: Any, run_id: str) -> Any:
    value = jsonable(value)
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            lowered = key.lower()
            if key in _VOLATILE_EVENT_KEYS or lowered.endswith("candidate_id"):
                continue
            result[key] = _semanticize(item, run_id)
        return result
    if isinstance(value, list):
        return [_semanticize(item, run_id) for item in value]
    if isinstance(value, str) and run_id:
        return value.replace(run_id, "<RUN_ID>")
    return value


def runtime_environment(subject_id: str, *, backend: Mapping[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "subject_id": subject_id,
        "python": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform_system": platform.system(),
        "platform_machine": platform.machine(),
        "processes": 1,
        "threads": 1,
    }
    if backend:
        payload["backend"] = jsonable(backend)
    return payload


@dataclass(frozen=True)
class RuntimeRecord:
    case_id: str
    run_id: str
    subject_id: str
    runtime_mode: str
    raw: RawObservation
    events: tuple[dict[str, Any], ...]
    measurements: dict[str, Any]
    environment: dict[str, Any]

    def _raw_payload(self) -> dict[str, Any]:
        return {
            "packet_a": asdict(self.raw.packet_a),
            "packet_b": asdict(self.raw.packet_b),
            "precomparison_relation": self.raw.precomparison_relation.value,
            "lifecycle_signals": asdict(self.raw.lifecycle_signals),
            "evidence_tokens": list(self.raw.evidence_tokens),
            "execution_error": self.raw.execution_error,
        }

    def semantic_projection(self) -> dict[str, Any]:
        return {
            "schema_version": RUNTIME_SCHEMA_VERSION,
            "implementation_revision": RUNTIME_IMPLEMENTATION_REVISION,
            "case_id": self.case_id,
            "subject_id": self.subject_id,
            "runtime_mode": self.runtime_mode,
            "raw_observation": self._raw_payload(),
            "events": _semanticize(self.events, self.run_id),
            "measurements": _semanticize(self.measurements, self.run_id),
            "environment": _semanticize(self.environment, self.run_id),
        }

    @property
    def semantic_fingerprint(self) -> str:
        return canonical_sha256(self.semantic_projection())

    def to_dict(self) -> dict[str, Any]:
        payload = self.semantic_projection()
        payload["run_id"] = self.run_id
        payload["events"] = jsonable(self.events)
        payload["measurements"] = jsonable(self.measurements)
        payload["environment"] = jsonable(self.environment)
        payload["semantic_fingerprint"] = self.semantic_fingerprint
        payload["event_count"] = len(self.events)
        return payload


def raw_observation(
    packet_a: ReplayPacket,
    packet_b: ReplayPacket,
    relation: PrecomparisonRelation,
    *,
    evidence_tokens: Iterable[str],
    signal_names: Iterable[str] = (),
) -> RawObservation:
    signal_set = frozenset(signal_names)
    allowed = set(LifecycleSignals().__dict__)
    unknown = signal_set.difference(allowed)
    if unknown:
        raise ValueError(f"unknown lifecycle signals: {sorted(unknown)}")
    signals = LifecycleSignals(**{name: name in signal_set for name in allowed})
    return RawObservation(
        packet_a=packet_a,
        packet_b=packet_b,
        precomparison_relation=relation,
        lifecycle_signals=signals,
        evidence_tokens=tuple(evidence_tokens),
    )


def assert_finite(values: Iterable[float]) -> None:
    for value in values:
        number = float(value)
        if not math.isfinite(number) or abs(number) >= 1.0e100:
            raise RuntimeError(f"non-finite runtime value: {number!r}")


def max_abs_delta(left: Iterable[float], right: Iterable[float]) -> float:
    pairs = tuple(zip(left, right))
    if not pairs:
        return 0.0
    return max(abs(float(a) - float(b)) for a, b in pairs)
