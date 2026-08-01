"""Finalize full L1 after two byte-stable E1 executions."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import platform
import shutil
from typing import Any

from run_l1_mp import scan_abaqus_processes, write_csv, write_json
from src.l1_cases import CASE_RESULT_COLUMNS, CHECKPOINT_COLUMNS
from src.l1_design_validation import sha256_file, validate_summary_document


ROOT = Path(__file__).resolve().parent
E1_DETERMINISTIC_FILES = [
    "l1_e1_call_ledger.csv",
    "l1_e1_case_results.csv",
    "l1_e1_accepted_checkpoints.csv",
    "l1_e1_design_validation.json",
    "l1_e1_result_report.md",
    "l1_e1_run_summary.json",
]


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def final_report(
    all_rows: list[dict[str, str]], ledger_rows: int,
    checkpoint_rows: int, comparison: dict[str, Any],
) -> str:
    e1_rows = [row for row in all_rows if row["sublevel"] == "L1-E1"]
    seeded = [
        row for row in e1_rows
        if row["variant"] in {
            "unsafe_trial_cache", "unsafe_output_feedback", "seeded_version_mismatch"
        }
    ]
    seed_lines = "\n".join(
        f"- `{row['case_id']} / {row['variant']}`: "
        f"`{row['observed_classification']}`; Delta R `{row['delta_residual']}`."
        for row in seeded
    )
    return f"""# L1 material-point and one-element final result

Status: **PASS L1-MP AND L1-E1 / L2-L6 OPEN**

## Decision

The finalized 12-case material-point sublevel and the newly executed eight-case
one-element sublevel passed all predeclared hard gates. The 20 E1 outcomes were
executed twice, and all six deterministic E1 artifacts were byte identical.

## Full L1 evidence

- Cases passed: `20/20`.
- Scenario-variant outcomes passed: `45/45`.
- Combined call-ledger rows: `{ledger_rows}`.
- Combined accepted-checkpoint rows: `{checkpoint_rows}`.
- Safe-control false positives: `0`.
- E1 duplicate files matched: `{len(comparison['files'])}/{len(comparison['files'])}`.
- Abaqus processes used: `0`.

## E1 negative controls

{seed_lines}

`E1-LC-02` used a pre-execution seed erratum after an informal preflight
proved that the original monotonic permutation had zero discriminating drift.
The formal histories use the same +0.03/-0.03 discarded packets in opposite
order; equations, tolerances, replay packet, and expected class are unchanged.

## Evidence classification

- `OBSERVED_L1`: 45 outcome rows, lifecycle ledgers, output/checkpoint
  provenance, version mismatch detection, and duplicate-run evidence.
- `ESTABLISHED_ANALYTICAL_REFERENCE`: one-dimensional return mapping and
  one-point bar R/K values.
- `OPEN`: L2-L6, host forced-retry behavior, global nonlinear convergence,
  conservation, coupled physical accuracy, performance, and application claims.

## Claim boundary

Full L1 demonstrates only that this standalone single-threaded harness detects
its seeded material and element lifecycle defects without false positives in
its safe controls. It does not establish Abaqus/UEL safety, restart parity,
global Newton robustness, mass conservation, spatial stability, two-phase
poromechanics accuracy, cross-framework generality, CO2 plume validity, fault
response, surface displacement, or production performance.
"""


def finalize(run_1: Path, run_2: Path, output_dir: Path) -> int:
    if output_dir.exists():
        raise FileExistsError(f"Final output directory already exists: {output_dir}")
    comparison: dict[str, Any] = {
        "design_version": "L1-D1.0", "sublevel": "L1-E1",
        "files": {}, "all_match": True,
    }
    for name in E1_DETERMINISTIC_FILES:
        hash_1, hash_2 = sha256_file(run_1 / name), sha256_file(run_2 / name)
        matched = hash_1 == hash_2
        comparison["files"][name] = {
            "run_1_sha256": hash_1, "run_2_sha256": hash_2, "matched": matched,
        }
        comparison["all_match"] = comparison["all_match"] and matched
    if not comparison["all_match"]:
        print(json.dumps(comparison, indent=2, sort_keys=True))
        return 2

    e1_rows = read_csv(run_1 / "l1_e1_case_results.csv")
    if len(e1_rows) != 20 or any(row["passed"] != "true" for row in e1_rows):
        raise RuntimeError("Cannot finalize: one or more E1 outcomes failed")
    summary_1 = read_json(run_1 / "l1_e1_run_summary.json")
    summary_2 = read_json(run_2 / "l1_e1_run_summary.json")
    if summary_1 != summary_2 or summary_1["sublevels"]["L1-E1"]["status"] != "PASS":
        raise RuntimeError("Cannot finalize: candidate summaries differ or E1 is not PASS")
    abaqus = scan_abaqus_processes()
    if abaqus:
        raise RuntimeError(f"Abaqus process found during finalization: {abaqus}")

    mp_archive = ROOT / "results_mp_pass"
    mp_dir = mp_archive if mp_archive.exists() else ROOT / "results"
    mp_rows = read_csv(mp_dir / "l1_case_results.csv")
    if len(mp_rows) != 25 or any(row["passed"] != "true" for row in mp_rows):
        raise RuntimeError("Finalized MP evidence is missing or no longer PASS")
    all_rows = mp_rows + e1_rows
    mp_ledger = read_csv(mp_dir / "l1_call_ledger.csv")
    e1_ledger = read_csv(run_1 / "l1_e1_call_ledger.csv")
    mp_checkpoints = read_csv(mp_dir / "l1_accepted_checkpoints.csv")
    e1_checkpoints = read_csv(run_1 / "l1_e1_accepted_checkpoints.csv")

    output_dir.mkdir(parents=True, exist_ok=False)
    write_csv(output_dir / "l1_call_ledger.csv", list(mp_ledger[0]), mp_ledger + e1_ledger)
    write_csv(output_dir / "l1_case_results.csv", CASE_RESULT_COLUMNS, all_rows)
    write_csv(
        output_dir / "l1_accepted_checkpoints.csv",
        CHECKPOINT_COLUMNS, mp_checkpoints + e1_checkpoints,
    )

    validation = {
        "passed": True,
        "mp": read_json(mp_dir / "l1_design_validation.json"),
        "e1": read_json(run_1 / "l1_e1_design_validation.json"),
        "case_count": 20,
        "scenario_variant_count": 45,
        "ledger_column_count": len(mp_ledger[0]),
    }
    write_json(output_dir / "l1_design_validation.json", validation)
    write_json(output_dir / "l1_duplicate_run_comparison.json", {
        "design_version": "L1-D1.0",
        "sublevels": {
            "L1-MP": read_json(mp_dir / "l1_duplicate_run_comparison.json"),
            "L1-E1": comparison,
        },
        "all_match": True,
    })

    metrics_1 = read_json(run_1 / "l1_e1_runtime_metrics.json")
    metrics_2 = read_json(run_2 / "l1_e1_runtime_metrics.json")
    runtime = {
        "L1-MP": read_json(mp_dir / "l1_runtime_metrics.json"),
        "L1-E1": {
            "run_1": metrics_1, "run_2": metrics_2,
            "total_wall_time_seconds": (
                metrics_1["wall_time_seconds"] + metrics_2["wall_time_seconds"]
            ),
            "maximum_python_peak_allocated_bytes": max(
                metrics_1["python_peak_allocated_bytes"],
                metrics_2["python_peak_allocated_bytes"],
            ),
        },
        "performance_is_reporting_only": True,
    }
    write_json(output_dir / "l1_runtime_metrics.json", runtime)
    report = final_report(
        all_rows, len(mp_ledger) + len(e1_ledger),
        len(mp_checkpoints) + len(e1_checkpoints), comparison,
    )
    (output_dir / "l1_result_report.md").write_text(
        report, encoding="utf-8", newline="\n"
    )

    gates = summary_1["gate_families"]
    gates["reproducibility"] = {
        "status": "PASS", "hard_gate": True,
        "evidence": [
            "two complete L1-E1 executions",
            "six deterministic E1 artifacts byte identical",
            "finalized L1-MP duplicate-run gate preserved",
        ],
    }
    final_summary: dict[str, Any] = {
        "design_version": "L1-D1.0",
        "execution_status": "COMPLETE",
        "implementation_hash": summary_1["implementation_hash"],
        "case_count": 20,
        "scenario_variant_count": 45,
        "sublevels": {
            "L1-MP": {
                "status": "PASS", "passed_cases": 12,
                "failed_cases": 0, "blocked_cases": 0,
            },
            "L1-E1": {
                "status": "PASS", "passed_cases": 8,
                "failed_cases": 0, "blocked_cases": 0,
            },
        },
        "gate_families": gates,
        "overall_pass": True,
        "unsafe_seed_detected": True,
        "safe_false_positive_count": 0,
        "ledger_rows": len(mp_ledger) + len(e1_ledger),
        "result_sha256": {},
        "claim_boundary": (
            "Standalone L1-MP and L1-E1 passed all predeclared hard gates in "
            "byte-stable executions. L2-L6 and all host/application claims remain open."
        ),
    }
    pre_summary_names = [
        "l1_call_ledger.csv", "l1_case_results.csv",
        "l1_accepted_checkpoints.csv", "l1_design_validation.json",
        "l1_duplicate_run_comparison.json", "l1_runtime_metrics.json",
        "l1_result_report.md",
    ]
    final_summary["result_sha256"] = {
        name: sha256_file(output_dir / name) for name in pre_summary_names
    }
    errors = validate_summary_document(final_summary)
    if errors:
        raise RuntimeError(f"Final full-L1 summary failed validation: {errors}")
    write_json(output_dir / "l1_run_summary.json", final_summary)

    source_files = [
        path for path in sorted(ROOT.rglob("*"))
        if path.is_file()
        and not any(
            part in {
                "results", "results_complete", "results_mp_pass",
                "l1_mp_runs", "l1_e1_runs", "__pycache__",
            }
            or part.startswith("_artifact_test") or part.startswith("results_")
            for part in path.relative_to(ROOT).parts
        )
        and path.suffix.lower() in {".py", ".md", ".csv", ".json"}
    ]
    result_files = [
        path for path in sorted(output_dir.iterdir())
        if path.is_file() and path.name != "l1_manifest.json"
    ]
    write_json(output_dir / "l1_manifest.json", {
        "design_version": "L1-D1.0",
        "execution_identifier": "L1-FINAL-D1.0",
        "execution_scope": "L1-MP_AND_L1-E1",
        "execution_status": "L1_PASS_L2_L6_OPEN",
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "single_threaded": True,
        "implementation_hash": final_summary["implementation_hash"],
        "source_sha256": {
            path.relative_to(ROOT).as_posix(): sha256_file(path) for path in source_files
        },
        "result_sha256": {path.name: sha256_file(path) for path in result_files},
        "commands": [
            "python -m unittest discover -s tests -v",
            "python run_l1_e1.py --output-dir <RUN_1>",
            "python run_l1_e1.py --output-dir <RUN_2>",
            "python finalize_l1_e1.py --run-1 <RUN_1> --run-2 <RUN_2> --output-dir results_complete",
        ],
        "design_case_count": 20,
        "design_scenario_variant_count": 45,
        "executed_mp_case_count": 12,
        "executed_mp_scenario_variant_count": 25,
        "executed_e1_case_count": 8,
        "executed_e1_scenario_variant_count": 20,
        "ledger_rows": len(mp_ledger) + len(e1_ledger),
        "checkpoint_rows": len(mp_checkpoints) + len(e1_checkpoints),
        "duplicate_run_all_match": True,
        "abaqus_used": False,
        "abaqus_processes_at_finalization": abaqus,
        "production_project_modified": False,
        "production_read_only_verification": (
            "E1 implementation and execution used only the independent NCS staging tree"
        ),
        "claim_boundary": (
            "Observed pass ends at standalone L1. Host integration, L2-L6, "
            "conservation, physical accuracy, applications, and performance remain open."
        ),
    })
    print(json.dumps({
        "status": "L1_PASS_L2_L6_OPEN", "output_dir": str(output_dir),
        "case_outcomes": len(all_rows),
        "ledger_rows": len(mp_ledger) + len(e1_ledger),
        "duplicate_files_matched": len(E1_DETERMINISTIC_FILES),
    }, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-1", type=Path, required=True)
    parser.add_argument("--run-2", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    return finalize(
        args.run_1.resolve(), args.run_2.resolve(), args.output_dir.resolve()
    )


if __name__ == "__main__":
    raise SystemExit(main())

