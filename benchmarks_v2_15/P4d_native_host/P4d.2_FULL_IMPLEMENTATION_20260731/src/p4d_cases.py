from __future__ import annotations

import csv
import json
import pathlib
from typing import Any

import numpy as np

from p4d_canonical import canonical_hash, file_sha256
from p4d_config import CASE_CONTRACTS, OPERATOR_DRIFT_THRESHOLD
from p4d_driver import HistoryRun, operator_drift, run_history
from p4d_io import metrics_to_dict, read_checkpoint, write_json_new
from p4d_mesh import build_mesh_context
from p4d_observer import classify_native_line_search, read_c_ledger
from p4d_oracle_case import execute_constitutive_oracle
from p4d_reference import execute_reference_case
from p4d_version_guard import execute_version_guard_case


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
            writer.writerow({key: json.dumps(_jsonable(value), sort_keys=True) if isinstance(value, (dict, list, tuple)) else value for key, value in event.items()})


def _load_dependency(dependency_root: pathlib.Path, case_id: str, run_id: str) -> tuple[dict[str, Any], dict[str, np.ndarray], pathlib.Path]:
    directory = dependency_root / case_id / run_id
    result = json.loads((directory / "case_result.json").read_text(encoding="utf-8"))
    with np.load(directory / "final_state_arrays.npz", allow_pickle=False) as payload:
        arrays = {name: np.asarray(payload[name], dtype=np.float64) for name in payload.files}
    return result, arrays, directory


def _lifecycle_result(history: HistoryRun) -> dict[str, Any]:
    mechanics_pass = all(
        attempt.get("snes_reason", -1) < 0 or all(
            [
                attempt["mechanics"]["all_values_finite"],
                attempt["mechanics"]["alpha_bounded"],
                attempt["mechanics"]["alpha_nondecreasing"],
                attempt["mechanics"]["free_residual_relative"] <= 1.0e-10,
                attempt["mechanics"]["reaction_balance_relative"] <= 1.0e-10,
                attempt["mechanics"]["yield_consistency_relative"] <= 1.0e-9,
            ]
        )
        for attempt in history.attempts
    )
    return {
        "history_id": history.history_id,
        "prerequisite_status": history.prerequisite_status,
        "final_state_hash": history.final_state.full_hash,
        "final_physical_hash": history.final_state.physical_hash,
        "persistent_projection_hash": history.persistent.projection_hash,
        "accepted_loads": [row["accepted_load_factor"] for row in history.output_store.rows if row["source_event"] == "AcceptCommit"],
        "rejected_candidate_reachable": history.output_store.rejected_candidate_reachable(),
        "accepted_output_row_count": len(history.output_store.rows),
        "event_count": len(history.events),
        "attempts": history.attempts,
        "replay_packet": None if history.replay_packet is None else {
            key: value for key, value in history.replay_packet.items() if key not in {"tau", "tangent"}
        },
        "mechanics_gates_pass": mechanics_pass,
    }


def execute_case(
    *,
    root: pathlib.Path,
    case_id: str,
    run_id: str,
    result_directory: pathlib.Path,
    dependency_root: pathlib.Path | None,
    environment: dict[str, Any],
) -> dict[str, Any]:
    if case_id not in CASE_CONTRACTS:
        raise ValueError(f"unknown P4d case {case_id}")
    if not result_directory.exists() or any(result_directory.iterdir()):
        raise RuntimeError("formal case result directory must exist and be empty")
    contract = CASE_CONTRACTS[case_id]
    environment_hash = canonical_hash({key: value for key, value in environment.items() if key != "run_id"})
    events: list[dict[str, Any]] = []
    history: HistoryRun | None = None
    result: dict[str, Any]

    if case_id == "P4D-REF-01":
        result = execute_reference_case()
    elif case_id == "P4D-CONST-01":
        from p4d_fraction_oracle import derive_fraction_packets
        result = execute_constitutive_oracle(derive_fraction_packets())
    elif case_id == "P4D-VER-01":
        result = execute_version_guard_case()
    else:
        observer_library = None
        observer_ledger = None
        initial_state = None
        checkpoint_directory = None
        if case_id == "P4D-SAFE-LS-01":
            observer_library = root / "build" / "libp4d_observer.so"
            observer_ledger = result_directory / "c_observer_ledger.jsonl"
        if case_id == "P4D-SAFE-RS-01":
            if dependency_root is None:
                raise RuntimeError("restart case requires the direct-case dependency root")
            _baseline, _arrays, direct_directory = _load_dependency(dependency_root, "P4D-SAFE-DIR-01", run_id)
            context = build_mesh_context()
            checkpoint_manifest = json.loads((direct_directory / "checkpoint_012" / "checkpoint_manifest.json").read_text(encoding="utf-8"))
            initial_state, _manifest = read_checkpoint(
                direct_directory / "checkpoint_012",
                context.hashes,
                checkpoint_manifest["environment_hash"],
            )
        if case_id == "P4D-SAFE-DIR-01":
            checkpoint_directory = result_directory / "checkpoint_012"
        history_name = {
            "P4D-SAFE-DIR-01": "H_DIRECT",
            "P4D-SAFE-LS-01": "H_NATIVE_LINESEARCH",
            "P4D-SAFE-RT-01": "H_DRIVER_RETRY",
            "P4D-SAFE-RS-01": "H_RESTART",
            "P4D-NC-CACHE-01": "H_CACHE_NEGATIVE",
            "P4D-NC-OUTPUT-01": "H_OUTPUT_NEGATIVE",
        }[case_id]
        history = run_history(
            history_name,
            run_id,
            initial_state=initial_state,
            environment_hash=environment_hash,
            checkpoint_directory=checkpoint_directory,
            observer_library=observer_library,
            observer_ledger=observer_ledger,
        )
        events = history.events
        result = _lifecycle_result(history)
        if case_id == "P4D-SAFE-DIR-01":
            passed = history.prerequisite_status == "PASS" and result["mechanics_gates_pass"] and not result["rejected_candidate_reachable"]
            result["primary_verdict"] = contract.expected_primary_verdict if passed else "SAFE_DIRECT_FAIL"
            result["pass_flag"] = passed
        else:
            if dependency_root is None:
                raise RuntimeError(f"{case_id} requires direct-case dependency evidence")
            direct_result, direct_arrays, direct_directory = _load_dependency(dependency_root, "P4D-SAFE-DIR-01", run_id)
            final_equal = bool(
                np.allclose(history.final_state.primary, direct_arrays["primary"], rtol=1.0e-10, atol=1.0e-10)
                and np.allclose(history.final_state.gamma_p, direct_arrays["gamma_p"], rtol=1.0e-10, atol=1.0e-10)
                and np.allclose(history.final_state.alpha, direct_arrays["alpha"], rtol=1.0e-10, atol=1.0e-10)
            )
            result["direct_final_field_parity"] = final_equal
            if case_id == "P4D-SAFE-LS-01":
                c_classification = classify_native_line_search(read_c_ledger(observer_ledger), events)
                result["native_line_search"] = c_classification
                passed = bool(
                    history.prerequisite_status == "PASS"
                    and final_equal
                    and result["mechanics_gates_pass"]
                    and c_classification["structured_unselected_candidate_present"]
                    and c_classification["candidate_to_python_packet_correlation_present"]
                    and c_classification["postcheck_flags_read_only"]
                )
            elif case_id == "P4D-SAFE-RS-01":
                passed = bool(history.prerequisite_status == "PASS" and final_equal and result["mechanics_gates_pass"])
            else:
                replay_path = direct_directory / "replay_packet_arrays.npz"
                with np.load(replay_path, allow_pickle=False) as payload:
                    direct_replay = {
                        "tau": np.asarray(payload["tau"], dtype=np.float64),
                        "tangent": np.asarray(payload["tangent"], dtype=np.float64),
                        **direct_result["replay_packet"],
                    }
                if history.replay_packet is None:
                    raise RuntimeError("retry-dependent case has no replay packet")
                drift = operator_drift(direct_replay, history.replay_packet)
                result["operator_replay_comparison"] = drift
                if case_id == "P4D-SAFE-RT-01":
                    passed = bool(
                        history.prerequisite_status == "PASS"
                        and final_equal
                        and drift["declared_primary_equal"]
                        and drift["declared_committed_equal"]
                        and drift["residual_drift_norm"] <= 1.0e-10
                        and drift["tangent_drift_norm"] <= 1.0e-10
                    )
                elif case_id == "P4D-NC-CACHE-01":
                    passed = bool(
                        history.prerequisite_status == "PASS"
                        and history.persistent.mutation_count == 1
                        and drift["declared_primary_equal"]
                        and drift["declared_committed_equal"]
                        and drift["residual_drift_finite"]
                        and drift["tangent_drift_finite"]
                        and max(drift["residual_drift_norm"], drift["tangent_drift_norm"]) > OPERATOR_DRIFT_THRESHOLD
                    )
                else:
                    passed = bool(history.prerequisite_status == "PASS" and result["rejected_candidate_reachable"])
            result["primary_verdict"] = contract.expected_primary_verdict if passed else f"{case_id}_CONTRACT_FAIL"
            result["pass_flag"] = passed

    result.update({
        "design_version": "P4d.0",
        "implementation_version": "P4d.2",
        "host_version": "P4D-DOLFINX-PETSC-HOST-1.0",
        "case_id": case_id,
        "run_id": run_id,
        "expected_primary_verdict": contract.expected_primary_verdict,
        "environment_hash": environment_hash,
        "formal_execution": True,
        "abaqus_used": False,
        "production_model_used": False,
    })
    write_json_new(result_directory / "environment.json", environment)
    if history is not None:
        _write_event_csv(result_directory / "event_ledger.csv", events)
        history.output_store.write(result_directory / "accepted_output")
        np.savez(
            result_directory / "final_state_arrays.npz",
            primary=history.final_state.primary,
            gamma_p=history.final_state.gamma_p,
            alpha=history.final_state.alpha,
        )
        if history.replay_packet is not None:
            np.savez(
                result_directory / "replay_packet_arrays.npz",
                tau=history.replay_packet["tau"],
                tangent=history.replay_packet["tangent"],
            )
            result["replay_packet"] = {
                key: value for key, value in history.replay_packet.items() if key not in {"tau", "tangent"}
            }
    else:
        np.savez(result_directory / "final_state_arrays.npz", primary=np.array([]), gamma_p=np.array([]), alpha=np.array([]))
    write_json_new(result_directory / "case_result.json", _jsonable(result))
    files = sorted(path for path in result_directory.rglob("*") if path.is_file())
    manifest = {
        "case_id": case_id,
        "run_id": run_id,
        "files": [
            {"path": path.relative_to(result_directory).as_posix(), "bytes": path.stat().st_size, "sha256": file_sha256(path)}
            for path in files
        ],
        "manifest_self_hash_embedded": False,
    }
    write_json_new(result_directory / "case_manifest.json", manifest)
    return result
