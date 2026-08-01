"""L5-D2 case layer over the immutable independent L5 implementation."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

from .l5_cases import (
    EVENT_COLUMNS,
    METRIC_COLUMNS,
    PROFILE_COLUMNS,
    _blank,
    _event_candidate,
    _profile_rows,
    execute_case as execute_d1_case,
)
from .l5_oracle import independent_oracle
from .l5_solver import compare_reference, run_checkpoints, snapshot
from .l5_state import IndependentModel, binary_fingerprint


DESIGN_VERSION = "L5-D2.0"
HOST_VERSION = "L5-HOST-D2.0"

D2_TO_D1 = {
    "L5-D2-REF-01": "L5-IV-REF-01",
    "L5-D2-MB-01": "L5-IV-MB-01",
    "L5-D2-FR-01": "L5-IV-FR-01",
    "L5-D2-OP-01": "L5-IV-OP-01",
    "L5-D2-RT-01": "L5-IV-RT-01",
    "L5-D2-RT-02": "L5-IV-RT-02",
    "L5-D2-XP-01": "L5-IV-XP-01",
}


def load_design(root: Path) -> tuple[dict[str, Any], dict[str, dict[str, str]]]:
    base = root / "benchmarks" / "L5_independent_validation"
    freeze = json.loads((base / "L5_D2_execution_freeze.json").read_text(encoding="utf-8"))
    with (base / "L5_D2_case_matrix.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    matrix = {row["case_id"]: row for row in rows}
    if freeze["design_version"] != DESIGN_VERSION:
        raise RuntimeError("L5-D2 design version mismatch")
    if freeze["design_status"] != "FROZEN_NOT_IMPLEMENTED":
        raise RuntimeError("unexpected L5-D2 design status")
    if set(matrix) != set(freeze["formal_cases"]):
        raise RuntimeError("L5-D2 freeze/matrix mismatch")
    return freeze, matrix


def regression_diagnostics(levels: tuple[int, ...], values: tuple[float, ...]) -> dict[str, Any]:
    if len(levels) != 5 or len(values) != 5:
        raise ValueError("the frozen L5-D2 regression requires five levels")
    if any(level <= 0 for level in levels):
        raise ValueError("positive cell counts are required")
    finite_positive = all(math.isfinite(value) and value > 0.0 for value in values)
    if not finite_positive:
        return {
            "finite_positive": False,
            "strictly_monotone_decreasing": False,
            "order": None,
            "intercept": None,
            "r_squared": None,
            "slope_standard_error": None,
            "log_fit_residuals": [],
            "adjacent_pair_orders": [],
        }

    x = tuple(math.log(1.0 / level) for level in levels)
    y = tuple(math.log(value) for value in values)
    x_mean = math.fsum(x) / len(x)
    y_mean = math.fsum(y) / len(y)
    sxx = math.fsum((item - x_mean) ** 2 for item in x)
    slope = math.fsum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, y)) / sxx
    intercept = y_mean - slope * x_mean
    predicted = tuple(intercept + slope * item for item in x)
    residuals = tuple(yi - estimate for yi, estimate in zip(y, predicted))
    ss_residual = math.fsum(value * value for value in residuals)
    ss_total = math.fsum((item - y_mean) ** 2 for item in y)
    r_squared = 1.0 - ss_residual / ss_total if ss_total > 0.0 else 1.0
    slope_standard_error = math.sqrt((ss_residual / (len(x) - 2)) / sxx)
    adjacent = tuple(
        math.log(values[index] / values[index + 1], 2.0)
        for index in range(len(values) - 1)
    )
    return {
        "finite_positive": True,
        "strictly_monotone_decreasing": all(
            values[index] > values[index + 1] for index in range(len(values) - 1)
        ),
        "order": slope,
        "intercept": intercept,
        "r_squared": r_squared,
        "slope_standard_error": slope_standard_error,
        "log_fit_residuals": list(residuals),
        "adjacent_pair_orders": list(adjacent),
    }


def _base(case_id: str, run_id: str, expected: str) -> dict[str, Any]:
    return {
        "design_version": DESIGN_VERSION,
        "host_version": HOST_VERSION,
        "case_id": case_id,
        "run_id": run_id,
        "expected_classification": expected,
        "processes": 1,
        "threads": 1,
        "abaqus_used": False,
        "production_model_used": False,
        "l4_implementation_imported": False,
        "two_way_flow_mechanics": False,
        "capillary_pressure": False,
    }


def _convergence(
    case_id: str,
    run_id: str,
    freeze: dict[str, Any],
    expected: str,
) -> dict[str, Any]:
    model = IndependentModel()
    target = float(freeze["times"]["convergence"])
    cfl = float(freeze["solver"]["convergence_CFL"])
    levels = tuple(int(value) for value in freeze["solver"]["convergence_N"])
    records = []
    profiles: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []

    for level_index, cell_count in enumerate(levels, 1):
        states, candidates = run_checkpoints(model, cell_count, cfl, (target,))
        state = states[target]
        view = snapshot(model, state)
        oracle = independent_oracle(cell_count, target)
        comparison = compare_reference(model, view, oracle)
        records.append((cell_count, state, comparison))
        profiles.extend(_profile_rows(case_id, run_id, f"mesh_{cell_count}", model, state))
        events.append(
            _event_candidate(
                case_id,
                run_id,
                level_index,
                model,
                candidates[-1],
                "five_level_convergence_endpoint",
            )
        )

    metric_values = {
        "saturation_l1": tuple(record[2].saturation_l1 for record in records),
        "pressure_l2_relative": tuple(record[2].pressure_l2_relative for record in records),
        "front_absolute": tuple(record[2].front_absolute for record in records),
        "displacement_absolute": tuple(record[2].displacement_absolute for record in records),
    }
    diagnostics = {
        metric: regression_diagnostics(levels, values)
        for metric, values in metric_values.items()
    }
    order_minimum = float(freeze["convergence_estimator"]["minimum_order"])
    passed = all(
        item["finite_positive"]
        and item["strictly_monotone_decreasing"]
        and item["order"] >= order_minimum
        for item in diagnostics.values()
    )
    all_values_finite = all(
        item["finite_positive"]
        and all(math.isfinite(value) for value in item["log_fit_residuals"])
        for item in diagnostics.values()
    ) and all(bool(row["finite"]) for row in events)
    passed = passed and all_values_finite

    metrics: list[dict[str, Any]] = []
    for level_index, (cell_count, state, value) in enumerate(records, 1):
        final_level = level_index == len(records)
        metrics.append(
            _blank(
                METRIC_COLUMNS,
                case_id=case_id,
                run_id=run_id,
                row_type="five_level_convergence",
                level=level_index,
                profile_id=f"mesh_{cell_count}",
                time=target,
                cell_count=cell_count,
                cfl=cfl,
                dt=cfl / (2 * cell_count),
                saturation_l1=value.saturation_l1,
                saturation_l2=value.saturation_l2,
                pressure_l2_relative=value.pressure_l2_relative,
                pressure_linf=value.pressure_linf,
                displacement_absolute=value.displacement_absolute,
                front_location=snapshot(model, state).front_location,
                front_absolute=value.front_absolute,
                order_saturation=diagnostics["saturation_l1"]["order"] if final_level else "NA",
                order_pressure=diagnostics["pressure_l2_relative"]["order"] if final_level else "NA",
                order_front=diagnostics["front_absolute"]["order"] if final_level else "NA",
                order_displacement=diagnostics["displacement_absolute"]["order"] if final_level else "NA",
                note="five_level_log_error_log_h_regression",
            )
        )

    result = _base(case_id, run_id, expected)
    result.update(
        {
            "observed_classification": expected if passed else "FAIL_FIVE_LEVEL_CONVERGENCE_GATE",
            "pass_flag": bool(passed),
            "all_values_finite": bool(all_values_finite),
            "convergence_levels": list(levels),
            "convergence_target_time": target,
            "convergence_order_minimum": order_minimum,
            "strict_monotonic_required": True,
            "adjacent_pair_orders_hard_gate": False,
            "fit_diagnostics_hard_gate": False,
            "minimum_observed_regression_order": (
                min(item["order"] for item in diagnostics.values())
                if all(item["order"] is not None for item in diagnostics.values())
                else None
            ),
            "regression_diagnostics": diagnostics,
            "metric_rows": len(metrics),
            "profile_rows": len(profiles),
            "event_rows": len(events),
        }
    )
    result["output_contract_hash"] = binary_fingerprint((metrics, profiles, events))
    return {
        "case_result": result,
        "metric_comparison": metrics,
        "accepted_profile": profiles,
        "lifecycle_event_log": events,
    }


def _remap_d1_payload(
    payload: dict[str, Any],
    d2_case_id: str,
    expected: str,
) -> dict[str, Any]:
    result = payload["case_result"]
    result["design_version"] = DESIGN_VERSION
    result["host_version"] = HOST_VERSION
    result["case_id"] = d2_case_id
    result["expected_classification"] = expected
    if result["pass_flag"]:
        result["observed_classification"] = expected
    result["immutable_d1_dependency"] = True
    for collection_name in ("metric_comparison", "accepted_profile", "lifecycle_event_log"):
        for row in payload[collection_name]:
            row["case_id"] = d2_case_id
    result["output_contract_hash"] = binary_fingerprint(
        (
            payload["metric_comparison"],
            payload["accepted_profile"],
            payload["lifecycle_event_log"],
        )
    )
    return payload


def execute_case(root: Path, case_id: str, run_id: str) -> dict[str, Any]:
    freeze, matrix = load_design(root)
    if case_id not in matrix:
        raise KeyError(case_id)
    expected = matrix[case_id]["expected_classification"]
    if case_id == "L5-D2-CV-01":
        return _convergence(case_id, run_id, freeze, expected)
    if case_id not in D2_TO_D1:
        raise AssertionError(case_id)
    payload = execute_d1_case(root, D2_TO_D1[case_id], run_id)
    return _remap_d1_payload(payload, case_id, expected)
