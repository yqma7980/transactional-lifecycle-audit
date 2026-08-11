"""Frozen L4-D1 case dispatcher and output contracts."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any, Iterable

from .l4_fv import (
    all_finite,
    cumulative_phase_defects,
    field_metrics,
    front_location,
    l2_drift,
    make_snapshot,
    normalized_defect,
    pressure_from_saturation,
    run_to_checkpoints,
)
from .l4_lifecycle import (
    SafeTransactionalVariant,
    UnsafePreviousSaturationCacheVariant,
    compare_retry,
)
from .l4_oracle import oracle_profile
from .l4_state import (
    canonical_hash,
    CommittedState,
    DESIGN_VERSION,
    HOST_VERSION,
    TrialCandidate,
    TwoPhaseModel,
    phase_mass_n,
    phase_mass_w,
)


METRIC_COLUMNS = (
    "case_id", "run_id", "row_type", "level", "profile_id", "time",
    "cell_count", "cfl", "dt", "saturation_l1_absolute",
    "saturation_l2_absolute", "pressure_l2_absolute", "pressure_l2_relative",
    "pressure_linf_absolute", "displacement_absolute", "front_location",
    "front_absolute", "spatial_or_temporal_order_saturation",
    "spatial_or_temporal_order_front", "spatial_or_temporal_order_pressure",
    "spatial_or_temporal_order_displacement", "step_mass_defect_normalized_n",
    "step_mass_defect_normalized_w", "cumulative_mass_defect_normalized_n",
    "cumulative_mass_defect_normalized_w", "saturation_bounds_ok",
    "saturation_spatial_monotone", "pressure_nonnegative",
    "pressure_spatial_monotone", "mass_n_nondecreasing",
    "mass_w_nonincreasing", "front_nondecreasing", "oracle_root_residual",
    "oracle_quadrature_error", "note",
)

PROFILE_COLUMNS = (
    "case_id", "run_id", "profile_id", "accepted_version", "time",
    "cell_index", "x", "S_n", "S_w", "pressure", "lambda_n",
    "lambda_w", "fractional_flow_n", "phase_mass_n", "phase_mass_w",
    "front_location", "displacement", "committed_fingerprint",
    "output_provenance_fingerprint",
)

EVENT_COLUMNS = (
    "case_id", "run_id", "ordinal", "history_id", "event", "attempt_id",
    "variant", "accepted", "time", "dt", "cell_count",
    "committed_fingerprint", "candidate_fingerprint",
    "persistent_fingerprint", "candidate_reachable",
    "output_provenance_fingerprint", "minimum_saturation_n",
    "maximum_saturation_n", "minimum_pressure", "maximum_pressure",
    "phase_mass_n", "phase_mass_w", "front_location", "displacement",
    "flux_n_in", "flux_n_out", "flux_w_in", "flux_w_out",
    "mass_defect_n", "mass_defect_w", "finite", "note",
)


def load_design(root: Path) -> tuple[dict[str, Any], dict[str, dict[str, str]]]:
    base = root / "benchmarks" / "L4_two_phase_displacement"
    freeze = json.loads((base / "L4_D1_execution_freeze.json").read_text(encoding="utf-8"))
    with (base / "L4_D0_case_matrix.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    matrix = {row["case_id"]: row for row in rows}
    if len(matrix) != len(rows):
        raise RuntimeError("duplicate L4 case ID")
    if freeze["design_version"] != DESIGN_VERSION:
        raise RuntimeError("freeze/implementation version mismatch")
    if set(freeze["formal_cases"]) != set(matrix):
        raise RuntimeError("freeze/matrix case mismatch")
    return freeze, matrix


def _blank_metric(case_id: str, run_id: str, **values: Any) -> dict[str, Any]:
    row = {column: "NA" for column in METRIC_COLUMNS}
    row.update({"case_id": case_id, "run_id": run_id})
    row.update(values)
    return row


def _profile_rows(
    case_id: str,
    run_id: str,
    profile_id: str,
    model: TwoPhaseModel,
    state: CommittedState,
) -> list[dict[str, Any]]:
    snapshot = make_snapshot(model, state)
    output_hash = snapshot.physical_hash
    dx = model.H / len(state.saturation_n)
    rows: list[dict[str, Any]] = []
    for index, (saturation, pressure) in enumerate(
        zip(snapshot.saturation_n, snapshot.pressure)
    ):
        rows.append(
            {
                "case_id": case_id,
                "run_id": run_id,
                "profile_id": profile_id,
                "accepted_version": state.accepted_version,
                "time": state.time,
                "cell_index": index,
                "x": (index + 0.5) * dx,
                "S_n": saturation,
                "S_w": 1.0 - saturation,
                "pressure": pressure,
                "lambda_n": model.lambda_n(saturation),
                "lambda_w": model.lambda_w(saturation),
                "fractional_flow_n": model.fractional_flow_n(saturation),
                "phase_mass_n": snapshot.phase_mass_n,
                "phase_mass_w": snapshot.phase_mass_w,
                "front_location": snapshot.front_location,
                "displacement": snapshot.displacement,
                "committed_fingerprint": state.fingerprint,
                "output_provenance_fingerprint": output_hash,
            }
        )
    return rows


def _state_from_candidate(candidate: TrialCandidate, accepted_version: int) -> CommittedState:
    return CommittedState(
        time=candidate.time,
        saturation_n=candidate.saturation_n,
        cumulative_n_in=candidate.cumulative_n_in,
        cumulative_n_out=candidate.cumulative_n_out,
        cumulative_w_in=candidate.cumulative_w_in,
        cumulative_w_out=candidate.cumulative_w_out,
        accepted_version=accepted_version,
    )


def _event_from_candidate(
    case_id: str,
    run_id: str,
    ordinal: int,
    cell_count: int,
    model: TwoPhaseModel,
    candidate: TrialCandidate,
    *,
    note: str,
) -> dict[str, Any]:
    state = _state_from_candidate(candidate, ordinal)
    snapshot = make_snapshot(model, state)
    values = (
        *candidate.finite_values,
        *snapshot.pressure,
        snapshot.displacement,
        snapshot.phase_mass_n,
        snapshot.phase_mass_w,
    )
    return {
        "case_id": case_id,
        "run_id": run_id,
        "ordinal": ordinal,
        "history_id": "PHYSICAL",
        "event": "AcceptIncrement",
        "attempt_id": candidate.attempt_id,
        "variant": "safe_transactional",
        "accepted": True,
        "time": candidate.time,
        "dt": candidate.dt,
        "cell_count": cell_count,
        "committed_fingerprint": state.fingerprint,
        "candidate_fingerprint": candidate.fingerprint,
        "persistent_fingerprint": "NA",
        "candidate_reachable": False,
        "output_provenance_fingerprint": snapshot.physical_hash,
        "minimum_saturation_n": min(candidate.saturation_n),
        "maximum_saturation_n": max(candidate.saturation_n),
        "minimum_pressure": min(snapshot.pressure),
        "maximum_pressure": max(snapshot.pressure),
        "phase_mass_n": snapshot.phase_mass_n,
        "phase_mass_w": snapshot.phase_mass_w,
        "front_location": snapshot.front_location,
        "displacement": snapshot.displacement,
        "flux_n_in": candidate.flux_n_in,
        "flux_n_out": candidate.flux_n_out,
        "flux_w_in": candidate.flux_w_in,
        "flux_w_out": candidate.flux_w_out,
        "mass_defect_n": candidate.declared_n_mass_defect,
        "mass_defect_w": candidate.declared_w_mass_defect,
        "finite": all_finite(values),
        "note": note,
    }


def _checkpoint_candidate(
    candidates: Iterable[TrialCandidate], target: float
) -> TrialCandidate:
    for candidate in candidates:
        if abs(candidate.time - target) <= 1.0e-13:
            return candidate
    raise RuntimeError(f"no accepted candidate at checkpoint {target}")


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
        "two_way_flow_mechanics": False,
        "capillary_pressure": False,
    }


def _reference(
    case_id: str, run_id: str, freeze: dict[str, Any], expected: str
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    model = TwoPhaseModel()
    times = tuple(float(value) for value in freeze["oracle"]["reference_times"])
    states, candidates = run_to_checkpoints(model, 800, 0.4, times)
    metrics_rows: list[dict[str, Any]] = []
    profiles: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    passed = True
    for level, time in enumerate(times, 1):
        state = states[time]
        snapshot = make_snapshot(model, state)
        oracle = oracle_profile(800, time)
        metrics = field_metrics(model, snapshot, oracle)
        passed &= (
            metrics.saturation_l1_absolute <= freeze["tolerances"]["saturation_l1_absolute"]
            and metrics.front_absolute <= freeze["tolerances"]["front_absolute"]
            and metrics.pressure_l2_relative <= freeze["tolerances"]["pressure_l2_relative"]
            and metrics.pressure_linf_absolute <= freeze["tolerances"]["pressure_linf_absolute"]
            and metrics.displacement_absolute <= freeze["tolerances"]["mechanical_displacement_absolute"]
            and metrics.oracle_root_residual <= freeze["tolerances"]["root_residual_maximum"]
            and metrics.oracle_quadrature_error <= freeze["tolerances"]["quadrature_estimate_maximum"]
        )
        profile_id = f"reference_t_{time:g}"
        metrics_rows.append(_blank_metric(
            case_id, run_id, row_type="entropy_reference", level=level,
            profile_id=profile_id, time=time, cell_count=800, cfl=0.4,
            dt=0.4 * (1.0 / 800) / 2.0,
            saturation_l1_absolute=metrics.saturation_l1_absolute,
            saturation_l2_absolute=metrics.saturation_l2_absolute,
            pressure_l2_relative=metrics.pressure_l2_relative,
            pressure_linf_absolute=metrics.pressure_linf_absolute,
            displacement_absolute=metrics.displacement_absolute,
            front_location=snapshot.front_location,
            front_absolute=metrics.front_absolute,
            oracle_root_residual=metrics.oracle_root_residual,
            oracle_quadrature_error=metrics.oracle_quadrature_error,
            note="independent_entropy_resistance_oracle",
        ))
        profiles.extend(_profile_rows(case_id, run_id, profile_id, model, state))
        candidate = _checkpoint_candidate(candidates, time)
        events.append(_event_from_candidate(
            case_id, run_id, candidate_index(candidates, candidate), 800,
            model, candidate, note="accepted_reference_checkpoint"
        ))
    result = _base_result(case_id, run_id, expected)
    result.update({
        "observed_classification": expected if passed else "FAIL_ENTROPY_REFERENCE",
        "pass_flag": passed,
        "all_values_finite": _payload_finite((metrics_rows, profiles, events), 1.0e100),
        "metric_rows": len(metrics_rows),
        "profile_rows": len(profiles),
        "event_rows": len(events),
    })
    return result, metrics_rows, profiles, events


def candidate_index(candidates: Iterable[TrialCandidate], target: TrialCandidate) -> int:
    for index, candidate in enumerate(candidates, 1):
        if candidate is target:
            return index
    raise RuntimeError("candidate identity not found")


def _difference_metrics(
    model: TwoPhaseModel,
    left: CommittedState,
    right: CommittedState,
) -> tuple[float, float, float]:
    left_snapshot = make_snapshot(model, left)
    right_snapshot = make_snapshot(model, right)
    dx = model.H / len(left.saturation_n)
    saturation_l1 = sum(
        abs(a - b) for a, b in zip(left.saturation_n, right.saturation_n)
    ) * dx
    pressure_l2 = l2_drift(left_snapshot.pressure, right_snapshot.pressure, model.H)
    pressure_norm = math.sqrt(
        sum(value * value for value in right_snapshot.pressure) * dx
    )
    return (
        saturation_l1,
        pressure_l2 / pressure_norm,
        abs(left_snapshot.displacement - right_snapshot.displacement),
    )


def _convergence(
    case_id: str,
    run_id: str,
    freeze: dict[str, Any],
    expected: str,
    *,
    spatial: bool,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    model = TwoPhaseModel()
    metrics_rows: list[dict[str, Any]] = []
    profiles: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    saturation_errors: list[float] = []
    pressure_errors: list[float] = []
    displacement_errors: list[float] = []
    front_errors: list[float] = []
    if spatial:
        levels = tuple((cells, 0.4) for cells in (80, 160, 320))
        reference_state = None
    else:
        levels = tuple((800, cfl) for cfl in (0.4, 0.2, 0.1))
        reference_state = run_to_checkpoints(model, 800, 0.0125, (0.2,))[0][0.2]
    for level, (cells, cfl) in enumerate(levels, 1):
        states, candidates = run_to_checkpoints(model, cells, cfl, (0.2,))
        state = states[0.2]
        snapshot = make_snapshot(model, state)
        if spatial:
            oracle = oracle_profile(cells, 0.2)
            metrics = field_metrics(model, snapshot, oracle)
            saturation_error = metrics.saturation_l1_absolute
            pressure_error = metrics.pressure_l2_relative
            displacement_error = metrics.displacement_absolute
            front_error = metrics.front_absolute
        else:
            saturation_error, pressure_error, displacement_error = _difference_metrics(
                model, state, reference_state
            )
            front_error = "NA"
        saturation_errors.append(saturation_error)
        pressure_errors.append(pressure_error)
        displacement_errors.append(displacement_error)
        if spatial:
            front_errors.append(float(front_error))
        profile_id = f"{'mesh' if spatial else 'time'}_level_{level}"
        metrics_rows.append(_blank_metric(
            case_id, run_id, row_type="mesh_convergence" if spatial else "time_convergence",
            level=level, profile_id=profile_id, time=0.2, cell_count=cells,
            cfl=cfl, dt=cfl * (1.0 / cells) / 2.0,
            saturation_l1_absolute=saturation_error,
            pressure_l2_relative=pressure_error,
            displacement_absolute=displacement_error,
            front_location=snapshot.front_location,
            front_absolute=front_error,
            note="entropy_oracle" if spatial else "same_mesh_time_reference",
        ))
        profiles.extend(_profile_rows(case_id, run_id, profile_id, model, state))
        candidate = candidates[-1]
        events.append(_event_from_candidate(
            case_id, run_id, candidate_index(candidates, candidate), cells, model, candidate,
            note="convergence_endpoint"
        ))
    saturation_orders = _orders(saturation_errors)
    pressure_orders = _orders(pressure_errors)
    displacement_orders = _orders(displacement_errors)
    front_orders = _orders(front_errors) if spatial else None
    threshold = freeze["tolerances"]["spatial_order_minimum" if spatial else "temporal_order_minimum"]
    decreasing = (
        saturation_errors[0] > saturation_errors[1] > saturation_errors[2]
        and pressure_errors[0] > pressure_errors[1] > pressure_errors[2]
        and displacement_errors[0] > displacement_errors[1] > displacement_errors[2]
        and (not spatial or front_errors[0] > front_errors[1] > front_errors[2])
    )
    passed = (
        decreasing
        and saturation_orders[1] >= threshold
        and pressure_orders[1] >= threshold
        and displacement_orders[1] >= threshold
        and (not spatial or front_orders[1] >= threshold)
    )
    metrics_rows[-1].update({
        "spatial_or_temporal_order_saturation": saturation_orders[1],
        "spatial_or_temporal_order_pressure": pressure_orders[1],
        "spatial_or_temporal_order_displacement": displacement_orders[1],
        "spatial_or_temporal_order_front": front_orders[1] if spatial else "NA",
    })
    result = _base_result(case_id, run_id, expected)
    result.update({
        "observed_classification": expected if passed else "FAIL_CONVERGENCE",
        "pass_flag": passed,
        "all_values_finite": _payload_finite((metrics_rows, profiles, events), 1.0e100),
        "errors_decrease": decreasing,
        "saturation_orders": saturation_orders,
        "pressure_orders": pressure_orders,
        "displacement_orders": displacement_orders,
        "front_orders": front_orders,
        "metric_rows": len(metrics_rows),
        "profile_rows": len(profiles),
        "event_rows": len(events),
    })
    return result, metrics_rows, profiles, events


def _mass(
    case_id: str,
    run_id: str,
    freeze: dict[str, Any],
    expected: str,
    *,
    wetting: bool,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    model = TwoPhaseModel()
    states, candidates = run_to_checkpoints(model, 256, 0.4, (0.6,))
    state = states[0.6]
    step_n = [normalized_defect(c.internal_n_mass_defect) for c in candidates]
    step_w = [normalized_defect(c.internal_w_mass_defect) for c in candidates]
    cumulative_n, cumulative_w = cumulative_phase_defects(model, state)
    cumulative_n_normalized = normalized_defect(cumulative_n)
    cumulative_w_normalized = normalized_defect(cumulative_w)
    selected_step = max(step_w if wetting else step_n)
    selected_cumulative = cumulative_w_normalized if wetting else cumulative_n_normalized
    passed = (
        selected_step <= freeze["tolerances"]["mass_defect_maximum"]
        and selected_cumulative <= freeze["tolerances"]["mass_defect_maximum"]
    )
    metrics_rows = [_blank_metric(
        case_id, run_id, row_type="wetting_mass" if wetting else "nonwetting_mass",
        level=1, profile_id="mass_endpoint", time=0.6, cell_count=256,
        cfl=0.4, dt=0.4 * (1.0 / 256) / 2.0,
        step_mass_defect_normalized_n=max(step_n),
        step_mass_defect_normalized_w=max(step_w),
        cumulative_mass_defect_normalized_n=cumulative_n_normalized,
        cumulative_mass_defect_normalized_w=cumulative_w_normalized,
        note="phasewise_discrete_balance",
    )]
    profiles = _profile_rows(case_id, run_id, "mass_endpoint", model, state)
    events = [
        _event_from_candidate(case_id, run_id, index, 256, model, candidate,
                              note="phase_mass_balance_step")
        for index, candidate in enumerate(candidates, 1)
    ]
    result = _base_result(case_id, run_id, expected)
    result.update({
        "observed_classification": expected if passed else "FAIL_PHASE_MASS_BALANCE",
        "pass_flag": passed,
        "all_values_finite": _payload_finite((metrics_rows, profiles, events), 1.0e100),
        "maximum_step_mass_defect_normalized_n": max(step_n),
        "maximum_step_mass_defect_normalized_w": max(step_w),
        "cumulative_mass_defect_normalized_n": cumulative_n_normalized,
        "cumulative_mass_defect_normalized_w": cumulative_w_normalized,
        "metric_rows": 1,
        "profile_rows": len(profiles),
        "event_rows": len(events),
    })
    return result, metrics_rows, profiles, events


def _front(
    case_id: str, run_id: str, freeze: dict[str, Any], expected: str
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    model = TwoPhaseModel()
    times = tuple(float(value) for value in freeze["schedules"]["front_times"])
    states, candidates = run_to_checkpoints(model, 800, 0.4, times)
    metrics_rows: list[dict[str, Any]] = []
    profiles: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    fronts: list[float] = []
    passed = True
    for level, time in enumerate(times, 1):
        state = states[time]
        snapshot = make_snapshot(model, state)
        oracle = oracle_profile(800, time)
        error = abs(snapshot.front_location - oracle.front_location)
        fronts.append(snapshot.front_location)
        passed &= error <= freeze["tolerances"]["front_absolute"]
        profile_id = f"front_t_{time:g}"
        metrics_rows.append(_blank_metric(
            case_id, run_id, row_type="front", level=level,
            profile_id=profile_id, time=time, cell_count=800, cfl=0.4,
            dt=0.4 * (1.0 / 800) / 2.0,
            front_location=snapshot.front_location, front_absolute=error,
            note="threshold_S_star_over_2",
        ))
        profiles.extend(_profile_rows(case_id, run_id, profile_id, model, state))
        candidate = _checkpoint_candidate(candidates, time)
        events.append(_event_from_candidate(
            case_id, run_id, candidate_index(candidates, candidate), 800,
            model, candidate, note="accepted_front_checkpoint"
        ))
    increasing = all(right > left for left, right in zip(fronts, fronts[1:]))
    passed &= increasing and fronts[-1] < model.H
    result = _base_result(case_id, run_id, expected)
    result.update({
        "observed_classification": expected if passed else "FAIL_FRONT_LOCATION",
        "pass_flag": passed,
        "all_values_finite": _payload_finite((metrics_rows, profiles, events), 1.0e100),
        "front_strictly_increasing": increasing,
        "front_before_outlet": fronts[-1] < model.H,
        "metric_rows": len(metrics_rows),
        "profile_rows": len(profiles),
        "event_rows": len(events),
    })
    return result, metrics_rows, profiles, events


def _mechanics(
    case_id: str, run_id: str, freeze: dict[str, Any], expected: str
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    model = TwoPhaseModel()
    times = tuple(float(value) for value in freeze["schedules"]["mechanics_times"])
    states, candidates = run_to_checkpoints(model, 800, 0.4, times)
    metrics_rows: list[dict[str, Any]] = []
    profiles: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    displacements: list[float] = []
    passed = True
    for level, time in enumerate(times, 1):
        state = states[time]
        snapshot = make_snapshot(model, state)
        oracle = oracle_profile(800, time)
        metrics = field_metrics(model, snapshot, oracle)
        displacements.append(snapshot.displacement)
        passed &= (
            metrics.pressure_l2_relative <= freeze["tolerances"]["pressure_l2_relative"]
            and metrics.pressure_linf_absolute <= freeze["tolerances"]["pressure_linf_absolute"]
            and metrics.displacement_absolute <= freeze["tolerances"]["mechanical_displacement_absolute"]
        )
        profile_id = f"mechanics_t_{time:g}"
        metrics_rows.append(_blank_metric(
            case_id, run_id, row_type="one_way_mechanics", level=level,
            profile_id=profile_id, time=time, cell_count=800, cfl=0.4,
            dt=0.4 * (1.0 / 800) / 2.0,
            pressure_l2_relative=metrics.pressure_l2_relative,
            pressure_linf_absolute=metrics.pressure_linf_absolute,
            displacement_absolute=metrics.displacement_absolute,
            note="accepted_pressure_to_one_way_mechanics",
        ))
        profiles.extend(_profile_rows(case_id, run_id, profile_id, model, state))
        candidate = _checkpoint_candidate(candidates, time)
        events.append(_event_from_candidate(
            case_id, run_id, candidate_index(candidates, candidate), 800,
            model, candidate, note="accepted_mechanics_checkpoint"
        ))
    response_increasing = all(
        right >= left for left, right in zip(displacements, displacements[1:])
    )
    passed &= response_increasing
    result = _base_result(case_id, run_id, expected)
    result.update({
        "observed_classification": expected if passed else "FAIL_ONE_WAY_MECHANICS",
        "pass_flag": passed,
        "all_values_finite": _payload_finite((metrics_rows, profiles, events), 1.0e100),
        "response_nondecreasing": response_increasing,
        "mechanics_feedback_to_flow": False,
        "metric_rows": len(metrics_rows),
        "profile_rows": len(profiles),
        "event_rows": len(events),
    })
    return result, metrics_rows, profiles, events


def _stability(
    case_id: str, run_id: str, freeze: dict[str, Any], expected: str
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    model = TwoPhaseModel()
    states, candidates = run_to_checkpoints(model, 256, 0.4, (0.6,))
    slack = freeze["tolerances"]["stability_slack"]
    saturation_bounds = True
    saturation_monotone = True
    pressure_nonnegative = True
    pressure_monotone = True
    masses_n = [0.0]
    masses_w = [model.phi * model.H]
    fronts = [0.0]
    for candidate in candidates:
        saturation = candidate.saturation_n
        pressure = pressure_from_saturation(model, saturation)
        saturation_bounds &= min(saturation) >= -slack and max(saturation) <= 1.0 + slack
        saturation_monotone &= all(
            saturation[i] + slack >= saturation[i + 1]
            for i in range(len(saturation) - 1)
        )
        pressure_nonnegative &= min(pressure) >= -slack
        pressure_monotone &= all(
            pressure[i] + slack >= pressure[i + 1]
            for i in range(len(pressure) - 1)
        )
        masses_n.append(phase_mass_n(model, saturation))
        masses_w.append(phase_mass_w(model, saturation))
        fronts.append(front_location(saturation, model.H))
    mass_n_up = all(right + slack >= left for left, right in zip(masses_n, masses_n[1:]))
    mass_w_down = all(right <= left + slack for left, right in zip(masses_w, masses_w[1:]))
    front_up = all(right + slack >= left for left, right in zip(fronts, fronts[1:]))
    passed = all((
        saturation_bounds, saturation_monotone, pressure_nonnegative,
        pressure_monotone, mass_n_up, mass_w_down, front_up,
    ))
    state = states[0.6]
    metrics_rows = [_blank_metric(
        case_id, run_id, row_type="stability", level=1,
        profile_id="stability_endpoint", time=0.6, cell_count=256,
        cfl=0.4, dt=0.4 * (1.0 / 256) / 2.0,
        saturation_bounds_ok=saturation_bounds,
        saturation_spatial_monotone=saturation_monotone,
        pressure_nonnegative=pressure_nonnegative,
        pressure_spatial_monotone=pressure_monotone,
        mass_n_nondecreasing=mass_n_up, mass_w_nonincreasing=mass_w_down,
        front_nondecreasing=front_up, note="all_accepted_steps_no_clipping",
    )]
    profiles = _profile_rows(case_id, run_id, "stability_endpoint", model, state)
    events = [
        _event_from_candidate(case_id, run_id, index, 256, model, candidate,
                              note="stability_step")
        for index, candidate in enumerate(candidates, 1)
    ]
    result = _base_result(case_id, run_id, expected)
    result.update({
        "observed_classification": expected if passed else "FAIL_MONOTONE_STABILITY",
        "pass_flag": passed,
        "all_values_finite": _payload_finite((metrics_rows, profiles, events), 1.0e100),
        "saturation_bounds_ok": saturation_bounds,
        "saturation_spatial_monotone": saturation_monotone,
        "pressure_nonnegative": pressure_nonnegative,
        "pressure_spatial_monotone": pressure_monotone,
        "mass_n_nondecreasing": mass_n_up,
        "mass_w_nonincreasing": mass_w_down,
        "front_nondecreasing": front_up,
        "clipping_used": False,
        "metric_rows": 1,
        "profile_rows": len(profiles),
        "event_rows": len(events),
    })
    return result, metrics_rows, profiles, events


def _retry(
    case_id: str,
    run_id: str,
    freeze: dict[str, Any],
    expected: str,
    *,
    unsafe: bool,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    model = TwoPhaseModel()
    comparison = compare_retry(
        model, 32,
        UnsafePreviousSaturationCacheVariant if unsafe else SafeTransactionalVariant,
        trial_dt=0.01, replay_dt=0.005,
    )
    if unsafe:
        passed = (
            comparison.declared_context_equal
            and comparison.committed_before_replay_unchanged
            and comparison.rejected_candidate_unreachable
            and not comparison.observed_replay_fingerprint_equal
            and comparison.saturation_l2_drift >= freeze["tolerances"]["unsafe_saturation_l2_drift_floor"]
            and comparison.pressure_l2_drift >= freeze["tolerances"]["unsafe_pressure_l2_drift_floor"]
            and comparison.displacement_drift >= freeze["tolerances"]["unsafe_displacement_drift_floor"]
            and comparison.declared_phase_mass_defect >= freeze["tolerances"]["unsafe_declared_phase_mass_defect_floor"]
            and comparison.all_values_finite
        )
    else:
        passed = (
            comparison.declared_context_equal
            and comparison.committed_before_replay_unchanged
            and comparison.rejected_candidate_unreachable
            and comparison.accepted_saturation_exact
            and comparison.accepted_pressure_exact
            and comparison.accepted_displacement_exact
            and comparison.accepted_phase_masses_exact
            and comparison.accepted_state_fingerprint_exact
            and comparison.accepted_output_fingerprint_exact
            and comparison.observed_replay_fingerprint_equal
            and comparison.saturation_l2_drift == 0.0
            and comparison.pressure_l2_drift == 0.0
            and comparison.displacement_drift == 0.0
            and comparison.declared_phase_mass_defect
            <= freeze["tolerances"]["mass_defect_maximum"]
            and comparison.all_values_finite
        )
    metrics_rows = [_blank_metric(
        case_id, run_id, row_type="retry", level=1, profile_id="retry_comparison",
        time=0.005, cell_count=32, cfl="NA", dt=0.005,
        saturation_l2_absolute=comparison.saturation_l2_drift,
        pressure_l2_absolute=comparison.pressure_l2_drift,
        displacement_absolute=comparison.displacement_drift,
        cumulative_mass_defect_normalized_n=comparison.declared_phase_mass_defect,
        note="unsafe_negative_control" if unsafe else "safe_exact_retry",
    )]
    profiles = []
    profiles.extend(_profile_rows(
        case_id, run_id, "direct_accepted", model, comparison.direct_state
    ))
    profiles.extend(_profile_rows(
        case_id, run_id, "retry_accepted", model, comparison.retry_state
    ))
    events: list[dict[str, Any]] = []
    for source in comparison.events:
        row = {column: "NA" for column in EVENT_COLUMNS}
        row.update(source)
        row.update({"case_id": case_id, "run_id": run_id, "cell_count": 32})
        events.append(row)
    result = _base_result(case_id, run_id, expected)
    result.update({
        "observed_classification": expected if passed else "FAIL_RETRY_GATE",
        "pass_flag": passed,
        "all_values_finite": comparison.all_values_finite,
        "declared_context_equal": comparison.declared_context_equal,
        "committed_before_replay_unchanged": comparison.committed_before_replay_unchanged,
        "rejected_candidate_unreachable": comparison.rejected_candidate_unreachable,
        "accepted_saturation_exact": comparison.accepted_saturation_exact,
        "accepted_pressure_exact": comparison.accepted_pressure_exact,
        "accepted_displacement_exact": comparison.accepted_displacement_exact,
        "accepted_phase_masses_exact": comparison.accepted_phase_masses_exact,
        "accepted_state_fingerprint_exact": comparison.accepted_state_fingerprint_exact,
        "accepted_output_fingerprint_exact": comparison.accepted_output_fingerprint_exact,
        "observed_replay_fingerprint_equal": comparison.observed_replay_fingerprint_equal,
        "saturation_l2_drift": comparison.saturation_l2_drift,
        "pressure_l2_drift": comparison.pressure_l2_drift,
        "displacement_drift": comparison.displacement_drift,
        "declared_phase_mass_defect": comparison.declared_phase_mass_defect,
        "metric_rows": 1,
        "profile_rows": len(profiles),
        "event_rows": len(events),
    })
    return result, metrics_rows, profiles, events


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
    if case_id == "L4-REF-01":
        result, metrics, profiles, events = _reference(case_id, run_id, freeze, expected)
    elif case_id == "L4-CV-S-01":
        result, metrics, profiles, events = _convergence(case_id, run_id, freeze, expected, spatial=True)
    elif case_id == "L4-CV-T-01":
        result, metrics, profiles, events = _convergence(case_id, run_id, freeze, expected, spatial=False)
    elif case_id == "L4-MB-W-01":
        result, metrics, profiles, events = _mass(case_id, run_id, freeze, expected, wetting=True)
    elif case_id == "L4-MB-N-01":
        result, metrics, profiles, events = _mass(case_id, run_id, freeze, expected, wetting=False)
    elif case_id == "L4-FR-01":
        result, metrics, profiles, events = _front(case_id, run_id, freeze, expected)
    elif case_id == "L4-MECH-01":
        result, metrics, profiles, events = _mechanics(case_id, run_id, freeze, expected)
    elif case_id == "L4-ST-01":
        result, metrics, profiles, events = _stability(case_id, run_id, freeze, expected)
    elif case_id == "L4-RT-01":
        result, metrics, profiles, events = _retry(case_id, run_id, freeze, expected, unsafe=False)
    elif case_id == "L4-RT-02":
        result, metrics, profiles, events = _retry(case_id, run_id, freeze, expected, unsafe=True)
    else:
        raise AssertionError(case_id)
    finite = _payload_finite((metrics, profiles, events), freeze["tolerances"]["finite_absolute_limit"])
    result["all_values_finite"] = bool(result.get("all_values_finite", True) and finite)
    if not result["all_values_finite"]:
        result["pass_flag"] = False
        result["observed_classification"] = "FAIL_NONFINITE"
    result["output_contract_hash"] = canonical_hash({
        "metrics": metrics,
        "profiles": profiles,
        "events": events,
    })
    return {
        "case_result": result,
        "metric_comparison": metrics,
        "accepted_profile": profiles,
        "phase_event_log": events,
    }

