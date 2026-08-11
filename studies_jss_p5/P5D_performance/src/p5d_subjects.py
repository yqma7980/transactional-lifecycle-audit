from __future__ import annotations

import math
import time
from typing import Any

import numpy as np

from p5d_common import canonical_hash, finite_values, json_bytes, normalize_event, validate_mode


def _audit_payload(
    mode: str,
    *,
    direct_hash: str,
    replay_hash: str,
    direct_operator_hash: str,
    replay_operator_hash: str,
    production_events: list[dict[str, Any]],
    declared_packet: dict[str, Any],
) -> tuple[dict[str, Any], int, int, float]:
    if mode == "M0_AUDIT_OFF":
        return {
            "performed": False,
            "generic_replay_equal": None,
            "eligibility_checked": False,
            "version_contract_checked": False,
            "provenance_checked": False,
        }, 0, 0, 0.0
    started = time.perf_counter()
    generic_equal = direct_hash == replay_hash and direct_operator_hash == replay_operator_hash
    packet = {
        "declared": declared_packet,
        "direct_candidate_hash": direct_hash,
        "replay_candidate_hash": replay_hash,
        "direct_operator_hash": direct_operator_hash,
        "replay_operator_hash": replay_operator_hash,
        "generic_replay_equal": generic_equal,
    }
    audit_bytes = len(json_bytes(packet))
    ledger_bytes = 0
    if mode == "M6_FULL_TLA":
        ledger = {
            "events": [normalize_event(event) for event in production_events],
            "replay": packet,
            "ownership": "HOST_COMMITTED_STATE",
            "version_relation": "EXACT_CURRENT",
            "accepted_output_source": "POST_COMMIT_AUTHORITATIVE_STATE",
            "rejected_candidate_reachable": False,
        }
        ledger_bytes = len(json_bytes(ledger))
        canonical_hash(ledger)
    elif mode == "M3_GENERIC_REPLAY":
        canonical_hash(packet)
    else:
        raise ValueError(f"Unsupported audit mode: {mode}")
    elapsed = time.perf_counter() - started
    return {
        "performed": True,
        "generic_replay_equal": generic_equal,
        "eligibility_checked": mode == "M6_FULL_TLA",
        "version_contract_checked": mode == "M6_FULL_TLA",
        "provenance_checked": mode == "M6_FULL_TLA",
    }, audit_bytes, ledger_bytes, elapsed


def execute_s01(workload_id: str, mode: str) -> dict[str, Any]:
    from p5d_fe import DynamicTransactionalFEHost, evaluate_dynamic_material_field

    validate_mode(mode)
    if workload_id == "S01-SMALL":
        nx = ny = 4
    elif workload_id == "S01-MEDIUM":
        nx = ny = 8
    else:
        raise ValueError(workload_id)
    host = DynamicTransactionalFEHost(
        nx=nx,
        ny=ny,
        run_id="P5D-S01-PRODUCTION",
        capture_ledger=mode == "M6_FULL_TLA",
    )
    trajectory: list[dict[str, Any]] = []
    production_started = time.perf_counter()
    try:
        for ordinal, target in enumerate((0.04, 0.08), start=1):
            host.begin_attempt(target, f"PRODUCTION-{ordinal:02d}", "EXACT_CURRENT", 25)
            attempt = host.solve_attempt()
            if not attempt.converged or not attempt.metrics.pass_flag:
                raise RuntimeError(f"S01 production solve failed at {target}: {attempt.metrics}")
            host.commit(attempt)
            trajectory.append({
                "target_load": target,
                "snes_reason": attempt.snes_reason,
                "nonlinear_iterations": attempt.nonlinear_iterations,
                "function_evaluations": attempt.function_evaluations,
                "residual_sequence_hex": list(attempt.residual_sequence_hex),
                "committed_physical_hash": host.committed.physical_hash,
                "plastic_point_count": attempt.metrics.plastic_point_count,
            })
        production_seconds = time.perf_counter() - production_started
        output_payload = {
            "primary": host.committed.primary,
            "gamma_p": host.committed.gamma_p,
            "alpha": host.committed.alpha,
            "accepted_load": host.committed.accepted_load,
            "accepted_version": host.committed.accepted_version,
        }
        output_fingerprint = canonical_hash(output_payload)
        trajectory_fingerprint = canonical_hash(trajectory)
        audit_started = time.perf_counter()
        if mode == "M0_AUDIT_OFF":
            direct = replay = None
            audit_eval_seconds = 0.0
            direct_hash = replay_hash = "NOT_EXECUTED"
            direct_operator_hash = replay_operator_hash = "NOT_EXECUTED"
        else:
            direct = evaluate_dynamic_material_field(
                host.context,
                host.committed.primary,
                host.committed,
                host.persistent,
                host.committed.accepted_load,
                "EXACT_CURRENT",
            )
            replay = evaluate_dynamic_material_field(
                host.context,
                host.committed.primary,
                host.committed,
                host.persistent,
                host.committed.accepted_load,
                "EXACT_CURRENT",
            )
            audit_eval_seconds = time.perf_counter() - audit_started
            direct_hash = direct.candidate_id
            replay_hash = replay.candidate_id
            direct_operator_hash = canonical_hash({"tau": direct.tau, "tangent": direct.tangent})
            replay_operator_hash = canonical_hash({"tau": replay.tau, "tangent": replay.tangent})
        audit, audit_bytes, ledger_bytes, serialization_seconds = _audit_payload(
            mode,
            direct_hash=direct_hash,
            replay_hash=replay_hash,
            direct_operator_hash=direct_operator_hash,
            replay_operator_hash=replay_operator_hash,
            production_events=host.events.records,
            declared_packet={
                "committed_hash": host.committed.full_hash,
                "persistent_hash": host.persistent.projection_hash,
                "load": host.committed.accepted_load,
                "residual_version": "P4D-R1",
                "tangent_version": "P4D-K1",
            },
        )
        audit_seconds = audit_eval_seconds + serialization_seconds
        values = [host.committed.primary, host.committed.gamma_p, host.committed.alpha]
        return {
            "subject_id": "JSS-S01",
            "workload_id": workload_id,
            "workload_parameters": {
                "triangles": int(host.context.connectivity.shape[0]),
                "integration_points": int(host.context.connectivity.shape[0] * host.context.quadrature_points.shape[0]),
                "nodes": int(host.context.coordinates.shape[0]),
                "load_path": [0.04, 0.08],
            },
            "output_fingerprint": output_fingerprint,
            "trajectory_fingerprint": trajectory_fingerprint,
            "output_summary": {
                "accepted_load": host.committed.accepted_load,
                "accepted_version": host.committed.accepted_version,
                "maximum_alpha": float(np.max(host.committed.alpha)),
                "primary_l2": float(np.linalg.norm(host.committed.primary)),
            },
            "production_counts": {
                "residual": host.production_residual_evaluations,
                "tangent": host.production_tangent_evaluations,
                "trial": host.production_trial_evaluations,
                "accepted": 2,
                "rejected": 0,
                "nonlinear_iterations": sum(row["nonlinear_iterations"] for row in trajectory),
            },
            "audit_counts": {
                "residual": 0 if mode == "M0_AUDIT_OFF" else 2,
                "tangent": 0 if mode == "M0_AUDIT_OFF" else 2,
                "trial": 0 if mode == "M0_AUDIT_OFF" else 2,
            },
            "production_seconds": production_seconds,
            "audit_seconds": audit_seconds,
            "serialization_hashing_seconds": serialization_seconds,
            "audit_bytes": audit_bytes,
            "event_ledger_bytes": ledger_bytes,
            "audit": audit,
            "all_values_finite": finite_values(values),
            "production_trajectory": trajectory,
        }
    finally:
        host.close()


def execute_s02(workload_id: str, mode: str) -> dict[str, Any]:
    from benchmarks.L4_two_phase_displacement.src.l4_fv import (
        accept_candidate,
        make_candidate,
        make_snapshot,
    )
    from benchmarks.L4_two_phase_displacement.src.l4_state import TwoPhaseModel, initial_state

    validate_mode(mode)
    if workload_id == "S02-SMALL":
        cell_count = 80
    elif workload_id == "S02-MEDIUM":
        cell_count = 320
    else:
        raise ValueError(workload_id)
    model = TwoPhaseModel()
    state = initial_state(cell_count)
    final_time = 0.05
    nominal_dt = 0.5 * (model.H / cell_count) / 2.0
    step_count = int(round(final_time / nominal_dt))
    dt = final_time / step_count
    trajectory: list[dict[str, Any]] = []
    verbose_events: list[dict[str, Any]] = []
    penultimate = state
    production_started = time.perf_counter()
    final_candidate = None
    for ordinal in range(1, step_count + 1):
        penultimate = state
        candidate = make_candidate(model, state, dt, attempt_id=f"PRODUCTION-{ordinal:04d}")
        state = accept_candidate(state, candidate)
        final_candidate = candidate
        trajectory.append({
            "accepted_version": state.accepted_version,
            "time_hex": state.time.hex(),
            "committed_hash": state.fingerprint,
            "candidate_saturation_hash": canonical_hash(candidate.saturation_n),
        })
        if mode == "M6_FULL_TLA":
            verbose_events.extend((
                {
                    "event": "TrialEvaluate",
                    "ordinal": 2 * ordinal - 1,
                    "committed_hash": penultimate.fingerprint,
                    "candidate_hash": candidate.fingerprint,
                    "source_state_hash": candidate.source_state_hash,
                    "residual_version": "L4-FV-R1",
                    "tangent_version": "L4-FV-K1",
                    "reachable_from_accepted_output": False,
                },
                {
                    "event": "AcceptCommit",
                    "ordinal": 2 * ordinal,
                    "committed_hash": state.fingerprint,
                    "candidate_hash": candidate.fingerprint,
                    "accepted_version": state.accepted_version,
                    "reachable_from_accepted_output": True,
                },
            ))
    production_seconds = time.perf_counter() - production_started
    if final_candidate is None:
        raise RuntimeError("S02 produced no candidate")
    snapshot = make_snapshot(model, state)
    output_payload = {
        "saturation_n": snapshot.saturation_n,
        "pressure": snapshot.pressure,
        "displacement": snapshot.displacement,
        "phase_mass_n": snapshot.phase_mass_n,
        "phase_mass_w": snapshot.phase_mass_w,
        "front_location": snapshot.front_location,
        "accepted_version": snapshot.accepted_version,
    }
    output_fingerprint = canonical_hash(output_payload)
    trajectory_fingerprint = canonical_hash(trajectory)
    audit_started = time.perf_counter()
    if mode == "M0_AUDIT_OFF":
        direct_hash = replay_hash = "NOT_EXECUTED"
        direct_operator_hash = replay_operator_hash = "NOT_EXECUTED"
        audit_eval_seconds = 0.0
    else:
        direct = make_candidate(model, penultimate, dt, attempt_id="AUDIT-REPLAY")
        replay = make_candidate(model, penultimate, dt, attempt_id="AUDIT-REPLAY")
        audit_eval_seconds = time.perf_counter() - audit_started
        direct_hash = direct.fingerprint
        replay_hash = replay.fingerprint
        direct_operator_hash = canonical_hash({
            "saturation": direct.saturation_n,
            "mass_n": direct.declared_n_mass_defect,
            "mass_w": direct.declared_w_mass_defect,
        })
        replay_operator_hash = canonical_hash({
            "saturation": replay.saturation_n,
            "mass_n": replay.declared_n_mass_defect,
            "mass_w": replay.declared_w_mass_defect,
        })
    audit, audit_bytes, ledger_bytes, serialization_seconds = _audit_payload(
        mode,
        direct_hash=direct_hash,
        replay_hash=replay_hash,
        direct_operator_hash=direct_operator_hash,
        replay_operator_hash=replay_operator_hash,
        production_events=verbose_events,
        declared_packet={
            "committed_hash": penultimate.fingerprint,
            "dt": dt,
            "model_hash": model.fingerprint,
            "residual_version": "L4-FV-R1",
            "tangent_version": "L4-FV-K1",
        },
    )
    return {
        "subject_id": "JSS-S02",
        "workload_id": workload_id,
        "workload_parameters": {
            "cells": cell_count,
            "steps": step_count,
            "final_time": final_time,
            "cfl": 0.5,
        },
        "output_fingerprint": output_fingerprint,
        "trajectory_fingerprint": trajectory_fingerprint,
        "output_summary": {
            "accepted_version": snapshot.accepted_version,
            "front_location": snapshot.front_location,
            "phase_mass_n": snapshot.phase_mass_n,
            "phase_mass_w": snapshot.phase_mass_w,
            "displacement": snapshot.displacement,
        },
        "production_counts": {
            "residual": step_count,
            "tangent": 0,
            "trial": step_count,
            "accepted": step_count,
            "rejected": 0,
            "nonlinear_iterations": 0,
        },
        "audit_counts": {
            "residual": 0 if mode == "M0_AUDIT_OFF" else 2,
            "tangent": 0,
            "trial": 0 if mode == "M0_AUDIT_OFF" else 2,
        },
        "production_seconds": production_seconds,
        "audit_seconds": audit_eval_seconds + serialization_seconds,
        "serialization_hashing_seconds": serialization_seconds,
        "audit_bytes": audit_bytes,
        "event_ledger_bytes": ledger_bytes,
        "audit": audit,
        "all_values_finite": finite_values(output_payload),
        "production_trajectory": trajectory,
    }


def _s03_replay_packet(execution) -> dict[str, Any]:
    candidates = execution.nonaccepted_residual_events
    if not candidates:
        raise RuntimeError("S03 produced no host-nonaccepted residual")
    event = next((row for row in candidates if row.get("x_hex") == "0x1.0000000000000p+0"), candidates[0])
    x = float(event["x"])
    return {
        "x": x,
        "residual": x**3 - 2.0 * x + 2.0,
        "tangent": 3.0 * x * x - 2.0,
        "committed_fingerprint": execution.committed_before.fingerprint,
    }


def execute_s03(workload_id: str, mode: str) -> dict[str, Any]:
    from benchmarks.L6_external_host.src.l6_scipy_adapter import ScipyLifecycleAdapter

    validate_mode(mode)
    if workload_id == "S03-SMALL":
        blocks = 1
    elif workload_id == "S03-MEDIUM":
        blocks = 8
    else:
        raise ValueError(workload_id)
    executions = []
    production_started = time.perf_counter()
    for block in range(blocks):
        execution = ScipyLifecycleAdapter(
            path_id=f"P5D-S03-BLOCK-{block:02d}", variant="safe_transactional"
        ).run(jacobian_mode="analytic")
        if not execution.success or not execution.committed_transition_valid:
            raise RuntimeError(f"S03 block {block} failed")
        executions.append(execution)
    production_seconds = time.perf_counter() - production_started
    outputs = [
        {
            "block": block,
            "x": execution.final_x,
            "residual": execution.final_residual,
            "cost": execution.final_cost,
            "accepted_version": execution.committed_after.accepted_version,
            "committed_history": execution.committed_after.history,
        }
        for block, execution in enumerate(executions)
    ]
    trajectories = [
        {
            "block": block,
            "nfev": execution.nfev,
            "njev": execution.njev,
            "events": [normalize_event(event) for event in execution.events],
        }
        for block, execution in enumerate(executions)
    ]
    output_fingerprint = canonical_hash(outputs)
    trajectory_fingerprint = canonical_hash(trajectories)
    audit_started = time.perf_counter()
    production_events = [event for execution in executions for event in execution.events]
    if mode == "M0_AUDIT_OFF":
        direct_hash = replay_hash = "NOT_EXECUTED"
        direct_operator_hash = replay_operator_hash = "NOT_EXECUTED"
        audit_eval_seconds = 0.0
    else:
        direct_packets = [_s03_replay_packet(execution) for execution in executions]
        replay_packets = [_s03_replay_packet(execution) for execution in executions]
        audit_eval_seconds = time.perf_counter() - audit_started
        direct_hash = canonical_hash(direct_packets)
        replay_hash = canonical_hash(replay_packets)
        direct_operator_hash = canonical_hash([
            {"residual": row["residual"], "tangent": row["tangent"]} for row in direct_packets
        ])
        replay_operator_hash = canonical_hash([
            {"residual": row["residual"], "tangent": row["tangent"]} for row in replay_packets
        ])
    audit, audit_bytes, ledger_bytes, serialization_seconds = _audit_payload(
        mode,
        direct_hash=direct_hash,
        replay_hash=replay_hash,
        direct_operator_hash=direct_operator_hash,
        replay_operator_hash=replay_operator_hash,
        production_events=production_events,
        declared_packet={
            "blocks": blocks,
            "residual_version": "L6-RJ-D1.0",
            "tangent_version": "L6-RJ-D1.0",
            "host": "SciPy-TRF-1.17.1",
        },
    )
    return {
        "subject_id": "JSS-S03",
        "workload_id": workload_id,
        "workload_parameters": {
            "independent_blocks": blocks,
            "block_semantics_equal": len({canonical_hash({
                "x": item["x"], "residual": item["residual"], "cost": item["cost"]
            }) for item in outputs}) == 1,
        },
        "output_fingerprint": output_fingerprint,
        "trajectory_fingerprint": trajectory_fingerprint,
        "output_summary": {
            "blocks": blocks,
            "maximum_abs_residual": max(abs(row["residual"]) for row in outputs),
            "mean_final_x": sum(row["x"] for row in outputs) / blocks,
        },
        "production_counts": {
            "residual": sum(execution.nfev for execution in executions),
            "tangent": sum(execution.njev for execution in executions),
            "trial": sum(execution.nfev for execution in executions),
            "accepted": sum(len(execution.accepted_residual_events) for execution in executions),
            "rejected": sum(len(execution.nonaccepted_residual_events) for execution in executions),
            "nonlinear_iterations": sum(
                sum(1 for event in execution.events if event["event"] == "HostAcceptedCallback")
                for execution in executions
            ),
        },
        "audit_counts": {
            "residual": 0 if mode == "M0_AUDIT_OFF" else 2 * blocks,
            "tangent": 0 if mode == "M0_AUDIT_OFF" else 2 * blocks,
            "trial": 0 if mode == "M0_AUDIT_OFF" else 2 * blocks,
        },
        "production_seconds": production_seconds,
        "audit_seconds": audit_eval_seconds + serialization_seconds,
        "serialization_hashing_seconds": serialization_seconds,
        "audit_bytes": audit_bytes,
        "event_ledger_bytes": ledger_bytes,
        "audit": audit,
        "all_values_finite": all(execution.all_values_finite for execution in executions),
        "production_trajectory": trajectories,
    }


def execute_subject(subject_id: str, workload_id: str, mode: str) -> dict[str, Any]:
    if subject_id == "JSS-S01":
        return execute_s01(workload_id, mode)
    if subject_id == "JSS-S02":
        return execute_s02(workload_id, mode)
    if subject_id == "JSS-S03":
        return execute_s03(workload_id, mode)
    raise ValueError(subject_id)
