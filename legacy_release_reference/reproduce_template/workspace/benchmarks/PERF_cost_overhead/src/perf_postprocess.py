"""Frozen verification and statistics for PERF-D1 formal evidence."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from benchmarks.L6_external_host.src.l6_state import canonical_json


EXPECTED_RUN_FILES = {
    "accepted_output.json",
    "performance_result.json",
    "case_manifest.json",
}
THREAD_ENV = {
    "OMP_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "PYTHONHASHSEED": "0",
    "PYTHONDONTWRITEBYTECODE": "1",
}
METRIC_FIELDS = (
    "wall_time_ns",
    "cpu_time_ns",
    "peak_working_set_bytes",
    "python_peak_bytes",
    "accepted_output_bytes",
    "accepted_steps_or_solves",
    "kernel_step_evaluations",
    "residual_evaluations",
    "tangent_evaluations",
    "accepted_callbacks",
    "nonlinear_iteration_proxy",
    "candidate_count",
    "commit_count",
    "audit_accepted_callback_count",
    "event_count",
    "fingerprint_count",
    "serialized_audit_bytes",
    "serialization_time_ns",
    "hashing_time_ns",
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def quantile_linear(values: Iterable[float], probability: float) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        raise ValueError("quantile requires values")
    if not 0.0 <= probability <= 1.0:
        raise ValueError("probability outside [0, 1]")
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def bootstrap_median_ci(
    values: Iterable[float],
    rng: np.random.Generator,
    *,
    resamples: int = 10_000,
) -> tuple[float, float]:
    data = np.asarray([float(value) for value in values], dtype=np.float64)
    if data.size == 0:
        raise ValueError("bootstrap requires values")
    indices = rng.integers(0, data.size, size=(resamples, data.size))
    medians = np.median(data[indices], axis=1)
    low, high = np.quantile(medians, [0.025, 0.975], method="linear")
    return float(low), float(high)


def distribution_stats(
    values: Iterable[float],
    rng: np.random.Generator,
) -> dict[str, float]:
    data = [float(value) for value in values]
    q1 = quantile_linear(data, 0.25)
    median = quantile_linear(data, 0.5)
    q3 = quantile_linear(data, 0.75)
    ci_low, ci_high = bootstrap_median_ci(data, rng)
    return {
        "median": median,
        "q1": q1,
        "q3": q3,
        "iqr": q3 - q1,
        "median_ci95_low": ci_low,
        "median_ci95_high": ci_high,
    }


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"no rows for {path}")
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def load_matrix(root: Path) -> list[dict[str, str]]:
    with (root / "PERF_D0_case_matrix.csv").open(
        "r", encoding="utf-8", newline=""
    ) as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != 45 or len({row["case_id"] for row in rows}) != 45:
        raise RuntimeError("frozen matrix is not 45 unique cells")
    return sorted(rows, key=lambda row: row["case_id"])


def _finite(value: Any, limit: float = 1.0e100) -> bool:
    if value is None or isinstance(value, bool):
        return True
    if isinstance(value, (int, float)):
        return math.isfinite(float(value)) and abs(float(value)) <= limit
    if isinstance(value, dict):
        return all(_finite(item, limit) for item in value.values())
    if isinstance(value, (list, tuple)):
        return all(_finite(item, limit) for item in value)
    return True


def flatten_result(result: dict[str, Any]) -> dict[str, Any]:
    counts = result["counts"]
    audit = result["audit"]
    return {
        "wall_time_ns": result["wall_time_ns"],
        "cpu_time_ns": result["cpu_time_ns"],
        "peak_working_set_bytes": result["peak_working_set_bytes"],
        "python_peak_bytes": result["python_peak_bytes"],
        "accepted_output_bytes": result["accepted_output_bytes"],
        "accepted_steps_or_solves": counts["accepted_steps_or_solves"],
        "kernel_step_evaluations": counts["kernel_step_evaluations"],
        "residual_evaluations": counts["residual_evaluations"],
        "tangent_evaluations": counts["tangent_evaluations"],
        "accepted_callbacks": counts["accepted_callbacks"],
        "nonlinear_iteration_proxy": counts["nonlinear_iteration_proxy"],
        "candidate_count": audit["candidate_count"],
        "commit_count": audit["commit_count"],
        "audit_accepted_callback_count": audit["accepted_callback_count"],
        "event_count": audit["event_count"],
        "fingerprint_count": audit["fingerprint_count"],
        "serialized_audit_bytes": audit["serialized_audit_bytes"],
        "serialization_time_ns": audit["serialization_time_ns"],
        "hashing_time_ns": audit["hashing_time_ns"],
    }


def verify_run(
    result_root: Path,
    row: dict[str, str],
    run_id: str,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, str]]]:
    run_dir = result_root / row["case_id"] / run_id
    names = {path.name for path in run_dir.iterdir() if path.is_file()}
    if names != EXPECTED_RUN_FILES:
        raise RuntimeError(f"unexpected files in {run_dir}: {sorted(names)}")
    manifest_path = run_dir / "case_manifest.json"
    manifest = _read_json(manifest_path)
    file_hashes: list[dict[str, str]] = []
    for name in sorted(EXPECTED_RUN_FILES):
        path = run_dir / name
        digest = sha256_file(path)
        file_hashes.append(
            {"path": path.as_posix(), "sha256": digest}
        )
        if name != "case_manifest.json" and manifest["outputs"].get(name) != digest:
            raise RuntimeError(f"manifest mismatch: {path}")
    result = _read_json(run_dir / "performance_result.json")
    accepted = _read_json(run_dir / "accepted_output.json")
    if not (
        result["pass_flag"]
        and result["classification"] == "PASS_OUTPUT_EQUIVALENT_TIMING_RECORDED"
        and result["phase"] == "formal"
        and result["case_id"] == row["case_id"]
        and result["run_id"] == run_id
        and result["family"] == row["family"]
        and result["size"] == row["size"]
        and result["config_id"] == row["config_id"]
    ):
        raise RuntimeError(f"result identity or classification mismatch: {run_dir}")
    if result["thread_environment"] != THREAD_ENV:
        raise RuntimeError(f"thread contract mismatch: {run_dir}")
    if result["affinity"]["process_mask"] != 1:
        raise RuntimeError(f"affinity mismatch: {run_dir}")
    if result["result_file_io_inside_timed_region"]:
        raise RuntimeError(f"file I/O entered timed region: {run_dir}")
    if not result["all_values_finite"] or not _finite(result):
        raise RuntimeError(f"non-finite result: {run_dir}")
    output_payload = accepted["accepted_output"]
    fingerprint = hashlib.sha256(
        canonical_json(output_payload).encode("utf-8")
    ).hexdigest()
    if not (
        fingerprint == result["accepted_output_fingerprint"]
        == accepted["accepted_output_fingerprint"]
    ):
        raise RuntimeError(f"accepted-output fingerprint mismatch: {run_dir}")
    return result, output_payload, file_hashes


def _verify_receipts(
    result_root: Path,
    expected_case_ids: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, str]]]:
    paths = [
        result_root / "warmup_receipts.json",
        result_root / "formal_execution_receipts.json",
    ]
    hashes = [{"path": path.as_posix(), "sha256": sha256_file(path)} for path in paths]
    warmups = _read_json(paths[0])
    formal = _read_json(paths[1])
    if warmups["count"] != 90 or len(warmups["receipts"]) != 90 or not warmups["all_passed"]:
        raise RuntimeError("warm-up receipt gate failed")
    if formal["count"] != 450 or len(formal["receipts"]) != 450 or not formal["all_passed"]:
        raise RuntimeError("formal receipt gate failed")
    expected_runs = {
        (case_id, f"run_{repetition:02d}")
        for case_id in expected_case_ids
        for repetition in range(1, 11)
    }
    observed_runs = {(item["case_id"], item["run_id"]) for item in formal["receipts"]}
    if observed_runs != expected_runs or len(observed_runs) != 450:
        raise RuntimeError("formal receipt identities are incomplete")
    if any(item["case_id"] not in expected_case_ids for item in warmups["receipts"]):
        raise RuntimeError("unknown warm-up case")
    return warmups["receipts"], formal["receipts"], hashes


def build_evidence(root: Path) -> dict[str, Any]:
    rows = load_matrix(root)
    result_root = root / "results" / "PERF_D1_cost_overhead"
    final_root = result_root / "final"
    if final_root.exists():
        raise FileExistsError(final_root)
    _, formal_receipts, raw_hashes = _verify_receipts(
        result_root, {row["case_id"] for row in rows}
    )
    receipt_lookup = {
        (item["case_id"], item["run_id"]): item for item in formal_receipts
    }
    raw_rows: list[dict[str, Any]] = []
    output_by_group: dict[tuple[str, str], set[str]] = {}
    canonical_output_by_group: dict[tuple[str, str], set[str]] = {}
    for row in rows:
        for repetition in range(1, 11):
            run_id = f"run_{repetition:02d}"
            result, output, hashes = verify_run(result_root, row, run_id)
            raw_hashes.extend(hashes)
            receipt = receipt_lookup[(row["case_id"], run_id)]
            if not (
                receipt["pass_flag"]
                and receipt["accepted_output_fingerprint"]
                == result["accepted_output_fingerprint"]
            ):
                raise RuntimeError(f"receipt mismatch: {row['case_id']} {run_id}")
            group = (row["family"], row["size"])
            output_by_group.setdefault(group, set()).add(
                result["accepted_output_fingerprint"]
            )
            canonical_output_by_group.setdefault(group, set()).add(
                canonical_json(output)
            )
            flat = flatten_result(result)
            raw_rows.append(
                {
                    "case_id": row["case_id"],
                    "run_id": run_id,
                    "family": row["family"],
                    "size": row["size"],
                    "config_id": row["config_id"],
                    "config_name": row["config_name"],
                    "accepted_output_fingerprint": result[
                        "accepted_output_fingerprint"
                    ],
                    "pass_flag": result["pass_flag"],
                    **flat,
                }
            )
    if len(raw_rows) != 450:
        raise RuntimeError("formal raw row count is not 450")
    if any(len(values) != 1 for values in output_by_group.values()):
        raise RuntimeError("cross-configuration output fingerprints differ")
    if any(len(values) != 1 for values in canonical_output_by_group.values()):
        raise RuntimeError("cross-configuration accepted outputs differ")

    rng = np.random.default_rng(20260722)
    summary_rows: list[dict[str, Any]] = []
    grouped_raw = {
        row["case_id"]: [item for item in raw_rows if item["case_id"] == row["case_id"]]
        for row in rows
    }
    for row in rows:
        values = grouped_raw[row["case_id"]]
        if len(values) != 10:
            raise RuntimeError(f"cell does not have 10 runs: {row['case_id']}")
        summary: dict[str, Any] = {
            "case_id": row["case_id"],
            "family": row["family"],
            "size": row["size"],
            "config_id": row["config_id"],
            "config_name": row["config_name"],
            "formal_process_count": 10,
            "all_output_fingerprints_equal": len(
                {item["accepted_output_fingerprint"] for item in values}
            ) == 1,
        }
        for metric in METRIC_FIELDS:
            stats = distribution_stats([item[metric] for item in values], rng)
            for name, value in stats.items():
                summary[f"{metric}_{name}"] = value
        summary_rows.append(summary)

    baselines = {
        (row["family"], row["size"]): row
        for row in summary_rows
        if row["config_id"] == "C0"
    }
    overhead_rows: list[dict[str, Any]] = []
    for row in summary_rows:
        baseline = baselines[(row["family"], row["size"])]
        wall_ratio = row["wall_time_ns_median"] / baseline["wall_time_ns_median"]
        cpu_ratio = row["cpu_time_ns_median"] / baseline["cpu_time_ns_median"]
        overhead_rows.append(
            {
                "case_id": row["case_id"],
                "family": row["family"],
                "size": row["size"],
                "config_id": row["config_id"],
                "config_name": row["config_name"],
                "baseline_case_id": baseline["case_id"],
                "wall_median_ratio_to_c0": wall_ratio,
                "wall_median_overhead_fraction": wall_ratio - 1.0,
                "cpu_median_ratio_to_c0": cpu_ratio,
                "cpu_median_overhead_fraction": cpu_ratio - 1.0,
            }
        )

    final_summary = {
        "schema_version": "PERF-D1-FINAL-SUMMARY-1.0",
        "design_version": "PERF-D1.0",
        "evidence_status": "OBSERVED-PERFORMANCE-D1",
        "classification": "PASS_OUTPUT_EQUIVALENT_TIMING_RECORDED",
        "formal_cell_count": 45,
        "warmup_process_count": 90,
        "formal_process_count": 450,
        "formal_processes_per_cell": 10,
        "threads_per_process": 1,
        "affinity_mask": 1,
        "all_values_finite": True,
        "all_output_equivalence_gates_passed": True,
        "all_manifest_hashes_match": True,
        "no_runs_deleted": True,
        "statistics": {
            "median_q1_q3_iqr": True,
            "bootstrap_median_ci95": True,
            "bootstrap_resamples": 10_000,
            "bootstrap_seed": 20260722,
            "quartile_method": "linear",
            "case_order": "lexicographic_case_id",
            "metric_order": list(METRIC_FIELDS),
        },
        "claim_boundary": "machine_specific_python_overhead_for_frozen_workloads_only",
        "performance_improvement_required": False,
        "abaqus_used": False,
        "comsol_used": False,
        "production_model_used": False,
    }

    final_root.mkdir(parents=True)
    run_path = final_root / "performance_run_source.csv"
    cell_path = final_root / "performance_cell_summary_source.csv"
    overhead_path = final_root / "performance_overhead_source.csv"
    summary_path = final_root / "performance_final_summary.json"
    _write_csv(run_path, raw_rows)
    _write_csv(cell_path, summary_rows)
    _write_csv(overhead_path, overhead_rows)
    _write_json(summary_path, final_summary)

    table_lines = [
        "| Family | Size | Config | Wall median (ms) | Wall overhead vs C0 | CPU median (ms) |",
        "|---|---:|---|---:|---:|---:|",
    ]
    for summary, overhead in zip(summary_rows, overhead_rows):
        table_lines.append(
            "| {family} | {size} | {config_id} | {wall:.6f} | {over:+.3%} | {cpu:.6f} |".format(
                family=summary["family"],
                size=summary["size"],
                config_id=summary["config_id"],
                wall=summary["wall_time_ns_median"] / 1.0e6,
                over=overhead["wall_median_overhead_fraction"],
                cpu=summary["cpu_time_ns_median"] / 1.0e6,
            )
        )
    report = "\n".join(
        [
            "# PERF-D1 controlled cost result",
            "",
            "Classification: **PASS_OUTPUT_EQUIVALENT_TIMING_RECORDED**",
            "",
            "All 45 cells completed two unmeasured warm-ups and ten independent measured single-process, single-thread runs. All 450 accepted numerical outputs were finite, and C0-C4 were exactly identical within every frozen family-size group. No measured run was deleted or excluded.",
            "",
            "The table reports machine-specific Python timings. Positive and negative overhead observations are retained. This evidence does not establish Abaqus or production-uel cost, parallel scaling, cross-machine performance, or universal acceleration.",
            "",
            *table_lines,
            "",
        ]
    )
    report_path = final_root / "performance_result_report.md"
    report_path.write_text(report, encoding="utf-8")

    source_files = [run_path, cell_path, overhead_path, summary_path, report_path]
    manifest = {
        "schema_version": "PERF-D1-EXECUTION-MANIFEST-1.0",
        "design_version": "PERF-D1.0",
        "raw_file_count": len(raw_hashes),
        "raw_files": sorted(raw_hashes, key=lambda item: item["path"]),
        "source_files": [
            {
                "path": path.as_posix(),
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
                "data_rows": (
                    sum(1 for _ in path.open("r", encoding="utf-8")) - 1
                    if path.suffix == ".csv"
                    else None
                ),
            }
            for path in source_files
        ],
        "preflight_files": [
            {
                "path": path.as_posix(),
                "sha256": sha256_file(path),
            }
            for path in sorted(
                (root / "preflight" / "PERF_D1_all_cells").rglob("*")
            )
            if path.is_file()
        ],
        "no_run_deletion": True,
        "no_abaqus_execution": True,
        "no_comsol_execution": True,
        "manifest_self_hash_embedded": False,
    }
    _write_json(final_root / "performance_execution_manifest.json", manifest)
    return final_summary


__all__ = [
    "METRIC_FIELDS",
    "bootstrap_median_ci",
    "build_evidence",
    "distribution_stats",
    "quantile_linear",
]
