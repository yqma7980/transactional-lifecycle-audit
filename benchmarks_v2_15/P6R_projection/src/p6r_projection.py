from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from p6r_contracts import METHOD_IDS, NOT_APPLICABLE, assert_no_forbidden_keys, canonical_hash


@dataclass(frozen=True)
class MethodProjection:
    method_id: str
    schema_version: str
    applicable: bool
    payload: Mapping[str, Any]
    payload_sha256: str


def _projection(method_id: str, payload: dict[str, Any], applicable: bool = True) -> MethodProjection:
    assert_no_forbidden_keys(payload)
    frozen = MappingProxyType(payload)
    return MethodProjection(
        method_id=method_id,
        schema_version="P6R-METHOD-PROJECTION-1.0",
        applicable=applicable,
        payload=frozen,
        payload_sha256=canonical_hash(payload),
    )


def _float_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def _bool_value(value: Any) -> bool | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes"}


def project_m1(bundle: Any) -> MethodProjection:
    result = bundle.case_result
    metrics = {key: float(value) for key, value in result.get("metric_distances", {}).items()}
    accepted = tuple(
        {
            "accepted_index": row.get("accepted_index", ""),
            "accepted_load_factor": _float_or_none(row.get("accepted_load_factor")),
            "accepted_version": row.get("accepted_version", ""),
            "top_reaction": _float_or_none(row.get("top_reaction")),
            "bottom_reaction": _float_or_none(row.get("bottom_reaction")),
            "residual_norm": _float_or_none(row.get("residual_norm")),
        }
        for row in bundle.accepted_output
    )
    return _projection(
        "M1_FINAL",
        {
            "all_values_finite": bool(result.get("all_values_finite")),
            "conventional_quiet": bool(result.get("conventional_quiet")),
            "endpoint_quiet": bool(result.get("endpoint_quiet", result.get("conventional_quiet"))),
            "accepted_output_length_equal": bool(result.get("accepted_output_length_equal", 1)),
            "metric_distances": metrics,
            "accepted_state_rows": accepted,
        },
    )


def project_m4(bundle: Any) -> MethodProjection:
    packets = set()
    for row in bundle.event_ledger:
        residual = row.get("residual_version", "")
        tangent = row.get("tangent_version", "")
        relation = row.get("operator_version_relation", "")
        if residual and tangent and relation:
            packets.add((residual, tangent, relation))
    structural = bundle.case_result.get("structural_packet", {})
    version = structural.get("S_VERSION", {}) if isinstance(structural, Mapping) else {}
    if version:
        packets.add(
            (
                str(version.get("residual_version", "")),
                str(version.get("tangent_version", "")),
                str(version.get("relation", "")),
            )
        )
    return _projection(
        "M4_OPERATOR",
        {
            "operator_packets": tuple(
                {
                    "residual_version": residual,
                    "tangent_version": tangent,
                    "compatibility_relation": relation,
                }
                for residual, tangent, relation in sorted(packets)
            )
        },
    )


def project_m5(bundle: Any) -> MethodProjection:
    result = bundle.case_result
    metrics = {key: float(value) for key, value in result.get("metric_distances", {}).items()}
    return _projection(
        "M5_META",
        {
            "equal_input_declared": bool(result.get("structural_identities_exact", 1)),
            "accepted_output_length_equal": bool(result.get("accepted_output_length_equal", 1)),
            "operator_replay_metric_distances": metrics,
            "all_values_finite": bool(result.get("all_values_finite")),
        },
    )


def _stream_aliases(rows: tuple[Mapping[str, str], ...]) -> dict[str, str]:
    names = sorted({row.get("history_id", "") for row in rows if row.get("history_id", "")})
    return {name: f"S{index}" for index, name in enumerate(names)}


def project_m6(bundle: Any) -> MethodProjection:
    aliases = _stream_aliases(bundle.event_ledger)
    allowed = (
        "event_kind",
        "event_ordinal",
        "candidate_id",
        "candidate_state_hash",
        "committed_state_hash",
        "committed_unchanged",
        "old_committed_state_hash",
        "operator_version_relation",
        "persistent_before_hash",
        "persistent_after_hash",
        "persistent_projection_hash",
        "physical_delta",
        "primary_vector_hash",
        "reachable_from_accepted_output",
        "residual_version",
        "tangent_version",
        "source_load",
        "target_load",
        "field_binding",
    )
    events = []
    for row in bundle.event_ledger:
        event = {key: row.get(key, "") for key in allowed}
        event["stream_id"] = aliases.get(row.get("history_id", ""), "")
        event["committed_unchanged"] = _bool_value(event["committed_unchanged"])
        event["reachable_from_accepted_output"] = _bool_value(
            event["reachable_from_accepted_output"]
        )
        event["physical_delta"] = _float_or_none(event["physical_delta"])
        events.append(event)
    return _projection(
        "M6_TLA",
        {
            "event_ledger": tuple(events),
            "all_values_finite": bool(bundle.case_result.get("all_values_finite")),
        },
    )


def build_method_projection(method_id: str, bundle: Any) -> MethodProjection:
    if method_id not in METHOD_IDS:
        raise ValueError(f"unauthorized method: {method_id}")
    if method_id in NOT_APPLICABLE:
        return _projection(
            method_id,
            {"not_applicable_reason": NOT_APPLICABLE[method_id]},
            applicable=False,
        )
    return {
        "M1_FINAL": project_m1,
        "M4_OPERATOR": project_m4,
        "M5_META": project_m5,
        "M6_TLA": project_m6,
    }[method_id](bundle)

