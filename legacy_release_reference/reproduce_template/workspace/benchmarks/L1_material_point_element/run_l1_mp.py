"""Run the frozen L1-MP matrix and write deterministic candidate artifacts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import tracemalloc
from typing import Any

from src.l1_cases import CASE_RESULT_COLUMNS, CHECKPOINT_COLUMNS, MPBenchmark
from src.l1_design_validation import sha256_file, validate_design, validate_summary_document


ROOT = Path(__file__).resolve().parent


def write_json(path: Path, document: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(document, ensure_ascii=True, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def write_csv(path: Path, columns: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def implementation_hash() -> str:
    digest = hashlib.sha256()
    paths = sorted((ROOT / "src").glob("*.py")) + [ROOT / "run_l1_mp.py"]
    for path in paths:
        digest.update(path.relative_to(ROOT).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def scan_abaqus_processes() -> list[str]:
    targets = {"standard.exe", "pre.exe", "smasimutility.exe", "abqcaek.exe"}
    if os.name != "nt":
        return []
    completed = subprocess.run(
        ["tasklist", "/FO", "CSV", "/NH"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    found: list[str] = []
    for row in csv.reader(completed.stdout.splitlines()):
        if row and row[0].lower() in targets:
            found.append(row[0])
    return sorted(found)


def build_gate_families(
    case_results: list[dict[str, str]],
    design_validation: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    failed = [row for row in case_results if row["passed"] != "true"]
    safe_failed = [
        row
        for row in failed
        if row["variant"] in {"safe_local", "safe_transactional"}
    ]
    unsafe_rows = [
        row
        for row in case_results
        if row["variant"] in {"unsafe_trial_cache", "unsafe_output_feedback"}
    ]
    ref_failed = [row for row in failed if row["case_id"].startswith("MP-REF")]
    operator_failed = [row for row in failed if row["case_id"].startswith("MP-OP")]
    checkpoint_failed = [
        row for row in failed if row["case_id"] in {"MP-LC-06", "MP-LC-07"}
    ]

    def gate(status: str, hard: bool, *evidence: str) -> dict[str, Any]:
        return {"status": status, "hard_gate": hard, "evidence": list(evidence)}

    return {
        "schema_provenance": gate(
            "PASS" if design_validation["passed"] and len(case_results) == 25 else "FAIL",
            True,
            "20 unique design cases; 45 total outcomes; 12 MP cases; 25 MP outcomes",
            "40-column ledger schema validated",
        ),
        "declared_state_equality": gate(
            "PASS"
            if all(row["declared_packet_equal"] == "true" for row in case_results)
            else "FAIL",
            True,
            "all compared replay packet hashes equal",
        ),
        "lifecycle": gate(
            "PASS" if not safe_failed and not failed else "FAIL",
            True,
            "safe controls invariant; seeded violations detected as expected",
        ),
        "seed_detection": gate(
            "PASS" if unsafe_rows and all(row["passed"] == "true" for row in unsafe_rows) else "FAIL",
            True,
            "unsafe_trial_cache and unsafe_output_feedback outcomes",
        ),
        "analytical_reference": gate(
            "PASS" if not ref_failed and not operator_failed else "FAIL",
            True,
            "fraction oracle and central-difference tangent gates",
        ),
        "thermodynamic_sanity": gate(
            "PASS"
            if all(
                row["passed"] == "true"
                for row in case_results
                if row["case_id"] == "MP-REF-03"
            )
            else "FAIL",
            True,
            "accepted load-unload-reload path; nonnegative incremental plastic dissipation",
        ),
        "output_checkpoint": gate(
            "PASS" if not checkpoint_failed else "FAIL",
            True,
            "terminal noninterference and checkpoint round trip",
        ),
        "reproducibility": gate(
            "BLOCKED",
            True,
            "awaiting comparison of two complete clean executions",
        ),
        "performance_reporting": gate(
            "PASS",
            False,
            "wall time and Python peak allocation recorded outside deterministic artifacts",
        ),
        "L1-E1_execution": gate(
            "BLOCKED",
            True,
            "not authorized in this execution scope",
        ),
    }


def build_report(
    case_results: list[dict[str, str]],
    ledger_rows: int,
    checkpoint_rows: int,
    all_cases_passed: bool,
) -> str:
    unsafe = [
        row
        for row in case_results
        if row["variant"] in {"unsafe_trial_cache", "unsafe_output_feedback"}
    ]
    unsafe_lines = "\n".join(
        f"- `{row['case_id']} / {row['variant']}`: {row['observed_classification']}; "
        f"delta stress `{row['delta_stress']}`."
        for row in unsafe
    )
    status = "CANDIDATE PASS; DUPLICATE-RUN GATE PENDING" if all_cases_passed else "FAIL"
    return f"""# L1-MP candidate result

Status: **{status}**

## Scope

Only the 12 frozen `L1-MP` cases and 25 scenario-variant outcomes were executed. `L1-E1` was not implemented or run.

## Candidate result

- MP outcomes passing their predeclared expectation: `{sum(row['passed'] == 'true' for row in case_results)}/25`.
- Call-ledger rows: `{ledger_rows}`.
- Accepted-checkpoint rows: `{checkpoint_rows}`.
- Safe replay false positives: `{sum(row['passed'] != 'true' for row in case_results if row['variant'] in {'safe_local', 'safe_transactional'})}`.
- Normal numeric values were finite: `{all(row['finite'] == 'true' for row in case_results)}`.

## Seed observations

{unsafe_lines}

## Pending gate

The complete run must be repeated and the deterministic summary, case table, ledger and checkpoint table must be byte-identical before the MP result is finalized.

## Claim boundary

This candidate run tests the standalone L1-MP harness only. It does not establish L1-E1, Abaqus/UEL safety, global Newton robustness, restart parity, conservation, coupled-flow accuracy, cross-framework generality or CO2 application validity.
"""


def run(output_dir: Path) -> int:
    validation = validate_design(ROOT)
    if not validation["passed"]:
        print(json.dumps(validation, indent=2, sort_keys=True))
        return 2
    output_dir.mkdir(parents=True, exist_ok=False)
    impl_hash = implementation_hash()
    abaqus_before = scan_abaqus_processes()

    tracemalloc.start()
    started = time.perf_counter()
    benchmark = MPBenchmark(ROOT, impl_hash)
    case_results, _, checkpoints = benchmark.run()
    elapsed = time.perf_counter() - started
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    abaqus_after = scan_abaqus_processes()

    benchmark.ledger.write(output_dir / "l1_call_ledger.csv")
    write_csv(output_dir / "l1_case_results.csv", CASE_RESULT_COLUMNS, case_results)
    write_csv(output_dir / "l1_accepted_checkpoints.csv", CHECKPOINT_COLUMNS, checkpoints)
    write_json(output_dir / "l1_design_validation.json", validation)

    all_cases_passed = all(row["passed"] == "true" for row in case_results)
    report = build_report(
        case_results,
        len(benchmark.ledger.rows),
        len(checkpoints),
        all_cases_passed,
    )
    (output_dir / "l1_result_report.md").write_text(report, encoding="utf-8", newline="\n")

    deterministic_names = [
        "l1_call_ledger.csv",
        "l1_case_results.csv",
        "l1_accepted_checkpoints.csv",
        "l1_design_validation.json",
        "l1_result_report.md",
    ]
    deterministic_hashes = {
        name: sha256_file(output_dir / name) for name in deterministic_names
    }
    failed_cases = sorted({row["case_id"] for row in case_results if row["passed"] != "true"})
    passed_case_count = 12 - len(failed_cases)
    unsafe_rows = [
        row
        for row in case_results
        if row["variant"] in {"unsafe_trial_cache", "unsafe_output_feedback"}
    ]
    summary: dict[str, Any] = {
        "design_version": "L1-D1.0",
        "execution_status": "STOPPED_AT_MP_GATE" if failed_cases else "STOPPED_AT_E1_GATE",
        "implementation_hash": impl_hash,
        "case_count": 20,
        "scenario_variant_count": 45,
        "sublevels": {
            "L1-MP": {
                "status": "FAIL" if failed_cases else "PASS",
                "passed_cases": passed_case_count,
                "failed_cases": len(failed_cases),
                "blocked_cases": 0,
            },
            "L1-E1": {
                "status": "BLOCKED",
                "passed_cases": 0,
                "failed_cases": 0,
                "blocked_cases": 8,
            },
        },
        "gate_families": build_gate_families(case_results, validation),
        "overall_pass": False,
        "unsafe_seed_detected": bool(unsafe_rows)
        and all(row["passed"] == "true" for row in unsafe_rows),
        "safe_false_positive_count": sum(
            row["passed"] != "true"
            for row in case_results
            if row["variant"] in {"safe_local", "safe_transactional"}
        ),
        "ledger_rows": len(benchmark.ledger.rows),
        "result_sha256": deterministic_hashes,
        "claim_boundary": (
            "This is an L1-MP candidate result pending duplicate-run comparison. "
            "L1-E1 and L2-L6 remain blocked and open."
        ),
    }
    summary_errors = validate_summary_document(summary)
    if summary_errors:
        raise RuntimeError(f"Generated summary failed schema validation: {summary_errors}")
    write_json(output_dir / "l1_run_summary.json", summary)

    runtime_metrics = {
        "wall_time_seconds": elapsed,
        "python_peak_allocated_bytes": peak_bytes,
        "evaluation_ledger_rows": len(benchmark.ledger.rows),
        "case_outcomes": len(case_results),
    }
    write_json(output_dir / "l1_runtime_metrics.json", runtime_metrics)

    source_paths = sorted((ROOT / "src").glob("*.py")) + [ROOT / "run_l1_mp.py"]
    manifest = {
        "design_version": "L1-D1.0",
        "execution_identifier": "L1-MP-D1.0-REPLAY",
        "execution_scope": "L1-MP_ONLY",
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "single_threaded": True,
        "implementation_hash": impl_hash,
        "source_sha256": {
            path.relative_to(ROOT).as_posix(): sha256_file(path) for path in source_paths
        },
        "result_sha256": {
            path.name: sha256_file(path)
            for path in sorted(output_dir.iterdir())
            if path.is_file() and path.name != "l1_manifest.json"
        },
        "command_line": "python run_l1_mp.py --output-dir <OUTPUT_DIR>",
        "design_case_count": 20,
        "design_scenario_variant_count": 45,
        "executed_mp_case_count": 12,
        "executed_mp_scenario_variant_count": 25,
        "abaqus_used": False,
        "abaqus_processes_before": abaqus_before,
        "abaqus_processes_after": abaqus_after,
        "production_project_modified": False,
        "production_read_only_verification": "runner contains no production-project write path",
        "e1_executed": False,
    }
    write_json(output_dir / "l1_manifest.json", manifest)
    print(
        json.dumps(
            {
                "output_dir": str(output_dir),
                "all_cases_passed": all_cases_passed,
                "ledger_rows": len(benchmark.ledger.rows),
                "wall_time_seconds": elapsed,
                "peak_bytes": peak_bytes,
                "abaqus_process_count": len(abaqus_before) + len(abaqus_after),
            },
            sort_keys=True,
        )
    )
    return 0 if all_cases_passed and not abaqus_before and not abaqus_after else 3


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    return run(args.output_dir.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
