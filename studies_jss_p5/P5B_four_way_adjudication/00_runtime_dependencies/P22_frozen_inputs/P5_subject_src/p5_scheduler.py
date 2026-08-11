from __future__ import annotations

import csv
import json
import math
from pathlib import Path
import sys
from typing import Any, Iterable

import numpy as np

from p5_backend_contracts import FREEZE_ROOT, SCALED_CASES, load_strength_grid, sha256, write_json_new


ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT_SRC = ROOT.parent / "P5_IMPLEMENTATION_PREFLIGHT_20260731" / "src"
if str(PREFLIGHT_SRC) not in sys.path:
    sys.path.insert(0, str(PREFLIGHT_SRC))
from p5_null_envelope import load_metric_scales, scaled_distance, thresholds
from p5_selector import SweepRow, select_strength, verify_fresh_repetitions


METRIC_IDS = ("M_R", "M_J", "M_X", "M_GP", "M_ALPHA", "M_REACTION", "M_OUTPUT_W", "M_OUTPUT_R")


def _case_directory(results_root: Path, case_id: str, run_id: str) -> Path:
    path = results_root / case_id / run_id
    if not path.is_dir():
        raise RuntimeError(f"missing P5 case directory: {path}")
    return path


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"expected object in {path}")
    return payload


def _read_metric_packet(case_directory: Path) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    with np.load(case_directory / "metric_packets.npz", allow_pickle=False) as archive:
        left = {metric_id: np.asarray(archive[f"left_{metric_id}"], dtype=np.float64) for metric_id in METRIC_IDS}
        right = {metric_id: np.asarray(archive[f"right_{metric_id}"], dtype=np.float64) for metric_id in METRIC_IDS}
    return left, right


def _metric_distance(left: dict[str, np.ndarray], right: dict[str, np.ndarray]) -> dict[str, float]:
    scales = load_metric_scales(FREEZE_ROOT / "P5_field_and_metric_scale_registry.csv")
    return {
        metric_id: scaled_distance(left[metric_id].tolist(), right[metric_id].tolist(), scales[metric_id].scale)
        for metric_id in METRIC_IDS
    }


def _write_csv_new(path: Path, fieldnames: list[str], rows: Iterable[dict[str, Any]]) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def calibrate_null_envelope(results_root: Path, final_root: Path) -> dict[str, Any]:
    exact_packets = []
    arithmetic_packets = []
    for number in range(1, 7):
        run_id = f"run_{number}"
        exact_dir = _case_directory(results_root, "P5-NULL-EXACT-CAL-01", run_id)
        exact_result = _read_json(exact_dir / "case_result.json")
        if not exact_result.get("pass_flag") or any(value != 0.0 for value in exact_result["metric_distances"].values()):
            raise RuntimeError("BLOCKED_EXACT_NULL_CONTROL_NONZERO")
        exact_packets.append(_read_metric_packet(exact_dir)[0])

        arithmetic_dir = _case_directory(results_root, "P5-NULL-ARITH-CAL-01", run_id)
        arithmetic_result = _read_json(arithmetic_dir / "case_result.json")
        if not arithmetic_result.get("pass_flag"):
            raise RuntimeError("BLOCKED_NULL_CALIBRATION")
        arithmetic_packets.append(_read_metric_packet(arithmetic_dir))

    rows: list[dict[str, Any]] = []
    envelopes = {metric_id: 0.0 for metric_id in METRIC_IDS}
    for run_index, (left, right) in enumerate(arithmetic_packets, start=1):
        distances = _metric_distance(left, right)
        for metric_id, value in distances.items():
            envelopes[metric_id] = max(envelopes[metric_id], value)
            rows.append({"comparison": "within_A_B", "left_run": run_index, "right_run": run_index, "metric_id": metric_id, "distance": value})

    for label, packets in (("fresh_A_A", [item[0] for item in arithmetic_packets]), ("fresh_B_B", [item[1] for item in arithmetic_packets])):
        for left_index in range(len(packets)):
            for right_index in range(left_index + 1, len(packets)):
                distances = _metric_distance(packets[left_index], packets[right_index])
                for metric_id, value in distances.items():
                    envelopes[metric_id] = max(envelopes[metric_id], value)
                    rows.append({
                        "comparison": label,
                        "left_run": left_index + 1,
                        "right_run": right_index + 1,
                        "metric_id": metric_id,
                        "distance": value,
                    })

    for left_index in range(len(exact_packets)):
        for right_index in range(left_index + 1, len(exact_packets)):
            if any(value != 0.0 for value in _metric_distance(exact_packets[left_index], exact_packets[right_index]).values()):
                raise RuntimeError("BLOCKED_EXACT_NULL_CONTROL_NONZERO")

    frozen_thresholds = thresholds(envelopes)
    status = "PASS_NULL_ENVELOPE_CALIBRATION"
    if any(not math.isfinite(value) or value > 1.0e-11 for value in envelopes.values()):
        status = "NOT_SUPPORTED_NULL_ENVELOPE_TOO_WIDE"
    if any(not math.isfinite(value) or value > 1.0e-10 for value in frozen_thresholds.values()):
        status = "NOT_SUPPORTED_NULL_ENVELOPE_TOO_WIDE"
    payload = {
        "status": status,
        "exact_process_count": 6,
        "arithmetic_process_count": 6,
        "calibration_envelope": envelopes,
        "thresholds": frozen_thresholds,
        "absolute_floor_multiplier": 1024,
        "margin_factor": 10.0,
        "machine_epsilon": float(np.finfo(np.float64).eps),
    }
    _write_csv_new(final_root / "null_pairwise_metrics.csv", ["comparison", "left_run", "right_run", "metric_id", "distance"], rows)
    write_json_new(final_root / "null_envelope.json", payload)
    if status != "PASS_NULL_ENVELOPE_CALIBRATION":
        raise RuntimeError(status)
    return payload


def confirm_null_envelope(results_root: Path, thresholds_payload: dict[str, Any]) -> dict[str, Any]:
    distances: list[dict[str, Any]] = []
    for number in (1, 2):
        run_id = f"run_{number}"
        case_dir = _case_directory(results_root, "P5-NULL-ARITH-CONF-01", run_id)
        result = _read_json(case_dir / "case_result.json")
        if not result.get("pass_flag"):
            raise RuntimeError("NOT_SUPPORTED_NULL_ENVELOPE_UNSTABLE")
        distances.append({"run_id": run_id, "metric_distances": result["metric_distances"]})
    return {"status": "PASS_NULL_ENVELOPE_CONFIRMATION", "runs": distances, "thresholds": thresholds_payload["thresholds"]}


def select_scaled_strengths(results_root: Path, final_root: Path) -> dict[str, Any]:
    grid = load_strength_grid()
    sweep_rows: list[dict[str, Any]] = []
    selections: dict[str, Any] = {}
    for case_id, family_id in SCALED_CASES.items():
        rows: list[SweepRow] = []
        for number in range(1, 16):
            result = _read_json(_case_directory(results_root, case_id, f"run_{number}") / "case_result.json")
            index = int(result["strength_index"])
            if index != number - 1 or float(result["eta"]) != float(grid[index]["eta"]):
                raise RuntimeError("P5 strength/run mapping drift")
            row = SweepRow(
                index=index,
                eta=float(result["eta"]),
                conventional_quiet=bool(result["conventional_quiet"]),
                lifecycle_violation_present=bool(result["lifecycle_violation_present"]),
                all_values_finite=bool(result["all_values_finite"]),
                z_residual=float(result["z_residual"]),
                z_tangent=float(result["z_tangent"]),
            )
            rows.append(row)
            sweep_rows.append({
                "case_id": case_id,
                "family_id": family_id,
                "run_id": f"run_{number}",
                "strength_index": index,
                "eta": row.eta,
                "conventional_quiet": row.conventional_quiet,
                "lifecycle_violation_present": row.lifecycle_violation_present,
                "all_values_finite": row.all_values_finite,
                "z_residual": row.z_residual,
                "z_tangent": row.z_tangent,
                "z_family": row.z_family,
            })
        selected = select_strength(rows)
        selections[family_id] = {
            "case_id": case_id,
            "status": selected.status,
            "selected_index": selected.selected_index,
            "selected_eta": selected.selected_eta,
            "next_index": selected.next_index,
            "next_eta": selected.next_eta,
        }
    _write_csv_new(
        final_root / "strength_sweep.csv",
        [
            "case_id", "family_id", "run_id", "strength_index", "eta", "conventional_quiet",
            "lifecycle_violation_present", "all_values_finite", "z_residual", "z_tangent", "z_family",
        ],
        sweep_rows,
    )
    payload = {"status": "SELECTION_COMPLETE", "families": selections}
    write_json_new(final_root / "selected_strengths.json", payload)
    return payload


def verify_scaled_repetitions(results_root: Path, selections: dict[str, Any], final_root: Path) -> dict[str, Any]:
    comparisons: list[dict[str, Any]] = []
    overall = "PASS_FRESH_PROCESS_VERIFICATION"
    for case_id, family_id in SCALED_CASES.items():
        selected = selections["families"][family_id]
        if selected["status"] != "SELECTED_PENDING_FRESH_VERIFICATION":
            comparisons.append({"family_id": family_id, "status": selected["status"]})
            overall = selected["status"]
            continue
        records = {
            int(selected["selected_index"]): [
                _read_json(_case_directory(results_root, case_id, run_id) / "case_result.json") for run_id in ("run_16", "run_17")
            ],
            int(selected["next_index"]): [
                _read_json(_case_directory(results_root, case_id, run_id) / "case_result.json") for run_id in ("run_18", "run_19")
            ],
        }
        selection_proxy = type("SelectionProxy", (), {
            "selected_index": int(selected["selected_index"]),
            "next_index": int(selected["next_index"]),
        })()
        status = verify_fresh_repetitions(selection_proxy, records)
        comparisons.append({
            "family_id": family_id,
            "status": status,
            "selected_pair_equal": _normalize(records[int(selected["selected_index"])][0]) == _normalize(records[int(selected["selected_index"])][1]),
            "next_pair_equal": _normalize(records[int(selected["next_index"])][0]) == _normalize(records[int(selected["next_index"])][1]),
        })
        if status != "PASS_FRESH_PROCESS_VERIFICATION":
            overall = status
    payload = {"status": overall, "families": comparisons}
    write_json_new(final_root / "duplicate_comparison.json", payload)
    return payload


def _normalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _normalize(item) for key, item in value.items() if key not in {"run_id", "wall_clock_timestamp", "absolute_path"}}
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    return value


def build_execution_manifest(results_root: Path, final_root: Path) -> dict[str, Any]:
    files = sorted(path for path in results_root.rglob("*") if path.is_file() and path != final_root / "execution_manifest.json")
    payload = {
        "formal_case_count": 7,
        "formal_process_count": 90,
        "files": [
            {"path": path.relative_to(results_root).as_posix(), "bytes": path.stat().st_size, "sha256": sha256(path)}
            for path in files
        ],
        "manifest_self_hash_embedded": False,
    }
    write_json_new(final_root / "execution_manifest.json", payload)
    return payload
