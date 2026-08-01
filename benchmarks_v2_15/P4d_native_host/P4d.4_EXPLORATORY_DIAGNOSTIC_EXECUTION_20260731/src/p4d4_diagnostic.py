from __future__ import annotations

import csv
import json
import pathlib
from dataclasses import asdict
from typing import Any

import numpy as np

from p4d_canonical import canonical_hash, file_sha256
from p4d_config import EQUILIBRIUM_TOL, YIELD_TOL
from p4d_host import AttemptResult, TransactionalFEHost
from p4d_io import AcceptedOutputStore, write_json_new
from p4d_observer import read_c_ledger
from p4d_state import PersistentState, initial_committed_state


CASE_TARGETS = {
    "P4D4-DIAG-LS-01": 0.20,
    "P4D4-DIAG-LS-02": 0.24,
    "P4D4-DIAG-LS-03": 0.28,
}
PREHISTORY_TARGETS = (0.04, 0.08, 0.10, 0.12, 0.16, 0.20, 0.14, 0.08)
RELATION = "DECLARED_ACCEPTED_STATE_LAG"


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


def _write_event_csv(path: pathlib.Path, events: list[dict[str, Any]]) -> None:
    fields = sorted({key for event in events for key in event})
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for event in events:
            writer.writerow(
                {
                    key: json.dumps(_jsonable(value), sort_keys=True)
                    if isinstance(value, (dict, list, tuple))
                    else value
                    for key, value in event.items()
                }
            )


def _attempt_summary(attempt: AttemptResult, phase: str) -> dict[str, Any]:
    return {
        "phase": phase,
        "attempt_id": attempt.attempt_id,
        "source_load": attempt.source_load,
        "target_load": attempt.target_load,
        "relation": attempt.relation,
        "snes_reason": attempt.snes_reason,
        "nonlinear_iterations": attempt.nonlinear_iterations,
        "function_evaluations": attempt.function_evaluations,
        "selected_candidate_id": attempt.selected_packet.candidate_id,
        "committed_immutable": (
            attempt.committed_hash_before == attempt.committed_hash_after_callbacks
        ),
        "mechanics": asdict(attempt.metrics),
    }


def _vector_hash(hex_values: list[str] | None) -> str | None:
    if hex_values is None:
        return None
    return canonical_hash(
        np.asarray([float.fromhex(value) for value in hex_values], dtype=np.float64)
    )


def _classify_diagnostic_native_events(
    c_events: list[dict[str, Any]], python_events: list[dict[str, Any]]
) -> dict[str, Any]:
    candidates = [
        event
        for event in c_events
        if event.get("callback_kind") == "LINE_SEARCH_CANDIDATE"
    ]
    selected = {
        event.get("event_ordinal"): event
        for event in c_events
        if event.get("callback_kind") == "LINE_SEARCH_SELECTED"
    }
    python_hashes = {
        event.get("primary_vector_hash")
        for event in python_events
        if event.get("event_kind") == "TrialEvaluate"
    }
    correlated = 0
    unselected_ordinals: list[int] = []
    pairs: list[dict[str, Any]] = []
    for candidate in candidates:
        ordinal = int(candidate["event_ordinal"])
        candidate_hash = _vector_hash(candidate.get("W_hex_values"))
        selected_event = selected.get(ordinal)
        selected_hash = (
            _vector_hash(selected_event.get("W_hex_values"))
            if selected_event is not None
            else None
        )
        exact_python_correlation = candidate_hash in python_hashes
        if exact_python_correlation:
            correlated += 1
        is_unselected = selected_event is None or candidate_hash != selected_hash
        if is_unselected:
            unselected_ordinals.append(ordinal)
        pairs.append(
            {
                "event_ordinal": ordinal,
                "nonlinear_iteration": candidate.get("nonlinear_iteration"),
                "candidate_lambda_hex": candidate.get("lambda_hex"),
                "selected_lambda_hex": (
                    selected_event.get("lambda_hex")
                    if selected_event is not None
                    else None
                ),
                "candidate_work_hash": candidate_hash,
                "selected_work_hash": selected_hash,
                "candidate_selected_equal": not is_unselected,
                "exact_python_trial_correlation": exact_python_correlation,
            }
        )
    candidate_count = len(candidates)
    correlation_complete = candidate_count > 0 and correlated == candidate_count
    observer_read_only = all(
        event.get("postcheck_change_flags") is False
        for event in c_events
        if event.get("callback_kind") == "ATTACH"
    )
    return {
        "candidate_event_count": candidate_count,
        "selected_event_count": len(selected),
        "structured_unselected_candidate_count": len(unselected_ordinals),
        "structured_unselected_candidate_present": bool(unselected_ordinals),
        "structured_unselected_event_ordinals": unselected_ordinals,
        "candidate_to_python_packet_correlation_count": correlated,
        "candidate_to_python_packet_correlation_complete": correlation_complete,
        "postcheck_flags_read_only": observer_read_only,
        "candidate_selection_pairs": pairs,
    }


def _mechanics_pass(attempt: AttemptResult) -> bool:
    metrics = attempt.metrics
    return bool(
        metrics.all_values_finite
        and metrics.alpha_bounded
        and metrics.alpha_nondecreasing
        and metrics.free_residual_relative <= EQUILIBRIUM_TOL
        and metrics.reaction_balance_relative <= EQUILIBRIUM_TOL
        and metrics.yield_consistency_relative <= YIELD_TOL
    )


def execute_diagnostic(
    *,
    case_id: str,
    run_id: str,
    result_directory: pathlib.Path,
    p4d2_root: pathlib.Path,
    environment: dict[str, Any],
) -> dict[str, Any]:
    if case_id not in CASE_TARGETS:
        raise ValueError(f"unknown P4d.4 diagnostic case {case_id}")
    if not result_directory.exists() or any(result_directory.iterdir()):
        raise RuntimeError("diagnostic result directory must exist and be empty")

    target_load = CASE_TARGETS[case_id]
    observer_ledger = result_directory / "c_observer_ledger.jsonl"
    observer_library = p4d2_root / "build" / "libp4d_observer.so"
    if file_sha256(observer_library) != (
        "a43222350c3fa3f7efecb535d673ab88393b61673b1004bcf3517ef4ef9047e6"
    ):
        raise RuntimeError("frozen observer binary hash mismatch")

    environment_hash = canonical_hash(
        {key: value for key, value in environment.items() if key != "run_id"}
    )
    persistent = PersistentState()
    output = AcceptedOutputStore()
    host = TransactionalFEHost(
        initial_committed_state(),
        persistent,
        run_id=f"{case_id}-{run_id}",
        observer_library=observer_library,
        observer_ledger=observer_ledger,
    )
    attempts: list[dict[str, Any]] = []
    prehistory_pass = True
    diagnostic_attempt: AttemptResult | None = None
    diagnostic_python_start = 0
    diagnostic_c_start = 0
    source_state_hash = None
    source_state_ready = False

    try:
        for index, load in enumerate(PREHISTORY_TARGETS, start=1):
            host.begin_attempt(
                load,
                f"{case_id}-{run_id}-PRE-{index:02d}",
                "EXACT_CURRENT",
                maximum_iterations=25,
            )
            attempt = host.solve_attempt()
            attempts.append(_attempt_summary(attempt, "PREHISTORY"))
            if not attempt.converged or not _mechanics_pass(attempt):
                prehistory_pass = False
                if not attempt.converged:
                    host.restore_after_failed_attempt(attempt)
                break
            host.commit(attempt)
            host.events.append(
                "OutputAcceptedState",
                solve_id=f"{case_id}-{run_id}",
                attempt_id=attempt.attempt_id,
                candidate_id=attempt.selected_packet.candidate_id,
                committed_state_hash=host.committed.full_hash,
                accepted_version=host.committed.accepted_version,
                reachable_from_accepted_output=True,
            )
            output.append_after_commit(
                state=host.committed,
                candidate_id=attempt.selected_packet.candidate_id,
                metrics=attempt.metrics,
                mesh_hashes=host.context.hashes,
                relation="EXACT_CURRENT",
            )

        source_state_hash = host.committed.full_hash
        source_state_ready = (
            prehistory_pass
            and host.committed.accepted_load == 0.08
            and host.committed.accepted_version == len(PREHISTORY_TARGETS)
        )
        if source_state_ready:
            diagnostic_python_start = len(host.events.records)
            diagnostic_c_start = len(read_c_ledger(observer_ledger))
            host.begin_attempt(
                target_load,
                f"{case_id}-{run_id}-DIAGNOSTIC",
                RELATION,
                maximum_iterations=25,
            )
            diagnostic_attempt = host.solve_attempt()
            attempts.append(_attempt_summary(diagnostic_attempt, "DIAGNOSTIC"))
            if diagnostic_attempt.converged and _mechanics_pass(diagnostic_attempt):
                host.commit(diagnostic_attempt)
                host.events.append(
                    "OutputAcceptedState",
                    solve_id=f"{case_id}-{run_id}",
                    attempt_id=diagnostic_attempt.attempt_id,
                    candidate_id=diagnostic_attempt.selected_packet.candidate_id,
                    committed_state_hash=host.committed.full_hash,
                    accepted_version=host.committed.accepted_version,
                    reachable_from_accepted_output=True,
                )
                output.append_after_commit(
                    state=host.committed,
                    candidate_id=diagnostic_attempt.selected_packet.candidate_id,
                    metrics=diagnostic_attempt.metrics,
                    mesh_hashes=host.context.hashes,
                    relation=RELATION,
                )
            elif not diagnostic_attempt.converged:
                host.restore_after_failed_attempt(diagnostic_attempt)
    finally:
        events = host.events.records
        final_state = host.committed
        mesh_hashes = dict(host.context.hashes)
        observer_metadata = host.observer_metadata
        host.close()

    c_events = read_c_ledger(observer_ledger)
    diagnostic_c_events = c_events[diagnostic_c_start:]
    diagnostic_python_events = events[diagnostic_python_start:]
    native = _classify_diagnostic_native_events(
        diagnostic_c_events, diagnostic_python_events
    )
    diagnostic_converged = bool(
        diagnostic_attempt is not None and diagnostic_attempt.converged
    )
    diagnostic_mechanics_pass = bool(
        diagnostic_attempt is not None and _mechanics_pass(diagnostic_attempt)
    )
    all_values_finite = bool(
        attempts
        and all(row["mechanics"]["all_values_finite"] for row in attempts)
        and np.isfinite(final_state.primary).all()
        and np.isfinite(final_state.gamma_p).all()
        and np.isfinite(final_state.alpha).all()
    )
    diagnostic_trigger = bool(
        diagnostic_converged
        and diagnostic_mechanics_pass
        and all_values_finite
        and native["structured_unselected_candidate_present"]
        and native["candidate_to_python_packet_correlation_complete"]
        and native["postcheck_flags_read_only"]
    )

    result = {
        "schema_version": "CMAME-P4D4-DIAGNOSTIC-RESULT-1.0",
        "design_version": "P4d.4",
        "implementation_dependency": "P4d.2",
        "host_version": "P4D-DOLFINX-PETSC-HOST-1.0",
        "case_id": case_id,
        "run_id": run_id,
        "evidence_status": "EXPLORATORY_NOT_FORMAL_EVIDENCE",
        "formal_execution": False,
        "formal_evidence": False,
        "execution_completed": diagnostic_attempt is not None,
        "source_load": 0.08,
        "target_load": target_load,
        "operator_relation": RELATION,
        "source_state_ready": source_state_ready,
        "source_state_hash": source_state_hash,
        "prehistory_pass": prehistory_pass,
        "accepted_loads": [
            row["accepted_load_factor"]
            for row in output.rows
            if row["source_event"] == "AcceptCommit"
        ],
        "diagnostic_snes_reason": (
            diagnostic_attempt.snes_reason if diagnostic_attempt is not None else None
        ),
        "diagnostic_positive_snes_reason": diagnostic_converged,
        "diagnostic_mechanics_gates_pass": diagnostic_mechanics_pass,
        "all_values_finite": all_values_finite,
        "committed_state_immutable_during_callbacks": all(
            row["committed_immutable"] for row in attempts
        ),
        "rejected_candidate_reachable": output.rejected_candidate_reachable(),
        "native_line_search": native,
        "diagnostic_trigger": diagnostic_trigger,
        "trigger_definition": (
            "positive SNES reason AND structured unselected candidate AND complete "
            "C/Python correlation AND mechanics/finite pass AND observer read-only"
        ),
        "attempts": attempts,
        "final_state_hash": final_state.full_hash,
        "final_physical_hash": final_state.physical_hash,
        "persistent_projection_hash": persistent.projection_hash,
        "environment_hash": environment_hash,
        "mesh_hashes": mesh_hashes,
        "observer_metadata": observer_metadata,
        "diagnostic_event_slices": {
            "python_start_index_zero_based": diagnostic_python_start,
            "c_start_index_zero_based": diagnostic_c_start,
            "python_event_count": len(diagnostic_python_events),
            "c_event_count": len(diagnostic_c_events),
        },
        "abaqus_used": False,
        "production_model_used": False,
        "heldout_executed": False,
    }

    write_json_new(result_directory / "environment.json", environment)
    _write_event_csv(result_directory / "event_ledger.csv", events)
    output.write(result_directory / "accepted_output")
    np.savez(
        result_directory / "final_state_arrays.npz",
        primary=final_state.primary,
        gamma_p=final_state.gamma_p,
        alpha=final_state.alpha,
    )
    write_json_new(result_directory / "case_result.json", _jsonable(result))
    files = sorted(
        path
        for path in result_directory.rglob("*")
        if path.is_file() and path.name != "case_manifest.json"
    )
    manifest = {
        "schema_version": "CMAME-P4D4-DIAGNOSTIC-CASE-MANIFEST-1.0",
        "case_id": case_id,
        "run_id": run_id,
        "evidence_status": "EXPLORATORY_NOT_FORMAL_EVIDENCE",
        "files": [
            {
                "path": path.relative_to(result_directory).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": file_sha256(path),
            }
            for path in files
        ],
        "manifest_self_hash_embedded": False,
    }
    write_json_new(result_directory / "case_manifest.json", manifest)
    return result
