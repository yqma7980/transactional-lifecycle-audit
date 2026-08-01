from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from p6r_contracts import NOT_APPLICABLE, NULL_THRESHOLDS
from p6r_projection import MethodProjection


@dataclass(frozen=True)
class DetectionResult:
    method_id: str
    applicable: bool
    anomaly_detected: bool | None
    classification: str
    localization_plane: str
    evidence: Mapping[str, Any]


def _detect_m1(payload: Mapping[str, Any]) -> DetectionResult:
    quiet = all(
        (
            payload["all_values_finite"],
            payload["conventional_quiet"],
            payload["endpoint_quiet"],
            payload["accepted_output_length_equal"],
        )
    )
    return DetectionResult(
        "M1_FINAL",
        True,
        not quiet,
        "PASS_CONVENTIONAL_FINAL_GATE" if quiet else "DETECT_CONVENTIONAL_FINAL_ANOMALY",
        "NONE" if quiet else "ACCEPTED_FINAL_STATE",
        {"gate_vector_all_true": quiet},
    )


def _detect_m4(payload: Mapping[str, Any]) -> DetectionResult:
    packets = payload["operator_packets"]
    matched = bool(packets) and all(
        packet["residual_version"]
        and packet["tangent_version"]
        and packet["compatibility_relation"] in {"EXACT_CURRENT", "DECLARED_LAGGED"}
        for packet in packets
    )
    return DetectionResult(
        "M4_OPERATOR",
        True,
        not matched,
        "PASS_MATCHED_OPERATOR_VERSION_PACKET" if matched else "REJECT_OPERATOR_VERSION_MISMATCH",
        "NONE" if matched else "OPERATOR_VERSION",
        {"operator_packet_count": len(packets), "all_packets_compatible": matched},
    )


def _detect_m5(payload: Mapping[str, Any]) -> DetectionResult:
    metrics = payload["operator_replay_metric_distances"]
    exceeded = {
        key: value
        for key, value in metrics.items()
        if key in NULL_THRESHOLDS and value > NULL_THRESHOLDS[key]
    }
    detected = bool(exceeded)
    return DetectionResult(
        "M5_META",
        True,
        detected,
        "DETECT_EQUAL_INPUT_OPERATOR_REPLAY_DRIFT" if detected else "PASS_META_NULL_ENVELOPE",
        "REPLAY_RELATION" if detected else "NONE",
        {"threshold_exceedances": exceeded},
    )


def _detect_m6(payload: Mapping[str, Any]) -> DetectionResult:
    events = payload["event_ledger"]
    mutations = [
        event
        for event in events
        if event["persistent_before_hash"]
        and event["persistent_after_hash"]
        and event["persistent_before_hash"] != event["persistent_after_hash"]
    ]
    reachable = [event for event in mutations if event["reachable_from_accepted_output"] is True]
    extra_streams = {
        event["stream_id"] for event in events if event["event_kind"] == "ExtraNonacceptingResidual"
    }
    unrestored = [event for event in mutations if event["stream_id"] in extra_streams]
    if reachable:
        classification = "FAIL_REJECTED_CANDIDATE_REACHABILITY"
        plane = "OWNER_EVENT_VERSION_SOURCE"
    elif unrestored:
        classification = "FAIL_PERSISTENT_STATE_RESTORATION"
        plane = "OWNER_EVENT_VERSION_SOURCE"
    else:
        classification = "PASS_TLA_NULL_ENVELOPE"
        plane = "NONE"
    detected = bool(reachable or unrestored)
    return DetectionResult(
        "M6_TLA",
        True,
        detected,
        classification,
        plane,
        {
            "persistent_mutation_count": len(mutations),
            "reachable_mutation_count": len(reachable),
            "extra_callback_unrestored_count": len(unrestored),
        },
    )


def detect_projection(projection: MethodProjection) -> DetectionResult:
    if not projection.applicable:
        return DetectionResult(
            projection.method_id,
            False,
            None,
            NOT_APPLICABLE[projection.method_id],
            "NONE",
            {},
        )
    return {
        "M1_FINAL": _detect_m1,
        "M4_OPERATOR": _detect_m4,
        "M5_META": _detect_m5,
        "M6_TLA": _detect_m6,
    }[projection.method_id](projection.payload)

