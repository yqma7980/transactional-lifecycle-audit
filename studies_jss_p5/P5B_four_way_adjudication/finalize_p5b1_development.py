from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results" / "development"
FINAL = RESULTS / "final"
CASES = (
    "P5B-PASS-01", "P5B-PASS-02", "P5B-PASS-03", "P5B-PASS-04",
    "P5B-DETECT-01", "P5B-DETECT-02", "P5B-DETECT-03", "P5B-DETECT-04",
    "P5B-INVALID-01", "P5B-INVALID-02", "P5B-INVALID-03", "P5B-INVALID-04",
    "P5B-NS-01", "P5B-NS-02", "P5B-NS-03", "P5B-NS-04",
)
HELD_OUT = ("P5B-PASS-05", "P5B-DETECT-05", "P5B-INVALID-05", "P5B-NS-05")
RUNS = ("run_1", "run_2")
RUN_FILES = {
    "case_result.json", "runtime_observation.json",
    "event_ledger.json", "case_manifest.json",
}
SEAL_SHA = "1fb1424db6d8c289f80fc7d0705178b79f3741edbee5816dc37c07b26c2e374f"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True, ensure_ascii=True)
        handle.write("\n")


def write_text(path: Path, value: str) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(value.rstrip() + "\n")


def main() -> int:
    errors: list[str] = []
    protected = read(ROOT / "P5B_FORMAL_REVIEW_SOURCE_MANIFEST.json")
    for row in protected["files"]:
        path = ROOT / row["relative_path"]
        if not path.is_file() or sha(path) != row["sha256"] or path.stat().st_size != row["bytes"]:
            errors.append("protected drift: " + row["relative_path"])
    if sha(ROOT / "P5B_HELDOUT_SEAL_STATUS.json") != SEAL_SHA:
        errors.append("held-out seal drift")
    for case_id in HELD_OUT:
        if any(path.name == case_id for path in ROOT.rglob(case_id)):
            errors.append("held-out path exists: " + case_id)
    actual_cases = tuple(sorted(
        path.name for path in RESULTS.iterdir()
        if path.is_dir() and path.name != "final"
    ))
    if actual_cases != tuple(sorted(CASES)):
        errors.append("DEVELOPMENT directory set differs from freeze")

    duplicates = []
    raw_files = []
    case_rows = []
    verdicts: Counter[str] = Counter()
    subjects: Counter[str] = Counter()
    for case_id in CASES:
        pair = []
        for run_id in RUNS:
            run_dir = RESULTS / case_id / run_id
            if {p.name for p in run_dir.iterdir() if p.is_file()} != RUN_FILES:
                errors.append(f"unexpected file set: {case_id}/{run_id}")
            payloads = {name: read(run_dir / name) for name in sorted(RUN_FILES)}
            result = payloads["case_result.json"]
            observation = payloads["runtime_observation.json"]
            ledger = payloads["event_ledger.json"]
            manifest = payloads["case_manifest.json"]
            verdicts[result["four_way_verdict"]] += 1
            subjects[manifest["subject_id"]] += 1
            if not result["pass_flag"]:
                errors.append(f"frozen verdict failed: {case_id}/{run_id}")
            if manifest["observed_verdict"] != result["four_way_verdict"]:
                errors.append(f"verdict chain failed: {case_id}/{run_id}")
            fingerprint = observation["semantic_fingerprint"]
            if manifest["runtime_semantic_fingerprint"] != fingerprint:
                errors.append(f"manifest fingerprint failed: {case_id}/{run_id}")
            if ledger["semantic_fingerprint"] != fingerprint:
                errors.append(f"ledger fingerprint failed: {case_id}/{run_id}")
            for name, row in manifest["outputs"].items():
                path = run_dir / name
                if sha(path) != row["sha256"] or path.stat().st_size != row["bytes"]:
                    errors.append(f"output integrity failed: {case_id}/{run_id}/{name}")
            for path in sorted(run_dir.iterdir()):
                if path.is_file():
                    raw_files.append({
                        "relative_path": path.relative_to(ROOT).as_posix(),
                        "sha256": sha(path),
                        "bytes": path.stat().st_size,
                    })
            pair.append(payloads)

        left, right = pair
        normalized_left = {k: v for k, v in left["case_result.json"].items() if k != "run_id"}
        normalized_right = {k: v for k, v in right["case_result.json"].items() if k != "run_id"}
        checks = {
            "case_result_equal_after_run_id_normalization": normalized_left == normalized_right,
            "runtime_semantic_fingerprint_equal":
                left["runtime_observation.json"]["semantic_fingerprint"]
                == right["runtime_observation.json"]["semantic_fingerprint"],
            "event_ledger_semantic_fingerprint_equal":
                left["event_ledger.json"]["semantic_fingerprint"]
                == right["event_ledger.json"]["semantic_fingerprint"],
            "input_hashes_equal":
                left["case_manifest.json"]["inputs"] == right["case_manifest.json"]["inputs"],
            "verdict_equal":
                left["case_result.json"]["four_way_verdict"]
                == right["case_result.json"]["four_way_verdict"],
            "both_pass_flag_true":
                left["case_result.json"]["pass_flag"] and right["case_result.json"]["pass_flag"],
        }
        duplicate_pass = all(checks.values())
        if not duplicate_pass:
            errors.append("duplicate gate failed: " + case_id)
        duplicates.append({
            "case_id": case_id,
            **checks,
            "run_1_semantic_fingerprint":
                left["runtime_observation.json"]["semantic_fingerprint"],
            "run_2_semantic_fingerprint":
                right["runtime_observation.json"]["semantic_fingerprint"],
            "observed_verdict": left["case_result.json"]["four_way_verdict"],
            "duplicate_gate_pass": duplicate_pass,
        })
        case_rows.append({
            "case_id": case_id,
            "subject_id": left["case_manifest.json"]["subject_id"],
            "expected_verdict": left["case_manifest.json"]["expected_verdict"],
            "observed_verdict": left["case_manifest.json"]["observed_verdict"],
            "formal_repetitions": 2,
            "all_repetitions_passed": checks["both_pass_flag_true"],
            "duplicate_gate_pass": duplicate_pass,
        })

    expected_verdicts = {
        "PASS_INVARIANT": 8, "DETECT_LIFECYCLE_DRIFT": 8,
        "INVALID": 8, "NOT_SUPPORTED": 8,
    }
    if len(raw_files) != 128:
        errors.append(f"raw file count {len(raw_files)} != 128")
    if dict(verdicts) != expected_verdicts:
        errors.append("verdict distribution differs from freeze")
    if errors:
        raise SystemExit("\n".join(errors))
    if FINAL.exists():
        raise FileExistsError("final evidence directory already exists")
    FINAL.mkdir(parents=False, exist_ok=False)

    duplicate_path = FINAL / "P5B1_duplicate_comparison.json"
    write_json(duplicate_path, {
        "schema_version": "JSS-P5B1-DUPLICATE-COMPARISON-1.0",
        "status": "PASS",
        "case_count": 16,
        "fresh_process_repetitions_per_case": 2,
        "all_duplicate_gates_passed": True,
        "comparisons": duplicates,
    })
    raw_aggregate = hashlib.sha256("\n".join(
        f"{row['relative_path']}|{row['sha256']}" for row in raw_files
    ).encode("utf-8")).hexdigest()
    raw_manifest_path = FINAL / "P5B1_development_raw_manifest.json"
    write_json(raw_manifest_path, {
        "schema_version": "JSS-P5B1-DEVELOPMENT-RAW-MANIFEST-1.0",
        "status": "RAW_EVIDENCE_FROZEN",
        "formal_case_count": 16,
        "formal_process_count": 32,
        "raw_file_count": 128,
        "aggregate_spec": "sorted <relative_path>|<sha256>, UTF-8, LF, no final newline",
        "aggregate_sha256": raw_aggregate,
        "files": raw_files,
        "manifest_self_hash_embedded": False,
    })
    summary_path = FINAL / "P5B1_development_final_summary.json"
    write_json(summary_path, {
        "schema_version": "JSS-P5B1-DEVELOPMENT-SUMMARY-1.0",
        "status": "DEVELOPMENT_COMPLETE_HELD_OUT_REMAINS_SEALED",
        "evidence_status": "OBSERVED-P5B-DEVELOPMENT",
        "design_version": "JSS-P5B.0",
        "implementation_revision": "JSS-P5B1-RUNTIME-1.0",
        "formal_case_count": 16,
        "formal_process_count": 32,
        "fresh_process_repetitions_per_case": 2,
        "processes_per_repetition": 1,
        "threads_per_process": 1,
        "all_cases_passed_frozen_verdict": True,
        "all_duplicate_gates_passed": True,
        "verdict_counts_by_run": expected_verdicts,
        "subject_counts_by_run": dict(sorted(subjects.items())),
        "case_results": case_rows,
        "held_out_case_count": 4,
        "held_out_access_authorized": False,
        "held_out_results_exist": False,
        "held_out_case_ids": list(HELD_OUT),
        "abaqus_used": False,
        "production_project_used": False,
        "does_not_authorize_held_out": True,
    })
    report_path = FINAL / "P5B1_development_result_report.md"
    report = [
        "# P5B.1 DEVELOPMENT formal execution report", "",
        "Status: DEVELOPMENT_COMPLETE_HELD_OUT_REMAINS_SEALED.", "",
        "Sixteen frozen DEVELOPMENT cases were each run in two fresh,",
        "single-process, single-thread repetitions. All 32 runs matched their",
        "predeclared four-way verdict and all 16 duplicate gates passed.", "",
        "| Case | Subject | Verdict | Runs | Duplicate |",
        "|---|---|---|---:|---|",
    ]
    report += [
        f"| {row['case_id']} | {row['subject_id']} | {row['observed_verdict']} | 2/2 | PASS |"
        for row in case_rows
    ]
    report += [
        "", "## Evidence boundary", "",
        "This package establishes only the frozen DEVELOPMENT outcomes.",
        "It does not provide held-out evidence, detection-rate estimates,",
        "production solver validation, Abaqus evidence, thread-safety evidence,",
        "performance evidence, or general solver certification.", "",
        "All four held-out cases remain sealed. No held-out activation manifest",
        "or held-out result directory was created.",
    ]
    write_text(report_path, "\n".join(report))

    impl_files = (
        "P5B1_EXECUTION_ADAPTER_FREEZE.json", "P5B1_CASE_RUNTIME_MAPPING.csv",
        "P5B1_EXECUTION_PROTOCOL.md", "run_p5b_development.py",
        "src/jss_p5b/formal_executor.py", "src/jss_p5b/runtime.py",
        "src/jss_p5b/runtime_local.py", "src/jss_p5b/runtime_mapping.py",
        "src/jss_p5b/runtime_s01.py", "src/jss_p5b/runtime_schema.py",
        "schemas/p5b_runtime_observation.schema.json",
        "tests/test_p5b1_local_subjects.py", "tests/test_p5b1_runner_lock.py",
        "tests/test_p5b1_runtime_mapping.py", "finalize_p5b1_development.py",
    )
    implementation_path = ROOT / "P5B1_IMPLEMENTATION_MANIFEST.json"
    write_json(implementation_path, {
        "schema_version": "JSS-P5B1-IMPLEMENTATION-MANIFEST-1.0",
        "implementation_status": "FORMALLY_EXECUTED_DEVELOPMENT_ONLY",
        "implementation_revision": "JSS-P5B1-RUNTIME-1.0",
        "pre_execution_unit_test_count": 46,
        "pre_execution_unit_tests_passed": 46,
        "pre_execution_identity_correction":
            "SciPy semantic path identifiers were made run-independent before formal execution; no equation, threshold, case, or verdict rule changed.",
        "docker_image":
            "dolfinx/dolfinx@sha256:1bb0d528457c78db65ba5445421abe37d0cdfa542cc182bf36d3b4aca02f1fab",
        "formal_case_count": 16,
        "formal_process_count": 32,
        "held_out_execution_count": 0,
        "files": {
            relative: {"sha256": sha(ROOT / relative), "bytes": (ROOT / relative).stat().st_size}
            for relative in impl_files
        },
        "manifest_self_hash_embedded": False,
    })
    preflight_path = ROOT / "P5B1_IMPLEMENTATION_PREFLIGHT_QA.md"
    write_text(preflight_path, """# P5B.1 implementation preflight QA

Status: PASS.

- JSON, CSV, AST, schema, and authorization contracts passed.
- The complete unit suite passed 46/46.
- Held-out selection and write attempts were rejected before directory creation.
- The fixed-digest DOLFINx image identity and read-only import smoke passed.
- The pre-execution run-identity correction changed no scientific contract.
""")
    final_qa_path = ROOT / "P5B1_DEVELOPMENT_FINAL_QA.md"
    write_text(final_qa_path, f"""# P5B.1 DEVELOPMENT final QA

Status: PASS_DEVELOPMENT_COMPLETE_HELD_OUT_REMAINS_SEALED.

- Protected files: {len(protected['files'])}; mismatches: 0.
- Formal DEVELOPMENT cases: 16/16.
- Fresh-process runs: 32/32.
- Raw result files: 128/128.
- Manifest integrity failures: 0.
- Duplicate semantic failures: 0.
- Verdict distribution: 8 PASS, 8 DETECT, 8 INVALID, 8 NOT_SUPPORTED runs.
- Held-out result directories and activation manifests: 0.
- Held-out seal SHA-256: {SEAL_SHA}.
- Abaqus and production models were not used.

This QA does not authorize held-out execution.
""")
    execution_manifest_path = FINAL / "P5B1_development_execution_manifest.json"
    tracked_outputs = (
        duplicate_path, raw_manifest_path, summary_path, report_path,
        implementation_path, preflight_path, final_qa_path,
    )
    write_json(execution_manifest_path, {
        "schema_version": "JSS-P5B1-DEVELOPMENT-EXECUTION-MANIFEST-1.0",
        "status": "DEVELOPMENT_COMPLETE_HELD_OUT_REMAINS_SEALED",
        "created_date": date.today().isoformat(),
        "raw_manifest_sha256": sha(raw_manifest_path),
        "summary_outputs": {
            path.relative_to(ROOT).as_posix(): sha(path) for path in tracked_outputs
        },
        "protected_source_manifest_sha256":
            sha(ROOT / "P5B_FORMAL_REVIEW_SOURCE_MANIFEST.json"),
        "development_activation_sha256": sha(ROOT / "P5B_DEVELOPMENT_ACTIVATION.json"),
        "held_out_seal_sha256": sha(ROOT / "P5B_HELDOUT_SEAL_STATUS.json"),
        "no_held_out_execution": True,
        "no_abaqus_execution": True,
        "no_production_model_execution": True,
        "manifest_self_hash_embedded": False,
    })

    source_manifest_path = ROOT / "P5B1_SOURCE_MANIFEST.json"
    source_rows = []
    for path in sorted(p for p in ROOT.rglob("*") if p.is_file()):
        if path != source_manifest_path:
            source_rows.append({
                "relative_path": path.relative_to(ROOT).as_posix(),
                "sha256": sha(path),
                "bytes": path.stat().st_size,
            })
    source_aggregate = hashlib.sha256("\n".join(
        f"{row['relative_path']}|{row['sha256']}" for row in source_rows
    ).encode("utf-8")).hexdigest()
    write_json(source_manifest_path, {
        "schema_version": "JSS-P5B1-SOURCE-MANIFEST-1.0",
        "package_status": "DEVELOPMENT_COMPLETE_HELD_OUT_REMAINS_SEALED",
        "file_count": len(source_rows),
        "aggregate_spec": "sorted <relative_path>|<sha256>, UTF-8, LF, no final newline",
        "aggregate_sha256": source_aggregate,
        "files": source_rows,
        "held_out_access_authorized": False,
        "held_out_results_exist": False,
        "manifest_self_hash_embedded": False,
    })
    print(json.dumps({
        "status": "DEVELOPMENT_COMPLETE_HELD_OUT_REMAINS_SEALED",
        "formal_case_count": 16,
        "formal_process_count": 32,
        "raw_file_count": 128,
        "source_manifest_sha256": sha(source_manifest_path),
        "source_aggregate_sha256": source_aggregate,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
