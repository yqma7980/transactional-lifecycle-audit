from __future__ import annotations

import json
import pathlib
from typing import Any

import numpy as np

from p4d_canonical import canonical_hash


def read_c_ledger(path: pathlib.Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _vector_hash(hex_values: list[str] | None) -> str | None:
    if hex_values is None:
        return None
    return canonical_hash(np.array([float.fromhex(value) for value in hex_values], dtype=np.float64))


def classify_native_line_search(c_events: list[dict[str, Any]], python_events: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = [event for event in c_events if event.get("callback_kind") == "LINE_SEARCH_CANDIDATE"]
    selected = [event for event in c_events if event.get("callback_kind") == "LINE_SEARCH_SELECTED"]
    python_hashes = {
        event.get("primary_vector_hash")
        for event in python_events
        if event.get("event_kind") == "TrialEvaluate"
    }
    unselected: list[dict[str, Any]] = []
    correlated = 0
    for candidate in candidates:
        work_hash = _vector_hash(candidate.get("W_hex_values"))
        if work_hash in python_hashes:
            correlated += 1
        matching_selected = [
            event for event in selected
            if event.get("nonlinear_iteration") == candidate.get("nonlinear_iteration")
        ]
        if matching_selected and all(event.get("W_hex_values") != candidate.get("W_hex_values") for event in matching_selected):
            unselected.append(candidate)
    return {
        "candidate_event_count": len(candidates),
        "selected_event_count": len(selected),
        "structured_unselected_candidate_count": len(unselected),
        "structured_unselected_candidate_present": bool(unselected),
        "candidate_to_python_packet_correlation_count": correlated,
        "candidate_to_python_packet_correlation_present": correlated > 0,
        "postcheck_flags_read_only": all(
            event.get("postcheck_change_flags") is False
            for event in c_events
            if event.get("callback_kind") == "ATTACH"
        ),
    }
