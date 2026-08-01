"""Finalize L1-MP only after two complete candidate runs are byte stable."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import platform
import shutil
import time
from typing import Any

from run_l1_mp import scan_abaqus_processes, write_json
from src.l1_design_validation import sha256_file, validate_summary_document


ROOT = Path(__file__).resolve().parent
DETERMINISTIC_CANDIDATE_FILES = [
    "l1_call_ledger.csv",
    "l1_case_results.csv",
    "l1_accepted_checkpoints.csv",
    "l1_design_validation.json",
    "l1_result_report.md",
    "l1_run_summary.json",
]


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def final_report(
    case_rows: list[dict[str, str]],
    ledger_rows: int,
    checkpoint_rows: int,
    metrics: dict[str, Any],
) -> str:
    unsafe = [
        row
        for row in case_rows
        if row["variant"] in {"unsafe_trial_cache", "unsafe_output_feedback"}
    ]
    unsafe_lines = "\n".join(
        f"- `{row['case_id']} / {row['variant']}`: delta stress "
        f"`{row['delta_stress']}`; `{row['observed_classification']}`."
        for row in unsafe
    )
    return f"""# L1-MP final result

Status: **PASS L1-MP / L1-E1 NOT IMPLEMENTED OR EXECUTED**

## Decision

All 12 frozen L1-MP cases and all 25 scenario-variant outcomes passed their predeclared hard gates in two independent complete executions. The deterministic call ledger, case table, checkpoint table, design-validation record, candidate report and candidate summary were byte identical between runs.

This is Branch A of the frozen plan. The full L1 level is not complete because L1-E1 remains blocked and was not authorized in this task.

## Hard-gate evidence

- MP cases passed: `12/12`.
- MP scenario-variant outcomes passed: `25/25`.
- Safe replay false positives: `0`.
- Call-ledger rows: `{ledger_rows}`.
- Accepted-checkpoint rows: `{checkpoint_rows}`.
- All normal numeric outputs finite: `true`.
- Rejected evaluations left committed safe state unchanged: `true`.
- Duplicate accept advanced the accepted version only once: `true`.
- Safe terminal/output reads were non-interfering: `true`.
- Checkpoint round trips reproduced committed state and operator fingerprints: `true`.
- Elastic and plastic directional tangent checks passed the frozen tolerance: `true`.

## Seed observations

{unsafe_lines}

The primary rejected-plastic-trial seed reproduced the frozen analytical drift `Delta stress = -205/121` within `1e-12`. Safe-local and safe-transactional controls returned exact-zero replay drift for their applicable lifecycle comparisons.

`MP-LC-02` used a documented pre-execution seed erratum. The original monotonic call-order permutation reached the same hidden plastic state and could not exercise its finite-nonzero drift gate; before formal execution it was replaced by the same `+0.03/-0.03` discarded packets in opposite order. Equations, tolerances and expected classification were unchanged.

## Reproducibility

- Compared deterministic files: `{len(DETERMINISTIC_CANDIDATE_FILES)}`.
- Mismatched deterministic files: `0`.
- Run 1 wall time: `{metrics['run_1']['wall_time_seconds']:.9f} s`.
- Run 2 wall time: `{metrics['run_2']['wall_time_seconds']:.9f} s`.
- Maximum Python peak allocation: `{metrics['maximum_python_peak_allocated_bytes']}` bytes.
- Abaqus processes observed during finalization: `0`.

Performance values are descriptive only and are not an L1 pass criterion.

## Evidence classification

- `OBSERVED_L1`: the 25 MP outcomes, ledger, checkpoint, seed-detection and duplicate-run results.
- `ESTABLISHED_ANALYTICAL_REFERENCE`: the frozen Fraction oracle values and central-difference tolerances.
- `OPEN`: L1-E1, L2-L6, host integration, global solves, conservation, performance and application consequences.

## Claim boundary

The result shows that this standalone L1-MP harness detects its seeded path-dependent lifecycle defects without flagging its safe controls. It does not establish Abaqus/UEL safety, restart parity, global Newton robustness, mass conservation, two-phase poromechanics accuracy, cross-framework generality, CO2 plume validity, fault response or surface displacement.
"""


def finalize(run_1: Path, run_2: Path, output_dir: Path) -> int:
    if output_dir.exists():
        raise FileExistsError(f"Final output directory already exists: {output_dir}")
    comparison: dict[str, Any] = {
        "design_version": "L1-D1.0",
        "files": {},
        "all_match": True,
    }
    for name in DETERMINISTIC_CANDIDATE_FILES:
        hash_1 = sha256_file(run_1 / name)
        hash_2 = sha256_file(run_2 / name)
        matched = hash_1 == hash_2
        comparison["files"][name] = {
            "run_1_sha256": hash_1,
            "run_2_sha256": hash_2,
            "matched": matched,
        }
        comparison["all_match"] = comparison["all_match"] and matched
    if not comparison["all_match"]:
        print(json.dumps(comparison, indent=2, sort_keys=True))
        return 2

    with (run_1 / "l1_case_results.csv").open("r", encoding="utf-8", newline="") as handle:
        case_rows = list(csv.DictReader(handle))
    if len(case_rows) != 25 or any(row["passed"] != "true" for row in case_rows):
        raise RuntimeError("Cannot finalize: one or more MP outcomes failed")
    summary_1 = read_json(run_1 / "l1_run_summary.json")
    summary_2 = read_json(run_2 / "l1_run_summary.json")
    if summary_1 != summary_2 or summary_1["sublevels"]["L1-MP"]["status"] != "PASS":
        raise RuntimeError("Cannot finalize: candidate summaries disagree or MP is not PASS")

    metrics_1 = read_json(run_1 / "l1_runtime_metrics.json")
    metrics_2 = read_json(run_2 / "l1_runtime_metrics.json")
    metrics = {
        "run_1": metrics_1,
        "run_2": metrics_2,
        "total_wall_time_seconds": metrics_1["wall_time_seconds"] + metrics_2["wall_time_seconds"],
        "maximum_python_peak_allocated_bytes": max(
            metrics_1["python_peak_allocated_bytes"],
            metrics_2["python_peak_allocated_bytes"],
        ),
        "performance_is_reporting_only": True,
    }

    abaqus_processes = scan_abaqus_processes()
    if abaqus_processes:
        raise RuntimeError(f"Abaqus process found during L1 finalization: {abaqus_processes}")

    started = time.perf_counter()
    output_dir.mkdir(parents=True, exist_ok=False)
    for name in (
        "l1_call_ledger.csv",
        "l1_case_results.csv",
        "l1_accepted_checkpoints.csv",
        "l1_design_validation.json",
    ):
        shutil.copyfile(run_1 / name, output_dir / name)

    ledger_rows = sum(1 for _ in (output_dir / "l1_call_ledger.csv").open("r", encoding="utf-8")) - 1
    checkpoint_rows = (
        sum(1 for _ in (output_dir / "l1_accepted_checkpoints.csv").open("r", encoding="utf-8")) - 1
    )
    report = final_report(case_rows, ledger_rows, checkpoint_rows, metrics)
    (output_dir / "l1_result_report.md").write_text(report, encoding="utf-8", newline="\n")
    write_json(output_dir / "l1_duplicate_run_comparison.json", comparison)
    write_json(output_dir / "l1_runtime_metrics.json", metrics)

    final_summary = summary_1
    final_summary["gate_families"]["reproducibility"] = {
        "status": "PASS",
        "hard_gate": True,
        "evidence": [
            "two complete executions",
            "six deterministic candidate artifacts byte identical",
        ],
    }
    final_summary["execution_status"] = "STOPPED_AT_E1_GATE"
    final_summary["overall_pass"] = False
    final_summary["claim_boundary"] = (
        "L1-MP passed all hard gates in two byte-stable executions. "
        "L1-E1 was not implemented or executed, so full L1 remains incomplete."
    )
    result_names_before_summary = [
        "l1_call_ledger.csv",
        "l1_case_results.csv",
        "l1_accepted_checkpoints.csv",
        "l1_design_validation.json",
        "l1_duplicate_run_comparison.json",
        "l1_runtime_metrics.json",
        "l1_result_report.md",
    ]
    final_summary["result_sha256"] = {
        name: sha256_file(output_dir / name) for name in result_names_before_summary
    }
    errors = validate_summary_document(final_summary)
    if errors:
        raise RuntimeError(f"Final summary failed schema validation: {errors}")
    write_json(output_dir / "l1_run_summary.json", final_summary)

    source_files = [
        path
        for path in sorted(ROOT.rglob("*"))
        if path.is_file()
        and not any(
            part in {"results", "l1_mp_runs", "__pycache__"}
            or part.startswith("l1_mp_test_")
            for part in path.relative_to(ROOT).parts
        )
        and path.name != "NCS_STATUS.md"
        and path.suffix.lower() in {".py", ".md", ".csv", ".json"}
    ]
    result_files = [
        path for path in sorted(output_dir.iterdir()) if path.is_file() and path.name != "l1_manifest.json"
    ]
    manifest = {
        "design_version": "L1-D1.0",
        "execution_identifier": "L1-MP-FINAL-D1.0",
        "execution_scope": "L1-MP_ONLY",
        "execution_status": "L1_MP_PASS_L1_E1_NOT_EXECUTED",
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
            "python run_l1_mp.py --output-dir <RUN_1>",
            "python run_l1_mp.py --output-dir <RUN_2>",
            "python finalize_l1_mp.py --run-1 <RUN_1> --run-2 <RUN_2> --output-dir results",
        ],
        "design_case_count": 20,
        "design_scenario_variant_count": 45,
        "executed_mp_case_count": 12,
        "executed_mp_scenario_variant_count": 25,
        "ledger_rows": ledger_rows,
        "checkpoint_rows": checkpoint_rows,
        "duplicate_run_all_match": True,
        "abaqus_used": False,
        "abaqus_processes_at_finalization": abaqus_processes,
        "production_project_modified": False,
        "production_read_only_verification": "implementation and execution paths contain no production-project writes",
        "e1_implemented": False,
        "e1_executed": False,
        "finalization_wall_time_seconds": time.perf_counter() - started,
        "claim_boundary": (
            "Observed pass applies only to the standalone L1-MP harness. "
            "Full L1 and L2-L6 remain open."
        ),
    }
    write_json(output_dir / "l1_manifest.json", manifest)
    print(
        json.dumps(
            {
                "status": "L1_MP_PASS_L1_E1_NOT_EXECUTED",
                "output_dir": str(output_dir),
                "case_outcomes": len(case_rows),
                "ledger_rows": ledger_rows,
                "duplicate_files_matched": len(DETERMINISTIC_CANDIDATE_FILES),
            },
            sort_keys=True,
        )
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-1", type=Path, required=True)
    parser.add_argument("--run-2", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    return finalize(args.run_1.resolve(), args.run_2.resolve(), args.output_dir.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
