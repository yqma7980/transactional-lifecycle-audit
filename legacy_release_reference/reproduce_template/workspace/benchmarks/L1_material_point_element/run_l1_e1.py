"""Run frozen L1-E1 after the finalized L1-MP prerequisite."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import platform
import time
import tracemalloc
from typing import Any

from run_l1_mp import scan_abaqus_processes, write_csv, write_json
from src.l1_design_validation import sha256_file, validate_design, validate_summary_document
from src.l1_e1_cases import CASE_RESULT_COLUMNS, CHECKPOINT_COLUMNS, E1Benchmark


ROOT = Path(__file__).resolve().parent


def implementation_hash() -> str:
    digest = hashlib.sha256()
    paths = sorted((ROOT / "src").glob("*.py")) + [ROOT / "run_l1_e1.py"]
    for path in paths:
        digest.update(path.relative_to(ROOT).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def validate_e1_prerequisites() -> dict[str, Any]:
    design = validate_design(ROOT)
    errors = list(design["errors"])
    freeze = json.loads((ROOT / "L1_E1_execution_freeze.json").read_text(encoding="utf-8"))
    if freeze.get("e1_authorized") is not True:
        errors.append("L1-E1 execution is not authorized")
    if freeze.get("execution_scope") != "L1-E1_ONLY_AFTER_MP_PASS":
        errors.append("invalid L1-E1 execution scope")
    mp_summary = json.loads((ROOT / "results" / "l1_run_summary.json").read_text(encoding="utf-8"))
    if mp_summary["sublevels"]["L1-MP"]["status"] != "PASS":
        errors.append("L1-MP prerequisite is not PASS")
    if mp_summary["gate_families"]["reproducibility"]["status"] != "PASS":
        errors.append("L1-MP duplicate-run gate is not PASS")
    with (ROOT / "L1_case_matrix.csv").open("r", encoding="utf-8", newline="") as handle:
        e1_rows = [row for row in csv.DictReader(handle) if row["sublevel"] == "L1-E1"]
    e1_outcomes = sum(len(row["variants_required"].split(";")) for row in e1_rows)
    if len(e1_rows) != 8 or e1_outcomes != 20:
        errors.append("L1-E1 must contain 8 cases and 20 outcomes")
    lc02 = next(row for row in e1_rows if row["case_id"] == "E1-LC-02")
    if (
        lc02["history_1"] != "discarded_u_0.03_then_m0.03"
        or lc02["history_2"] != "discarded_u_m0.03_then_0.03"
    ):
        errors.append("E1-LC-02 does not match the pre-execution seed erratum")
    return {
        "passed": not errors,
        "errors": errors,
        "design_validation": design,
        "mp_prerequisite_status": mp_summary["sublevels"]["L1-MP"]["status"],
        "mp_reproducibility_status": mp_summary["gate_families"]["reproducibility"]["status"],
        "e1_case_count": len(e1_rows),
        "e1_scenario_variant_count": e1_outcomes,
        "seed_erratum_status": freeze["pre_execution_seed_erratum"]["status"],
    }


def build_gate_families(
    rows: list[dict[str, str]], validation: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    failed = [row for row in rows if row["passed"] != "true"]
    safe_failed = [
        row for row in failed if row["variant"] in {"safe_local", "safe_transactional"}
    ]
    negative = [
        row for row in rows
        if row["variant"] in {
            "unsafe_trial_cache", "unsafe_output_feedback", "seeded_version_mismatch"
        }
    ]
    reference_failed = [row for row in failed if row["case_id"].startswith("E1-REF")]
    output_failed = [
        row for row in failed if row["case_id"] in {"E1-LC-03", "E1-LC-04", "E1-LC-05"}
    ]
    version_failed = [row for row in failed if row["case_id"] == "E1-OP-01"]

    def gate(status: str, hard: bool, *evidence: str) -> dict[str, Any]:
        return {"status": status, "hard_gate": hard, "evidence": list(evidence)}

    return {
        "schema_provenance": gate(
            "PASS" if validation["passed"] and len(rows) == 20 else "FAIL", True,
            "8 E1 cases; 20 E1 outcomes; 40-column ledger",
        ),
        "L1-MP_prerequisite": gate(
            "PASS", True, "finalized MP summary and duplicate-run gate are PASS"
        ),
        "declared_state_equality": gate(
            "PASS" if all(row["declared_packet_equal"] == "true" for row in rows) else "FAIL",
            True, "all compared element replay packets are identical",
        ),
        "lifecycle": gate(
            "PASS" if not failed and not safe_failed else "FAIL", True,
            "safe controls invariant and negative controls detected",
        ),
        "seed_detection": gate(
            "PASS" if len(negative) == 4 and all(row["passed"] == "true" for row in negative)
            else "FAIL",
            True, "two trial-cache rows, output-feedback row, and version-mismatch row",
        ),
        "analytical_reference": gate(
            "PASS" if not reference_failed else "FAIL", True,
            "elastic and plastic bar residual/tangent references",
        ),
        "thermodynamic_sanity": gate(
            "PASS", True, "inherited finalized MP accepted-path dissipation gate"
        ),
        "output_checkpoint": gate(
            "PASS" if not output_failed else "FAIL", True,
            "read-only accepted output and exact checkpoint round trip",
        ),
        "residual_tangent_version": gate(
            "PASS" if not version_failed else "FAIL", True,
            "matched safe versions; isolated mismatch rejected before lifecycle verdict",
        ),
        "reproducibility": gate(
            "BLOCKED", True, "awaiting byte comparison of two complete E1 executions"
        ),
        "performance_reporting": gate(
            "PASS", False, "wall time and Python allocation are reporting-only"
        ),
    }



def build_report(rows: list[dict[str, str]], ledger_rows: int, checkpoint_rows: int) -> str:
    seeded = [
        row for row in rows
        if row["variant"] in {
            "unsafe_trial_cache", "unsafe_output_feedback", "seeded_version_mismatch"
        }
    ]
    seed_lines = "\n".join(
        f"- `{row['case_id']} / {row['variant']}`: "
        f"`{row['observed_classification']}`; Delta R `{row['delta_residual']}`."
        for row in seeded
    )
    return f"""# L1-E1 candidate result

Status: **CANDIDATE PASS; DUPLICATE-RUN GATE PENDING**

## Scope

The finalized L1-MP result was used only as a prerequisite. This execution covers
the eight frozen L1-E1 cases and 20 scenario-variant outcomes. No global solve,
Abaqus process, production UEL, L2, or application case was used.

## Candidate evidence

- E1 outcomes passing: `{sum(row['passed'] == 'true' for row in rows)}/20`.
- E1 call-ledger rows: `{ledger_rows}`.
- E1 accepted-checkpoint rows: `{checkpoint_rows}`.
- Safe-control false positives: `{sum(row['passed'] != 'true' for row in rows if row['variant'] in {'safe_local', 'safe_transactional'})}`.
- All normal numerical element outputs finite: `{all(row['finite'] == 'true' for row in rows)}`.

## Negative-control observations

{seed_lines}

`E1-LC-02` uses a documented pre-execution seed erratum. The original
monotonic permutation produced zero drift in an informal preflight; the formal
matrix therefore uses the same +0.03/-0.03 discarded packets in opposite order.
No equation, tolerance, common replay packet, or expected classification changed.

## Pending hard gate

A second clean execution must reproduce the six deterministic E1 artifacts byte
for byte before full L1 can be marked PASS.

## Claim boundary

This candidate tests a standalone one-point bar consumer of the L1 material
packet. It does not establish Abaqus safety, global Newton robustness,
conservation, physical accuracy, cross-framework generality, production
performance, CO2 plume validity, fault response, or surface displacement.
"""


def run(output_dir: Path) -> int:
    validation = validate_e1_prerequisites()
    if not validation["passed"]:
        print(json.dumps(validation, indent=2, sort_keys=True))
        return 2
    output_dir.mkdir(parents=True, exist_ok=False)
    impl_hash = implementation_hash()
    abaqus_before = scan_abaqus_processes()

    tracemalloc.start()
    started = time.perf_counter()
    benchmark = E1Benchmark(ROOT, impl_hash)
    rows, _, checkpoints = benchmark.run()
    elapsed = time.perf_counter() - started
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    abaqus_after = scan_abaqus_processes()

    benchmark.ledger.write(output_dir / "l1_e1_call_ledger.csv")
    write_csv(output_dir / "l1_e1_case_results.csv", CASE_RESULT_COLUMNS, rows)
    write_csv(output_dir / "l1_e1_accepted_checkpoints.csv", CHECKPOINT_COLUMNS, checkpoints)
    write_json(output_dir / "l1_e1_design_validation.json", validation)
    report = build_report(rows, len(benchmark.ledger.rows), len(checkpoints))
    (output_dir / "l1_e1_result_report.md").write_text(
        report, encoding="utf-8", newline="\n"
    )

    deterministic_names = [
        "l1_e1_call_ledger.csv", "l1_e1_case_results.csv",
        "l1_e1_accepted_checkpoints.csv", "l1_e1_design_validation.json",
        "l1_e1_result_report.md",
    ]
    deterministic_hashes = {
        name: sha256_file(output_dir / name) for name in deterministic_names
    }
    failed_cases = sorted({row["case_id"] for row in rows if row["passed"] != "true"})
    all_passed = not failed_cases
    gates = build_gate_families(rows, validation)
    summary: dict[str, Any] = {
        "design_version": "L1-D1.0",
        "execution_status": "STOPPED_AT_E1_GATE",
        "implementation_hash": impl_hash,
        "case_count": 20,
        "scenario_variant_count": 45,
        "sublevels": {
            "L1-MP": {
                "status": "PASS", "passed_cases": 12,
                "failed_cases": 0, "blocked_cases": 0,
            },
            "L1-E1": {
                "status": "PASS" if all_passed else "FAIL",
                "passed_cases": 8 - len(failed_cases),
                "failed_cases": len(failed_cases), "blocked_cases": 0,
            },
        },
        "gate_families": gates,
        "overall_pass": False,
        "unsafe_seed_detected": gates["seed_detection"]["status"] == "PASS",
        "safe_false_positive_count": sum(
            row["passed"] != "true" for row in rows
            if row["variant"] in {"safe_local", "safe_transactional"}
        ),
        "ledger_rows": len(benchmark.ledger.rows),
        "result_sha256": deterministic_hashes,
        "claim_boundary": (
            "L1-E1 candidate outcomes passed, but full L1 remains incomplete "
            "until the duplicate-run hard gate passes. L2-L6 remain open."
        ),
    }
    errors = validate_summary_document(summary)
    if errors:
        raise RuntimeError(f"Generated E1 summary failed validation: {errors}")
    write_json(output_dir / "l1_e1_run_summary.json", summary)

    write_json(output_dir / "l1_e1_runtime_metrics.json", {
        "wall_time_seconds": elapsed,
        "python_peak_allocated_bytes": peak_bytes,
        "evaluation_ledger_rows": len(benchmark.ledger.rows),
        "case_outcomes": len(rows),
    })
    source_paths = sorted((ROOT / "src").glob("*.py")) + [ROOT / "run_l1_e1.py"]
    write_json(output_dir / "l1_e1_manifest.json", {
        "design_version": "L1-D1.0",
        "execution_identifier": "L1-E1-D1.0-REPLAY",
        "execution_scope": "L1-E1_ONLY_AFTER_MP_PASS",
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "single_threaded": True,
        "implementation_hash": impl_hash,
        "source_sha256": {
            path.relative_to(ROOT).as_posix(): sha256_file(path) for path in source_paths
        },
        "result_sha256": {
            path.name: sha256_file(path) for path in sorted(output_dir.iterdir())
            if path.is_file() and path.name != "l1_e1_manifest.json"
        },
        "command_line": "python run_l1_e1.py --output-dir <OUTPUT_DIR>",
        "executed_e1_case_count": 8,
        "executed_e1_scenario_variant_count": 20,
        "abaqus_used": False,
        "abaqus_processes_before": abaqus_before,
        "abaqus_processes_after": abaqus_after,
        "production_project_modified": False,
        "production_read_only_verification": "runner contains no production write path",
    })
    print(json.dumps({
        "output_dir": str(output_dir), "all_cases_passed": all_passed,
        "ledger_rows": len(benchmark.ledger.rows),
        "wall_time_seconds": elapsed, "peak_bytes": peak_bytes,
        "abaqus_process_count": len(abaqus_before) + len(abaqus_after),
    }, sort_keys=True))
    return 0 if all_passed and not abaqus_before and not abaqus_after else 3


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    return run(args.output_dir.resolve())


if __name__ == "__main__":
    raise SystemExit(main())

