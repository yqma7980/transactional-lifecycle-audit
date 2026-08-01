"""Frozen L3, L4 and SciPy-host workloads for PERF-D1."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

import numpy as np
from scipy.optimize import least_squares

from benchmarks.L3_poroelastic_consolidation.src.l3_fv import (
    accept_candidate as l3_accept,
    make_candidate as l3_make_candidate,
)
from benchmarks.L3_poroelastic_consolidation.src.l3_state import (
    PoroModel,
    initial_state as l3_initial_state,
    make_snapshot as l3_make_snapshot,
)
from benchmarks.L4_two_phase_displacement.src.l4_fv import (
    accept_candidate as l4_accept,
    make_candidate as l4_make_candidate,
    make_snapshot as l4_make_snapshot,
)
from benchmarks.L4_two_phase_displacement.src.l4_state import (
    TwoPhaseModel,
    initial_state as l4_initial_state,
)
from benchmarks.L6_external_host.src.l6_scipy_adapter import HostConfiguration

from .perf_instrumentation import AuditCollector


def run_l3(row: dict[str, Any], audit: AuditCollector) -> tuple[dict[str, Any], dict[str, int]]:
    model = PoroModel()
    cell_count = int(row["n_cells"])
    steps = int(row["accepted_steps"])
    end_time = float(row["end_time"])
    dt = end_time / steps
    state = l3_initial_state(model, cell_count)

    for ordinal in range(1, steps + 1):
        audit.begin_attempt(
            {
                "family": "L3",
                "ordinal": ordinal,
                "accepted_version": state.accepted_version,
            }
        )
        candidate = l3_make_candidate(
            model,
            state,
            dt,
            attempt_id=f"PERF_L3_{ordinal:08d}",
        )
        audit.observe_candidate(
            {
                "family": "L3",
                "ordinal": ordinal,
                "time": candidate.time,
                "pressure_0": candidate.pressure[0],
                "pressure_last": candidate.pressure[-1],
                "declared_mass_defect": candidate.declared_mass_defect,
                "accepted_version_before": state.accepted_version,
            }
        )
        state = l3_accept(state, candidate)
        audit.commit(
            {
                "family": "L3",
                "ordinal": ordinal,
                "time": state.time,
                "accepted_version": state.accepted_version,
                "pressure_0": state.pressure[0],
                "pressure_last": state.pressure[-1],
            }
        )

    snapshot = l3_make_snapshot(model, state)
    output = {
        "family": "L3",
        "time": state.time,
        "pressure": list(state.pressure),
        "cumulative_outflow": state.cumulative_outflow,
        "accepted_version": state.accepted_version,
        "settlement": snapshot.settlement,
    }
    counts = {
        "accepted_steps_or_solves": steps,
        "kernel_step_evaluations": steps,
        "residual_evaluations": 0,
        "tangent_evaluations": 0,
        "accepted_callbacks": 0,
        "nonlinear_iteration_proxy": 0,
    }
    return output, counts


def run_l4(row: dict[str, Any], audit: AuditCollector) -> tuple[dict[str, Any], dict[str, int]]:
    model = TwoPhaseModel()
    cell_count = int(row["n_cells"])
    end_time = float(row["end_time"])
    cfl = float(row["cfl"])
    state = l4_initial_state(cell_count)
    dx = model.H / cell_count
    nominal_dt = cfl * dx / 2.0
    ordinal = 0
    tolerance = 1.0e-15

    while state.time < end_time - tolerance:
        ordinal += 1
        dt = min(nominal_dt, end_time - state.time)
        audit.begin_attempt(
            {
                "family": "L4",
                "ordinal": ordinal,
                "accepted_version": state.accepted_version,
            }
        )
        candidate = l4_make_candidate(
            model,
            state,
            dt,
            attempt_id=f"PERF_L4_{ordinal:08d}",
        )
        audit.observe_candidate(
            {
                "family": "L4",
                "ordinal": ordinal,
                "time": candidate.time,
                "saturation_0": candidate.saturation_n[0],
                "saturation_last": candidate.saturation_n[-1],
                "declared_n_mass_defect": candidate.declared_n_mass_defect,
                "declared_w_mass_defect": candidate.declared_w_mass_defect,
                "accepted_version_before": state.accepted_version,
            }
        )
        state = l4_accept(state, candidate)
        audit.commit(
            {
                "family": "L4",
                "ordinal": ordinal,
                "time": state.time,
                "accepted_version": state.accepted_version,
                "saturation_0": state.saturation_n[0],
                "saturation_last": state.saturation_n[-1],
            }
        )

    snapshot = l4_make_snapshot(model, state)
    output = {
        "family": "L4",
        "time": state.time,
        "saturation_n": list(snapshot.saturation_n),
        "pressure": list(snapshot.pressure),
        "phase_mass_n": snapshot.phase_mass_n,
        "phase_mass_w": snapshot.phase_mass_w,
        "front_location": snapshot.front_location,
        "displacement": snapshot.displacement,
        "accepted_version": snapshot.accepted_version,
    }
    counts = {
        "accepted_steps_or_solves": ordinal,
        "kernel_step_evaluations": ordinal,
        "residual_evaluations": 0,
        "tangent_evaluations": 0,
        "accepted_callbacks": 0,
        "nonlinear_iteration_proxy": 0,
    }
    return output, counts


class _PerformanceScipyHost:
    def __init__(self, audit: AuditCollector, solve_ordinal: int) -> None:
        self.audit = audit
        self.solve_ordinal = solve_ordinal
        self.config = HostConfiguration()
        self.nfev = 0
        self.njev = 0
        self.callbacks = 0
        self.last_callback_x: float | None = None

    def fun(self, x_array: np.ndarray) -> np.ndarray:
        x = float(x_array[0])
        self.nfev += 1
        residual = x**3 - 2.0 * x + 2.0
        self.audit.begin_attempt(
            {
                "family": "L6",
                "solve": self.solve_ordinal,
                "residual_evaluation": self.nfev,
            }
        )
        self.audit.observe_candidate(
            {
                "family": "L6",
                "solve": self.solve_ordinal,
                "residual_evaluation": self.nfev,
                "x": x,
                "residual": residual,
                "residual_state_version": f"accepted:0|x:{x.hex()}",
            }
        )
        return np.array([residual], dtype=float)

    def jac(self, x_array: np.ndarray) -> np.ndarray:
        x = float(x_array[0])
        self.njev += 1
        tangent = 3.0 * x**2 - 2.0
        self.audit.observe_tangent(
            {
                "family": "L6",
                "solve": self.solve_ordinal,
                "tangent_evaluation": self.njev,
                "x": x,
                "tangent": tangent,
                "tangent_state_version": f"accepted:0|x:{x.hex()}",
            }
        )
        return np.array([[tangent]], dtype=float)

    def callback(self, intermediate_result: Any) -> None:
        x = float(intermediate_result.x[0])
        self.callbacks += 1
        self.last_callback_x = x
        self.audit.accepted_callback(
            {
                "family": "L6",
                "solve": self.solve_ordinal,
                "callback": self.callbacks,
                "x": x,
                "cost": float(intermediate_result.cost),
                "nfev": int(intermediate_result.nfev),
                "nit": int(intermediate_result.nit),
            }
        )

    def run(self) -> dict[str, Any]:
        config = self.config
        result = least_squares(
            fun=self.fun,
            x0=np.array([config.x0], dtype=float),
            jac=self.jac,
            method=config.method,
            tr_solver=config.tr_solver,
            ftol=config.ftol,
            xtol=config.xtol,
            gtol=config.gtol,
            max_nfev=config.max_nfev,
            x_scale=config.x_scale,
            loss=config.loss,
            callback=self.callback,
            verbose=0,
        )
        final_x = float(result.x[0])
        if not result.success:
            raise RuntimeError(f"SciPy host failed: {result.message}")
        if self.last_callback_x is None or self.last_callback_x.hex() != final_x.hex():
            raise RuntimeError("host return does not match final accepted callback")
        self.audit.commit(
            {
                "family": "L6",
                "solve": self.solve_ordinal,
                "x": final_x,
                "residual": float(result.fun[0]),
                "cost": float(result.cost),
                "accepted_version": 1,
            }
        )
        return {
            "solve": self.solve_ordinal,
            "x": final_x,
            "residual": float(result.fun[0]),
            "cost": float(result.cost),
            "nfev": int(result.nfev),
            "njev": int(result.njev),
            "status": int(result.status),
            "accepted_callbacks": self.callbacks,
        }


def run_l6(row: dict[str, Any], audit: AuditCollector) -> tuple[dict[str, Any], dict[str, int]]:
    repeats = int(row["batch_repeats"])
    solves: list[dict[str, Any]] = []
    for ordinal in range(1, repeats + 1):
        solves.append(_PerformanceScipyHost(audit, ordinal).run())
    output = {"family": "L6", "solves": solves}
    counts = {
        "accepted_steps_or_solves": repeats,
        "kernel_step_evaluations": 0,
        "residual_evaluations": sum(item["nfev"] for item in solves),
        "tangent_evaluations": sum(item["njev"] for item in solves),
        "accepted_callbacks": sum(item["accepted_callbacks"] for item in solves),
        "nonlinear_iteration_proxy": sum(item["accepted_callbacks"] for item in solves),
    }
    return output, counts


def execute_family(row: dict[str, Any], audit: AuditCollector) -> tuple[dict[str, Any], dict[str, int]]:
    family = row["family"]
    if family == "L3":
        return run_l3(row, audit)
    if family == "L4":
        return run_l4(row, audit)
    if family == "L6":
        return run_l6(row, audit)
    raise ValueError(f"unknown family: {family}")


__all__ = ["execute_family", "run_l3", "run_l4", "run_l6"]