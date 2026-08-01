"""Frozen L3-D1 case dispatcher."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

from .l3_fv import (
    all_finite,
    cumulative_mass_defect,
    field_metrics,
    normalized,
    run_constant_step,
)
from .l3_lifecycle import (
    SafeTransactionalVariant,
    UnsafePreviousStateCacheVariant,
    compare_retry,
)
from .l3_state import CommittedState, DESIGN_VERSION, HOST_VERSION, PoroModel, settlement


COMPARISON_COLUMNS = (
    "case_id", "run_id", "row_type", "level", "time", "cell_count", "dt",
    "pressure_l2_relative", "pressure_linf_absolute", "settlement_absolute",
    "oracle_tail_envelope", "spatial_or_temporal_order_pressure",
    "spatial_or_temporal_order_settlement", "step_mass_defect_normalized",
    "cumulative_mass_defect_normalized", "pressure_bounds_ok",
    "pressure_depth_monotone", "mean_pressure_nonincreasing",
    "settlement_nondecreasing", "outflow_nondecreasing", "note",
)
EVENT_COLUMNS = (
    "case_id", "run_id", "ordinal", "history_id", "event", "attempt_id",
    "variant", "accepted", "time", "dt", "cell_count",
    "committed_fingerprint", "candidate_fingerprint", "persistent_fingerprint",
    "candidate_reachable", "mean_pressure", "minimum_pressure", "maximum_pressure",
    "settlement", "cumulative_outflow", "boundary_flux", "storage_change",
    "mass_defect", "finite", "note",
)


def load_design(root: Path) -> tuple[dict[str, Any], dict[str, dict[str, str]]]:
    base = root / "benchmarks" / "L3_poroelastic_consolidation"
    freeze = json.loads((base / "L3_D1_execution_freeze.json").read_text(encoding="utf-8"))
    with (base / "L3_D0_case_matrix.csv").open(encoding="utf-8", newline="") as handle:
        matrix = {row["case_id"]: row for row in csv.DictReader(handle)}
    if freeze["design_version"] != DESIGN_VERSION:
        raise RuntimeError("freeze/implementation version mismatch")
    if set(freeze["formal_cases"]) != set(matrix):
        raise RuntimeError("freeze/matrix case mismatch")
    return freeze, matrix


def _blank_comparison(case_id: str, run_id: str, **values: Any) -> dict[str, Any]:
    row = {column: "NA" for column in COMPARISON_COLUMNS}
    row.update({"case_id": case_id, "run_id": run_id})
    row.update(values)
    return row


def _event_from_candidate(
    case_id: str,
    run_id: str,
    ordinal: int,
    cell_count: int,
    model: PoroModel,
    accepted_version: int,
    candidate: Any,
    *,
    event: str = "AcceptIncrement",
    note: str,
) -> dict[str, Any]:
    pressure = candidate.pressure
    accepted_state = CommittedState(
        time=candidate.time,
        pressure=candidate.pressure,
        cumulative_outflow=candidate.cumulative_outflow,
        accepted_version=accepted_version,
    )
    return {
        "case_id": case_id,
        "run_id": run_id,
        "ordinal": ordinal,
        "history_id": "PHYSICAL",
        "event": event,
        "attempt_id": candidate.attempt_id,
        "variant": "safe_transactional",
        "accepted": event == "AcceptIncrement",
        "time": candidate.time,
        "dt": candidate.dt,
        "cell_count": cell_count,
        "committed_fingerprint": accepted_state.fingerprint,
        "candidate_fingerprint": candidate.fingerprint,
        "persistent_fingerprint": "NA",
        "candidate_reachable": False,
        "mean_pressure": sum(pressure) / len(pressure),
        "minimum_pressure": min(pressure),
        "maximum_pressure": max(pressure),
        "settlement": settlement(model, pressure),
        "cumulative_outflow": candidate.cumulative_outflow,
        "boundary_flux": candidate.boundary_flux,
        "storage_change": candidate.declared_storage_change,
        "mass_defect": candidate.declared_mass_defect,
        "finite": True,
        "note": note,
    }


def _orders(errors: list[float]) -> tuple[float, float]:
    if any(value <= 0.0 for value in errors):
        raise RuntimeError("nonpositive error cannot define order")
    return (
        math.log(errors[0] / errors[1], 2.0),
        math.log(errors[1] / errors[2], 2.0),
    )


def _base_result(case_id: str, run_id: str, expected: str) -> dict[str, Any]:
    return {
        "design_version": DESIGN_VERSION,
        "host_version": HOST_VERSION,
        "case_id": case_id,
        "run_id": run_id,
        "expected_classification": expected,
        "abaqus_used": False,
        "production_model_used": False,
        "processes": 1,
        "threads": 1,
    }


def _reference(case_id: str, run_id: str, freeze: dict[str, Any], expected: str) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    model = PoroModel()
    comparisons: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    passed = True
    for ordinal, time in enumerate((0.05, 0.2, 0.5), 1):
        state, candidates = run_constant_step(model, 160, 0.00025, time)
        metrics = field_metrics(model, state)
        passed &= (
            metrics.pressure_l2_relative <= freeze["tolerances"]["reference_pressure_l2_relative"]
            and metrics.pressure_linf_absolute <= freeze["tolerances"]["reference_pressure_linf"]
            and metrics.settlement_absolute <= freeze["tolerances"]["reference_settlement_absolute"]
            and metrics.oracle_tail_envelope <= freeze["oracle"]["tail_envelope"]
        )
        comparisons.append(_blank_comparison(
            case_id, run_id, row_type="reference", level=ordinal, time=time,
            cell_count=160, dt=0.00025,
            pressure_l2_relative=metrics.pressure_l2_relative,
            pressure_linf_absolute=metrics.pressure_linf_absolute,
            settlement_absolute=metrics.settlement_absolute,
            oracle_tail_envelope=metrics.oracle_tail_envelope,
            note="analytical_reference",
        ))
        events.append(_event_from_candidate(case_id, run_id, ordinal, 160, model, state.accepted_version, candidates[-1], note=f"accepted_t={time}"))
    result = _base_result(case_id, run_id, expected)
    result.update({"observed_classification": expected if passed else "FAIL_ANALYTICAL_REFERENCE", "pass_flag": passed, "all_values_finite": True, "comparison_rows": len(comparisons), "event_rows": len(events)})
    return result, comparisons, events


def _convergence(case_id: str, run_id: str, freeze: dict[str, Any], expected: str, spatial: bool) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    model = PoroModel()
    levels = [(20, 0.2 * (1.0 / 20) ** 2), (40, 0.2 * (1.0 / 40) ** 2), (80, 0.2 * (1.0 / 80) ** 2)] if spatial else [(400, 0.04), (400, 0.02), (400, 0.01)]
    pressure_errors: list[float] = []
    settlement_errors: list[float] = []
    comparisons: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    for ordinal, (cells, dt) in enumerate(levels, 1):
        state, candidates = run_constant_step(model, cells, dt, 0.2)
        metrics = field_metrics(model, state)
        pressure_errors.append(metrics.pressure_l2_relative)
        settlement_errors.append(metrics.settlement_absolute)
        comparisons.append(_blank_comparison(case_id, run_id, row_type="spatial" if spatial else "temporal", level=ordinal, time=0.2, cell_count=cells, dt=dt, pressure_l2_relative=metrics.pressure_l2_relative, pressure_linf_absolute=metrics.pressure_linf_absolute, settlement_absolute=metrics.settlement_absolute, oracle_tail_envelope=metrics.oracle_tail_envelope, note="convergence_level"))
        events.append(_event_from_candidate(case_id, run_id, ordinal, cells, model, state.accepted_version, candidates[-1], note="convergence_endpoint"))
    p_orders = _orders(pressure_errors)
    s_orders = _orders(settlement_errors)
    threshold = freeze["tolerances"]["spatial_order_minimum" if spatial else "temporal_order_minimum"]
    decreasing = pressure_errors[0] > pressure_errors[1] > pressure_errors[2] and settlement_errors[0] > settlement_errors[1] > settlement_errors[2]
    passed = decreasing and p_orders[1] >= threshold and s_orders[1] >= threshold
    comparisons[-1]["spatial_or_temporal_order_pressure"] = p_orders[1]
    comparisons[-1]["spatial_or_temporal_order_settlement"] = s_orders[1]
    result = _base_result(case_id, run_id, expected)
    result.update({"observed_classification": expected if passed else "FAIL_CONVERGENCE", "pass_flag": passed, "all_values_finite": True, "pressure_orders": p_orders, "settlement_orders": s_orders, "errors_decrease": decreasing, "comparison_rows": 3, "event_rows": 3})
    return result, comparisons, events


def _mass(case_id: str, run_id: str, freeze: dict[str, Any], expected: str) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    model = PoroModel()
    state, candidates = run_constant_step(model, 64, 0.005, 0.5)
    step_defects = [normalized(c.internal_mass_defect, c.outflow_increment, c.storage_change_from_source) for c in candidates]
    cumulative = normalized(cumulative_mass_defect(model, state), state.cumulative_outflow, model.storage_coefficient * model.H * model.p0)
    maximum = max(step_defects)
    passed = maximum <= freeze["tolerances"]["mass_defect_maximum"] and cumulative <= freeze["tolerances"]["mass_defect_maximum"]
    comparisons = [_blank_comparison(case_id, run_id, row_type="mass", level=1, time=0.5, cell_count=64, dt=0.005, step_mass_defect_normalized=maximum, cumulative_mass_defect_normalized=cumulative, note="discrete_global_balance")]
    events = [_event_from_candidate(case_id, run_id, i, 64, model, i, c, note="mass_balance_step") for i, c in enumerate(candidates, 1)]
    result = _base_result(case_id, run_id, expected)
    result.update({"observed_classification": expected if passed else "FAIL_DISCRETE_MASS_BALANCE", "pass_flag": passed, "all_values_finite": True, "maximum_step_mass_defect_normalized": maximum, "cumulative_mass_defect_normalized": cumulative, "comparison_rows": 1, "event_rows": len(events)})
    return result, comparisons, events


def _stability(case_id: str, run_id: str, freeze: dict[str, Any], expected: str) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    model = PoroModel()
    state, candidates = run_constant_step(model, 80, 0.0025, 0.5)
    slack = freeze["tolerances"]["stability_slack"]
    bounds = all(min(c.pressure) >= -slack and max(c.pressure) <= model.p0 + slack for c in candidates)
    depth = all(all(c.pressure[i] <= c.pressure[i + 1] + slack for i in range(len(c.pressure) - 1)) for c in candidates)
    means = [model.p0] + [sum(c.pressure) / len(c.pressure) for c in candidates]
    settlements = [model.H * (model.q - model.alpha * model.p0) / model.K_d] + [settlement(model, c.pressure) for c in candidates]
    outflows = [0.0] + [c.cumulative_outflow for c in candidates]
    mean_down = all(b <= a + slack for a, b in zip(means, means[1:]))
    settlement_up = all(b + slack >= a for a, b in zip(settlements, settlements[1:]))
    outflow_up = all(b + slack >= a for a, b in zip(outflows, outflows[1:]))
    passed = bounds and depth and mean_down and settlement_up and outflow_up
    comparisons = [_blank_comparison(case_id, run_id, row_type="stability", level=1, time=0.5, cell_count=80, dt=0.0025, pressure_bounds_ok=bounds, pressure_depth_monotone=depth, mean_pressure_nonincreasing=mean_down, settlement_nondecreasing=settlement_up, outflow_nondecreasing=outflow_up, note="all_accepted_steps")]
    events = [_event_from_candidate(case_id, run_id, i, 80, model, i, c, note="stability_step") for i, c in enumerate(candidates, 1)]
    result = _base_result(case_id, run_id, expected)
    result.update({"observed_classification": expected if passed else "FAIL_MONOTONE_STABILITY", "pass_flag": passed, "all_values_finite": True, "pressure_bounds_ok": bounds, "pressure_depth_monotone": depth, "mean_pressure_nonincreasing": mean_down, "settlement_nondecreasing": settlement_up, "outflow_nondecreasing": outflow_up, "comparison_rows": 1, "event_rows": len(events)})
    return result, comparisons, events


def _retry(case_id: str, run_id: str, freeze: dict[str, Any], expected: str, unsafe: bool) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    model = PoroModel()
    comparison = compare_retry(model, 32, UnsafePreviousStateCacheVariant if unsafe else SafeTransactionalVariant)
    if unsafe:
        passed = (
            comparison.declared_context_equal
            and comparison.committed_before_replay_unchanged
            and comparison.rejected_candidate_unreachable
            and not comparison.observed_replay_fingerprint_equal
            and comparison.pressure_l2_drift >= freeze["tolerances"]["unsafe_pressure_l2_drift_floor"]
            and comparison.settlement_drift >= freeze["tolerances"]["unsafe_settlement_drift_floor"]
            and comparison.declared_mass_defect >= freeze["tolerances"]["unsafe_declared_mass_defect_floor"]
            and comparison.all_values_finite
        )
    else:
        passed = (
            comparison.declared_context_equal
            and comparison.committed_before_replay_unchanged
            and comparison.rejected_candidate_unreachable
            and comparison.accepted_pressure_exact
            and comparison.accepted_state_fingerprint_exact
            and comparison.observed_replay_fingerprint_equal
            and comparison.pressure_l2_drift == 0.0
            and comparison.settlement_drift == 0.0
            and comparison.all_values_finite
        )
    comparisons = [_blank_comparison(case_id, run_id, row_type="retry", level=1, time=0.01, cell_count=32, dt=0.01, pressure_l2_relative=comparison.pressure_l2_drift, settlement_absolute=comparison.settlement_drift, cumulative_mass_defect_normalized=comparison.declared_mass_defect, note="unsafe_negative_control" if unsafe else "safe_exact_retry")]
    events = []
    for source in comparison.events:
        row = {column: "NA" for column in EVENT_COLUMNS}
        row.update(source)
        row.update({"case_id": case_id, "run_id": run_id, "cell_count": 32})
        events.append(row)
    result = _base_result(case_id, run_id, expected)
    result.update({"observed_classification": expected if passed else "FAIL_RETRY_GATE", "pass_flag": passed, "all_values_finite": comparison.all_values_finite, "declared_context_equal": comparison.declared_context_equal, "committed_before_replay_unchanged": comparison.committed_before_replay_unchanged, "rejected_candidate_unreachable": comparison.rejected_candidate_unreachable, "accepted_pressure_exact": comparison.accepted_pressure_exact, "accepted_state_fingerprint_exact": comparison.accepted_state_fingerprint_exact, "observed_replay_fingerprint_equal": comparison.observed_replay_fingerprint_equal, "pressure_l2_drift": comparison.pressure_l2_drift, "settlement_drift": comparison.settlement_drift, "declared_mass_defect": comparison.declared_mass_defect, "comparison_rows": 1, "event_rows": len(events)})
    return result, comparisons, events


def _payload_finite(value: Any, limit: float) -> bool:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return True
    if isinstance(value, (int, float)):
        numeric = float(value)
        return math.isfinite(numeric) and abs(numeric) <= limit
    if isinstance(value, dict):
        return all(_payload_finite(item, limit) for item in value.values())
    if isinstance(value, (list, tuple)):
        return all(_payload_finite(item, limit) for item in value)
    return True


def execute_case(root: Path, case_id: str, run_id: str) -> dict[str, Any]:
    freeze, matrix = load_design(root)
    if case_id not in matrix:
        raise KeyError(f"unauthorized case: {case_id}")
    expected = matrix[case_id]["expected_classification"]
    if case_id == "L3-REF-01":
        result, comparisons, events = _reference(case_id, run_id, freeze, expected)
    elif case_id == "L3-CV-S-01":
        result, comparisons, events = _convergence(case_id, run_id, freeze, expected, True)
    elif case_id == "L3-CV-T-01":
        result, comparisons, events = _convergence(case_id, run_id, freeze, expected, False)
    elif case_id == "L3-MB-01":
        result, comparisons, events = _mass(case_id, run_id, freeze, expected)
    elif case_id == "L3-ST-01":
        result, comparisons, events = _stability(case_id, run_id, freeze, expected)
    elif case_id == "L3-RT-01":
        result, comparisons, events = _retry(case_id, run_id, freeze, expected, False)
    elif case_id == "L3-RT-02":
        result, comparisons, events = _retry(case_id, run_id, freeze, expected, True)
    else:
        raise AssertionError(case_id)
    finite = _payload_finite(comparisons, freeze["tolerances"]["finite_absolute_limit"]) and _payload_finite(events, freeze["tolerances"]["finite_absolute_limit"])
    result["all_values_finite"] = bool(result.get("all_values_finite", True) and finite)
    if not result["all_values_finite"]:
        result["pass_flag"] = False
        result["observed_classification"] = "FAIL_NONFINITE"
    return {"case_result": result, "field_comparison": comparisons, "poro_event_log": events}
