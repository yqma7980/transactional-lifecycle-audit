from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
import random
import statistics
from typing import Any


BOOTSTRAP_SEED = 20260811
BOOTSTRAP_RESAMPLES = 10_000


def write_json_new(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def write_csv_new(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError("cannot write empty CSV")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(path)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def load_matrix(root: Path) -> list[dict[str, str]]:
    with (root / "frozen_inputs" / "P5D_performance_matrix.csv").open(
        "r", encoding="utf-8", newline=""
    ) as stream:
        return list(csv.DictReader(stream))


def load_run(root: Path, phase: str, cell_id: str, run_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    run_root = root / "results" / phase / cell_id / run_id
    return (
        json.loads((run_root / "case_result.json").read_text(encoding="utf-8")),
        json.loads((run_root / "process_envelope.json").read_text(encoding="utf-8")),
    )


def group_rows(matrix: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    groups: dict[str, list[dict[str, str]]] = {}
    for row in matrix:
        groups.setdefault(row["workload_id"], []).append(row)
    return groups


def semantic_gate(records: list[dict[str, Any]]) -> dict[str, Any]:
    outputs = {record["result"]["output_fingerprint"] for record in records}
    trajectories = {record["result"]["trajectory_fingerprint"] for record in records}
    production_counts = {
        json.dumps(record["result"]["production_counts"], sort_keys=True)
        for record in records
    }
    environments = {record["environment"]["semantic_fingerprint"] for record in records}
    modes = {record["instrumentation_mode"] for record in records}
    audit_contract = all(
        (
            record["instrumentation_mode"] == "M0_AUDIT_OFF"
            and record["result"]["audit"]["performed"] is False
        )
        or (
            record["instrumentation_mode"] in {"M3_GENERIC_REPLAY", "M6_FULL_TLA"}
            and record["result"]["audit"]["performed"] is True
            and record["result"]["audit"]["generic_replay_equal"] is True
            and sum(record["result"]["audit_counts"].values()) > 0
        )
        for record in records
    )
    return {
        "accepted_output_equivalence": len(outputs) == 1,
        "production_trajectory_equivalence": len(trajectories) == 1,
        "production_work_equivalence": len(production_counts) == 1,
        "environment_identity": len(environments) == 1,
        "audit_work_separated": audit_contract,
        "finite_and_schema": all(record.get("pass_flag") is True for record in records),
        "all_modes_present": modes == {"M0_AUDIT_OFF", "M3_GENERIC_REPLAY", "M6_FULL_TLA"},
    }


def qualification(root: Path) -> dict[str, Any]:
    matrix = load_matrix(root)
    records_by_cell: dict[str, dict[str, Any]] = {}
    for row in matrix:
        result, envelope = load_run(root, "qualification_v3", row["cell_id"], "qualification_01")
        if envelope["exit_code"] != 0:
            raise RuntimeError(f"qualification process failed: {row['cell_id']}")
        records_by_cell[row["cell_id"]] = result
    groups = []
    for workload_id, rows in sorted(group_rows(matrix).items()):
        records = [records_by_cell[row["cell_id"]] for row in rows]
        gates = semantic_gate(records)
        groups.append({
            "workload_id": workload_id,
            "subject_id": rows[0]["subject_id"],
            "gates": gates,
            "pass_flag": all(gates.values()),
            "output_fingerprint": records[0]["result"]["output_fingerprint"],
            "trajectory_fingerprint": records[0]["result"]["trajectory_fingerprint"],
            "production_counts": records[0]["result"]["production_counts"],
        })
    passed = all(group["pass_flag"] for group in groups)
    payload = {
        "protocol_id": "JSS-P5D-PERFORMANCE-1.0",
        "status": "PASS_P5D_EQUIVALENCE_GATES" if passed else "FAIL_P5D_EQUIVALENCE_GATES",
        "qualification_processes": len(matrix),
        "subject_workload_triplets": len(groups),
        "groups": groups,
        "formal_execution_authorized_by_result": passed,
        "historical_aeds_timing_used": False,
    }
    write_json_new(root / "qualification_v3" / "P5D_equivalence_gate_results_v3.json", payload)
    return payload


def quantile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def bootstrap_ci(values: list[float], *, salt: str) -> tuple[float, float]:
    seed = BOOTSTRAP_SEED + sum(ord(character) for character in salt)
    rng = random.Random(seed)
    medians = []
    n = len(values)
    for _ in range(BOOTSTRAP_RESAMPLES):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        medians.append(statistics.median(sample))
    return quantile(medians, 0.025), quantile(medians, 0.975)


def metric_summary(values: list[float], *, salt: str) -> dict[str, Any]:
    if len(values) != 10 or not all(math.isfinite(value) for value in values):
        raise RuntimeError(f"formal metric requires ten finite values: {salt}")
    low, high = bootstrap_ci(values, salt=salt)
    q1 = quantile(values, 0.25)
    q3 = quantile(values, 0.75)
    return {
        "values": values,
        "median": statistics.median(values),
        "q1": q1,
        "q3": q3,
        "iqr": q3 - q1,
        "bootstrap_95_low": low,
        "bootstrap_95_high": high,
    }


def formal(root: Path) -> dict[str, Any]:
    matrix = load_matrix(root)
    raw_rows: list[dict[str, Any]] = []
    records_by_cell: dict[str, list[dict[str, Any]]] = {}
    for row in matrix:
        records: list[dict[str, Any]] = []
        for ordinal in range(1, 11):
            run_id = f"run_{ordinal:02d}"
            result, envelope = load_run(root, "formal", row["cell_id"], run_id)
            if envelope["exit_code"] != 0 or result.get("pass_flag") is not True:
                raise RuntimeError(f"formal process failed: {row['cell_id']} {run_id}")
            record = result | {"external_wall_time_seconds": envelope["external_wall_time_seconds"]}
            records.append(record)
            raw_rows.append({
                "cell_id": row["cell_id"],
                "subject_id": row["subject_id"],
                "workload_id": row["workload_id"],
                "mode": row["instrumentation_mode"],
                "run_id": run_id,
                "external_wall_seconds": envelope["external_wall_time_seconds"],
                "internal_wall_seconds": result["internal_wall_time_seconds"],
                "cpu_seconds": result["cpu_time_seconds"],
                "peak_rss_bytes": result["peak_rss_bytes"],
                "initialization_seconds": result["initialization_seconds"],
                "production_seconds": result["result"]["production_seconds"],
                "audit_seconds": result["result"]["audit_seconds"],
                "serialization_hashing_seconds": result["result"]["serialization_hashing_seconds"],
                "audit_bytes": result["result"]["audit_bytes"],
                "event_ledger_bytes": result["result"]["event_ledger_bytes"],
                "production_residual": result["result"]["production_counts"]["residual"],
                "production_tangent": result["result"]["production_counts"]["tangent"],
                "production_trial": result["result"]["production_counts"]["trial"],
                "audit_residual": result["result"]["audit_counts"]["residual"],
                "audit_tangent": result["result"]["audit_counts"]["tangent"],
                "audit_trial": result["result"]["audit_counts"]["trial"],
                "output_fingerprint": result["result"]["output_fingerprint"],
                "trajectory_fingerprint": result["result"]["trajectory_fingerprint"],
                "pass_flag": True,
            })
        records_by_cell[row["cell_id"]] = records
    # Equivalence is checked across all 30 mode repetitions in each workload.
    workload_gates = []
    for workload_id, rows in sorted(group_rows(matrix).items()):
        records = [record for row in rows for record in records_by_cell[row["cell_id"]]]
        gates = semantic_gate(records)
        workload_gates.append({
            "workload_id": workload_id,
            "gates": gates,
            "pass_flag": all(gates.values()),
        })
    if not all(item["pass_flag"] for item in workload_gates):
        raise RuntimeError("formal P5D equivalence gate failed")

    metrics = {
        "external_wall_seconds": lambda record: record["external_wall_time_seconds"],
        "internal_wall_seconds": lambda record: record["internal_wall_time_seconds"],
        "cpu_seconds": lambda record: record["cpu_time_seconds"],
        "peak_rss_bytes": lambda record: float(record["peak_rss_bytes"]),
        "initialization_seconds": lambda record: record["initialization_seconds"],
        "production_seconds": lambda record: record["result"]["production_seconds"],
        "audit_seconds": lambda record: record["result"]["audit_seconds"],
        "serialization_hashing_seconds": lambda record: record["result"]["serialization_hashing_seconds"],
        "audit_bytes": lambda record: float(record["result"]["audit_bytes"]),
        "event_ledger_bytes": lambda record: float(record["result"]["event_ledger_bytes"]),
    }
    cell_summaries = []
    cell_by_id: dict[str, dict[str, Any]] = {}
    for row in matrix:
        records = records_by_cell[row["cell_id"]]
        summary = {
            "cell_id": row["cell_id"],
            "subject_id": row["subject_id"],
            "workload_id": row["workload_id"],
            "mode": row["instrumentation_mode"],
            "formal_repetitions": len(records),
            "metrics": {
                name: metric_summary([float(extractor(record)) for record in records], salt=row["cell_id"] + name)
                for name, extractor in metrics.items()
            },
            "output_fingerprint": records[0]["result"]["output_fingerprint"],
            "trajectory_fingerprint": records[0]["result"]["trajectory_fingerprint"],
            "production_counts": records[0]["result"]["production_counts"],
            "audit_counts": records[0]["result"]["audit_counts"],
        }
        cell_summaries.append(summary)
        cell_by_id[row["cell_id"]] = summary

    overhead_rows = []
    for workload_id, rows in sorted(group_rows(matrix).items()):
        baseline_row = next(row for row in rows if row["instrumentation_mode"] == "M0_AUDIT_OFF")
        baseline = cell_by_id[baseline_row["cell_id"]]
        for row in sorted(rows, key=lambda item: item["instrumentation_mode"]):
            summary = cell_by_id[row["cell_id"]]
            wall_base = baseline["metrics"]["external_wall_seconds"]["median"]
            internal_base = baseline["metrics"]["internal_wall_seconds"]["median"]
            cpu_base = baseline["metrics"]["cpu_seconds"]["median"]
            rss_base = baseline["metrics"]["peak_rss_bytes"]["median"]
            overhead_rows.append({
                "subject_id": row["subject_id"],
                "workload_id": workload_id,
                "mode": row["instrumentation_mode"],
                "external_wall_median_seconds": summary["metrics"]["external_wall_seconds"]["median"],
                "external_wall_overhead_percent": 100.0 * (summary["metrics"]["external_wall_seconds"]["median"] / wall_base - 1.0),
                "internal_wall_median_seconds": summary["metrics"]["internal_wall_seconds"]["median"],
                "internal_wall_overhead_percent": 100.0 * (summary["metrics"]["internal_wall_seconds"]["median"] / internal_base - 1.0),
                "cpu_median_seconds": summary["metrics"]["cpu_seconds"]["median"],
                "cpu_overhead_percent": 100.0 * (summary["metrics"]["cpu_seconds"]["median"] / cpu_base - 1.0),
                "peak_rss_median_bytes": summary["metrics"]["peak_rss_bytes"]["median"],
                "peak_rss_overhead_percent": 100.0 * (summary["metrics"]["peak_rss_bytes"]["median"] / rss_base - 1.0),
                "audit_bytes_median": summary["metrics"]["audit_bytes"]["median"],
                "event_ledger_bytes_median": summary["metrics"]["event_ledger_bytes"]["median"],
            })

    write_csv_new(root / "final" / "P5D_formal_run_source.csv", raw_rows)
    write_csv_new(root / "final" / "P5D_overhead_source.csv", overhead_rows)
    payload = {
        "evidence_status": "OBSERVED-JSS-P5D",
        "status": "PASS_P5D_FORMAL_PERFORMANCE_STUDY",
        "subjects": 3,
        "workloads": 6,
        "cells": 18,
        "warmup_processes": 36,
        "formal_fresh_processes": 180,
        "all_slow_runs_retained": True,
        "all_equivalence_gates_passed": True,
        "workload_gates": workload_gates,
        "cell_summaries": cell_summaries,
        "overhead_rows": overhead_rows,
        "bootstrap_resamples": BOOTSTRAP_RESAMPLES,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "historical_aeds_timing_used": False,
        "abaqus_used": False,
        "production_model_used": False,
        "interpretation_boundary": "three subjects, two sizes, one machine, single process, single thread",
    }
    write_json_new(root / "final" / "P5D_final_summary.json", payload)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("qualification", "formal"), required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parent
    payload = qualification(root) if args.phase == "qualification" else formal(root)
    print(payload["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
