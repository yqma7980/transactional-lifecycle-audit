from __future__ import annotations

import csv
import json
from pathlib import Path
import sys
from typing import Any, Iterable

import numpy as np

from p5_arithmetic import ElementContributionPacket, build_element_contributions, reduce_operator
from p5_backend_contracts import (
    DESIGN_VERSION,
    FREEZE_ROOT,
    HOST_VERSION,
    IMPLEMENTATION_VERSION,
    NULL_CASE_LIMITS,
    SCALED_CASES,
    sha256,
    write_json_new,
)
from p5_fe_history import P5HistoryRun, run_p5_history, semantic_history_summary


ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT_SRC = ROOT.parent / "P5_IMPLEMENTATION_PREFLIGHT_20260731" / "src"
if str(PREFLIGHT_SRC) not in sys.path:
    sys.path.insert(0, str(PREFLIGHT_SRC))
from p5_null_envelope import load_metric_scales, scaled_distance


NULL_PATHS = {
    "P5-NULL-EXACT-CAL-01": ("ARITH_A_REFERENCE", "ARITH_A_REFERENCE"),
    "P5-NULL-ARITH-CAL-01": ("ARITH_A_REFERENCE", "ARITH_B_CALIBRATION"),
    "P5-NULL-ARITH-CONF-01": ("ARITH_A_REFERENCE", "ARITH_C_CONFIRMATION"),
}

EXPECTED_FAULT_VERDICTS = {
    "F01": "FAIL_PERSISTENT_STATE_RESTORATION",
    "F02": "FAIL_DECLARED_PERSISTENT_FIELD_RESTORATION",
    "F05": "FAIL_REJECTED_SOURCE_REACHABILITY",
    "F07": "FAIL_PROCESS_GLOBAL_STATE_RESTORATION",
}

CONVENTIONAL_QUIET_METRICS = (
    "M_X",
    "M_GP",
    "M_ALPHA",
    "M_REACTION",
    "M_OUTPUT_W",
    "M_OUTPUT_R",
)


def _jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, float)):
        return float(value)
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _metric_packet(history: P5HistoryRun, path_id: str) -> tuple[dict[str, np.ndarray], ElementContributionPacket]:
    contributions = build_element_contributions(history.context, history.replay_packet)
    operator = reduce_operator(contributions, path_id)
    if not history.output_rows:
        raise RuntimeError("P5 history has no accepted output")
    final = history.output_rows[-1]
    packet = {
        "M_R": operator.residual,
        "M_J": operator.tangent,
        "M_X": np.asarray(history.final_state.primary, dtype=np.float64),
        "M_GP": np.asarray(history.final_state.gamma_p, dtype=np.float64),
        "M_ALPHA": np.asarray(history.final_state.alpha, dtype=np.float64),
        "M_REACTION": np.asarray([final["top_reaction"], final["bottom_reaction"]], dtype=np.float64),
        "M_OUTPUT_W": np.concatenate([np.asarray(row["primary"], dtype=np.float64) for row in history.output_rows]),
        "M_OUTPUT_R": np.asarray(
            [[row["top_reaction"], row["bottom_reaction"]] for row in history.output_rows],
            dtype=np.float64,
        ),
    }
    return packet, contributions


def _structural_packet(history: P5HistoryRun) -> dict[str, Any]:
    packet = history.replay_packet
    return {
        "S_SCHEMA": "CMAME-P5-METRIC-PACKET-1.0",
        "S_VERSION": {
            "accepted_version": history.final_state.accepted_version,
            "residual_version": packet.residual_version,
            "tangent_version": packet.tangent_version,
            "relation": packet.relation,
        },
        "S_SOURCE": {
            "replay_candidate_id": packet.candidate_id,
            "accepted_candidate_ids": [row["candidate_id"] for row in history.output_rows],
            "accepted_source_events": [row["source_event"] for row in history.output_rows],
        },
        "S_REACH": {
            "rejected_source_candidate_id": history.persistent.rejected_source_candidate_id,
            "lifecycle_violation_present": history.lifecycle_violation_present,
        },
        "S_ORDER": [row["event_kind"] for row in history.events],
    }


def _distances(left: dict[str, np.ndarray], right: dict[str, np.ndarray]) -> dict[str, float]:
    scales = load_metric_scales(FREEZE_ROOT / "P5_field_and_metric_scale_registry.csv")
    return {
        metric_id: scaled_distance(left[metric_id].tolist(), right[metric_id].tolist(), scale.scale)
        for metric_id, scale in scales.items()
    }


def _all_finite(packet: dict[str, np.ndarray]) -> bool:
    return all(np.isfinite(values).all() and np.max(np.abs(values), initial=0.0) < 1.0e100 for values in packet.values())


def _write_event_ledger(path: Path, histories: list[P5HistoryRun]) -> None:
    records = []
    for history in histories:
        for row in history.events:
            records.append({"history_role": history.role, "history_id": history.history_id, **row})
    fields = sorted({key for row in records for key in row})
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in records:
            writer.writerow({
                key: json.dumps(_jsonable(value), sort_keys=True) if isinstance(value, (dict, list, tuple)) else value
                for key, value in row.items()
            })


def _write_output_summary(path: Path, histories: list[P5HistoryRun]) -> None:
    fields = [
        "history_role",
        "history_id",
        "accepted_index",
        "accepted_load_factor",
        "accepted_version",
        "candidate_id",
        "source_event",
        "top_reaction",
        "bottom_reaction",
        "residual_norm",
        "relation",
    ]
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for history in histories:
            for row in history.output_rows:
                payload = {key: row[key] for key in fields if key not in {"history_role", "history_id"}}
                writer.writerow({"history_role": history.role, "history_id": history.history_id, **payload})


def flatten_term_lists(term_lists: Iterable[Iterable[float]]) -> tuple[np.ndarray, np.ndarray]:
    values: list[float] = []
    offsets = [0]
    for terms in term_lists:
        values.extend(float(item) for item in terms)
        offsets.append(len(values))
    return np.asarray(values, dtype=np.float64), np.asarray(offsets, dtype=np.int64)


def _flatten_contributions(packet: ElementContributionPacket) -> dict[str, np.ndarray]:
    residual_values, residual_offsets = flatten_term_lists(packet.residual_terms)
    tangent_rows = [terms for row in packet.tangent_terms for terms in row]
    tangent_values, tangent_offsets = flatten_term_lists(tangent_rows)
    return {
        "residual_values": residual_values,
        "residual_offsets": residual_offsets,
        "tangent_values": tangent_values,
        "tangent_offsets": tangent_offsets,
        "operator_shape": np.asarray([packet.dof_count, packet.dof_count], dtype=np.int64),
        "cell_count": np.asarray([packet.cell_count], dtype=np.int64),
    }


def execute_case(
    *,
    case_id: str,
    run_id: str,
    result_directory: Path,
    environment: dict[str, Any],
    strength_index: int | None,
    eta: float | None,
    thresholds: dict[str, float] | None,
) -> dict[str, Any]:
    if result_directory.exists() and any(result_directory.iterdir()):
        raise RuntimeError("P5 result directory must be empty")
    if "semantic_environment_hash" not in environment:
        raise RuntimeError("runner did not declare semantic_environment_hash")

    histories: list[P5HistoryRun]
    if case_id in NULL_CASE_LIMITS:
        history = run_p5_history(None, False, 0.0, run_id)
        left_path, right_path = NULL_PATHS[case_id]
        histories = [history]
        left, left_contributions = _metric_packet(history, left_path)
        right, right_contributions = _metric_packet(history, right_path)
        structural_packet = _structural_packet(history)
        structural_equal = structural_packet == _structural_packet(history)
        metric_distances = _distances(left, right)
        all_values_finite = _all_finite(left) and _all_finite(right)
        conventional_quiet = history.conventional_quiet
        if case_id == "P5-NULL-EXACT-CAL-01":
            pass_flag = bool(conventional_quiet and structural_equal and all(value == 0.0 for value in metric_distances.values()))
            classification = "CALIBRATION_EXACT_ZERO" if pass_flag else "BLOCKED_EXACT_NULL_CONTROL_NONZERO"
        elif case_id == "P5-NULL-ARITH-CAL-01":
            pass_flag = bool(conventional_quiet and structural_equal and all_values_finite)
            classification = "CALIBRATION_NUMERIC_ENVELOPE_OBSERVATION" if pass_flag else "BLOCKED_NULL_CALIBRATION"
        else:
            if thresholds is None:
                raise RuntimeError("null confirmation requires frozen calibration thresholds")
            pass_flag = bool(
                conventional_quiet
                and structural_equal
                and all_values_finite
                and all(metric_distances[key] <= thresholds[key] for key in metric_distances)
            )
            classification = "CONFIRM_NULL_ENVELOPE" if pass_flag else "NOT_SUPPORTED_NULL_ENVELOPE_UNSTABLE"
        result = {
            "case_role": "null",
            "left_arithmetic_path": left_path,
            "right_arithmetic_path": right_path,
            "structural_packet": structural_packet,
            "structural_identities_exact": structural_equal,
            "metric_distances": metric_distances,
            "all_values_finite": all_values_finite,
            "conventional_quiet": conventional_quiet,
            "observed_classification": classification,
            "pass_flag": pass_flag,
            "history": semantic_history_summary(history),
        }
    elif case_id in SCALED_CASES:
        if strength_index is None or eta is None or thresholds is None:
            raise RuntimeError("scaled P5 case requires strength index, eta and frozen thresholds")
        family_id = SCALED_CASES[case_id]
        safe = run_p5_history(family_id, False, 0.0, run_id)
        faulty = run_p5_history(family_id, True, eta, run_id)
        histories = [safe, faulty]
        left_path = right_path = "ARITH_A_REFERENCE"
        left, left_contributions = _metric_packet(safe, left_path)
        right, right_contributions = _metric_packet(faulty, right_path)
        metric_distances = _distances(left, right)
        expected_verdict = EXPECTED_FAULT_VERDICTS[family_id]
        observed_verdict = faulty.mutation_record["expected_lifecycle_verdict"] if faulty.mutation_record else "MISSING_MUTATION"
        lifecycle_violation = bool(faulty.lifecycle_violation_present and observed_verdict == expected_verdict)
        endpoint_quiet = all(metric_distances[metric_id] <= 1.0e-10 for metric_id in CONVENTIONAL_QUIET_METRICS)
        conventional_quiet = bool(safe.conventional_quiet and faulty.conventional_quiet and endpoint_quiet)
        all_values_finite = _all_finite(left) and _all_finite(right)
        z_residual = metric_distances["M_R"] / thresholds["M_R"]
        z_tangent = metric_distances["M_J"] / thresholds["M_J"]
        pass_flag = bool(lifecycle_violation and all_values_finite)
        result = {
            "case_role": "scaled_development",
            "family_id": family_id,
            "strength_index": int(strength_index),
            "eta": float(eta),
            "expected_lifecycle_verdict": expected_verdict,
            "observed_lifecycle_verdict": observed_verdict,
            "lifecycle_violation_present": lifecycle_violation,
            "metric_distances": metric_distances,
            "z_residual": float(z_residual),
            "z_tangent": float(z_tangent),
            "z_family": float(max(z_residual, z_tangent)),
            "all_values_finite": all_values_finite,
            "endpoint_quiet": endpoint_quiet,
            "conventional_quiet": conventional_quiet,
            "observed_classification": "SWEEP_OBSERVATION_READY_FOR_SELECTION" if pass_flag else "SCALED_CASE_EXECUTION_INVALID",
            "pass_flag": pass_flag,
            "safe_history": semantic_history_summary(safe),
            "faulty_history": semantic_history_summary(faulty),
        }
    else:
        raise ValueError(f"unknown P5 case {case_id}")

    result.update({
        "design_version": DESIGN_VERSION,
        "implementation_version": IMPLEMENTATION_VERSION,
        "host_version": HOST_VERSION,
        "case_id": case_id,
        "run_id": run_id,
        "environment_hash": environment["semantic_environment_hash"],
        "formal_execution": True,
        "abaqus_used": False,
        "production_model_used": False,
    })
    write_json_new(result_directory / "environment.json", environment)
    _write_event_ledger(result_directory / "event_ledger.csv", histories)
    _write_output_summary(result_directory / "accepted_output.csv", histories)
    np.savez(
        result_directory / "metric_packets.npz",
        **{f"left_{key}": value for key, value in left.items()},
        **{f"right_{key}": value for key, value in right.items()},
    )
    left_flat = _flatten_contributions(left_contributions)
    right_flat = _flatten_contributions(right_contributions)
    np.savez(
        result_directory / "operator_contributions.npz",
        **{f"left_{key}": value for key, value in left_flat.items()},
        **{f"right_{key}": value for key, value in right_flat.items()},
    )
    write_json_new(result_directory / "case_result.json", _jsonable(result))
    files = sorted(path for path in result_directory.iterdir() if path.is_file())
    manifest = {
        "case_id": case_id,
        "run_id": run_id,
        "files": [
            {"path": path.name, "bytes": path.stat().st_size, "sha256": sha256(path)}
            for path in files
        ],
        "manifest_self_hash_embedded": False,
    }
    write_json_new(result_directory / "case_manifest.json", manifest)
    return result
