from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results" / "heldout"
FINAL = RESULTS / "final"
CASES = (
    "P5B-DETECT-05",
    "P5B-INVALID-05",
    "P5B-NS-05",
    "P5B-PASS-05",
)
RUNS = ("run_1", "run_2")
RUN_FILES = {
    "case_result.json",
    "runtime_observation.json",
    "event_ledger.json",
    "case_manifest.json",
}
EXPECTED = {
    "P5B-DETECT-05": "DETECT_LIFECYCLE_DRIFT",
    "P5B-INVALID-05": "INVALID",
    "P5B-NS-05": "NOT_SUPPORTED",
    "P5B-PASS-05": "PASS_INVARIANT",
}
EXPECTED_RUN_COUNTS = {
    "PASS_INVARIANT": 2,
    "DETECT_LIFECYCLE_DRIFT": 2,
    "INVALID": 2,
    "NOT_SUPPORTED": 2,
}
P5B2_HASHES = {
    "00_frozen_inputs/P5B2/P5B2_HELDOUT_ACTIVATION_MANIFEST.json":
        "c47ff42e8abfdf74874d6c4a2a4f5554a77a407a79ed012fe3bd3660e0609e5b",
    "00_frozen_inputs/P5B2/P5B2_heldout_case_matrix.csv":
        "453240fca5509bdb031b0a3b796c12bf5b4e35c102e1d457fc58869a65c8d055",
    "00_frozen_inputs/P5B2/P5B2_SOURCE_MANIFEST.json":
        "b05e33850c7073c1d443804ad908eb194d2c1372b0f133b9136cd983a6a78f37",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_new(path: Path, payload: Any) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True, ensure_ascii=True)
        handle.write("\n")


def write_text_new(path: Path, value: str) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(value.rstrip() + "\n")


def verify_manifest_rows(manifest_path: Path, key: str) -> list[str]:
    errors: list[str] = []
    payload = read_json(manifest_path)
    for row in payload[key]:
        path = ROOT / row["relative_path"]
        if not path.is_file():
            errors.append("missing protected file: " + row["relative_path"])
        elif sha256(path) != row["sha256"] or path.stat().st_size != row["bytes"]:
            errors.append("protected file drift: " + row["relative_path"])
    return errors


def case_specific_checks(case_id: str, result: dict[str, Any], observation: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    measurements = observation["measurements"]
    if case_id == "P5B-PASS-05":
        if measurements.get("accepted_field_delta") != 0.0:
            errors.append("PASS-05 accepted-field delta is nonzero")
        if measurements.get("postcommit_output_after_commit") is not True:
            errors.append("PASS-05 output ordering failed")
        if measurements.get("postcommit_output_candidate_matches_accepted_candidate") is not True:
            errors.append("PASS-05 output candidate provenance failed")
    elif case_id == "P5B-DETECT-05":
        if measurements.get("output_provenance_violation") is not True:
            errors.append("DETECT-05 output provenance signal absent")
        if measurements.get("faulty_output_candidate_matches_rejected") is not True:
            errors.append("DETECT-05 rejected candidate source absent")
        if result.get("active_signals") != ["output_provenance_violation"]:
            errors.append("DETECT-05 active signal drift")
    elif case_id == "P5B-INVALID-05":
        if result.get("lifecycle_evaluated") is not False:
            errors.append("INVALID-05 reached lifecycle evaluation")
        if result.get("mismatch_fields") != ["environment_hash"]:
            errors.append("INVALID-05 mismatch field drift")
        if measurements.get("no_fe_solve_executed_for_eligibility_audit") is not True:
            errors.append("INVALID-05 unexpectedly ran FE solve")
    elif case_id == "P5B-NS-05":
        if result.get("applicability_evaluated") is not True:
            errors.append("NS-05 applicability was not evaluated")
        if result.get("lifecycle_evaluated") is not False:
            errors.append("NS-05 reached lifecycle evaluation")
        if measurements.get("no_subject_solve_executed_for_capability_audit") is not True:
            errors.append("NS-05 unexpectedly ran subject solve")
    return errors


def main() -> int:
    errors: list[str] = []
    p5b1_manifest = ROOT / "P5B1_SOURCE_MANIFEST.json"
    errors.extend(verify_manifest_rows(p5b1_manifest, "files"))
    for relative, expected in P5B2_HASHES.items():
        path = ROOT / relative
        if not path.is_file() or sha256(path) != expected:
            errors.append("P5B.2 frozen hash drift: " + relative)

    implementation = read_json(ROOT / "P5B3_IMPLEMENTATION_MANIFEST.json")
    if implementation["status"] != "IMPLEMENTED_UNIT_TESTED_READY_FOR_AUTHORIZED_EXECUTION":
        errors.append("implementation pre-execution status drift")
    for relative, row in implementation["implementation_files"].items():
        path = ROOT / relative
        if not path.is_file() or sha256(path) != row["sha256"] or path.stat().st_size != row["bytes"]:
            errors.append("P5B.3 implementation drift: " + relative)

    if not RESULTS.is_dir():
        errors.append("held-out results root is absent")
        actual_cases: tuple[str, ...] = ()
    else:
        actual_cases = tuple(sorted(
            path.name for path in RESULTS.iterdir()
            if path.is_dir() and path.name != "final"
        ))
    if actual_cases != CASES:
        errors.append("held-out case directory set differs from freeze")

    duplicates: list[dict[str, Any]] = []
    raw_files: list[dict[str, Any]] = []
    case_rows: list[dict[str, Any]] = []
    verdicts: Counter[str] = Counter()
    subjects: Counter[str] = Counter()
    for case_id in CASES:
        pair: list[dict[str, dict[str, Any]]] = []
        for run_id in RUNS:
            run_dir = RESULTS / case_id / run_id
            if not run_dir.is_dir():
                errors.append(f"missing run directory: {case_id}/{run_id}")
                continue
            actual_files = {p.name for p in run_dir.iterdir() if p.is_file()}
            if actual_files != RUN_FILES:
                errors.append(f"unexpected file set: {case_id}/{run_id}")
                continue
            payloads = {name: read_json(run_dir / name) for name in sorted(RUN_FILES)}
            result = payloads["case_result.json"]
            observation = payloads["runtime_observation.json"]
            ledger = payloads["event_ledger.json"]
            manifest = payloads["case_manifest.json"]
            observed = result["four_way_verdict"]
            verdicts[observed] += 1
            subjects[manifest["subject_id"]] += 1
            if observed != EXPECTED[case_id] or manifest["observed_verdict"] != observed:
                errors.append(f"frozen verdict failed: {case_id}/{run_id}")
            if result["pass_flag"] is not True or manifest["pass_flag"] is not True:
                errors.append(f"pass flag failed: {case_id}/{run_id}")
            fingerprint = observation["semantic_fingerprint"]
            if ledger["semantic_fingerprint"] != fingerprint:
                errors.append(f"ledger fingerprint failed: {case_id}/{run_id}")
            if manifest["runtime_semantic_fingerprint"] != fingerprint:
                errors.append(f"manifest fingerprint failed: {case_id}/{run_id}")
            for name, row in manifest["outputs"].items():
                path = run_dir / name
                if not path.is_file() or sha256(path) != row["sha256"] or path.stat().st_size != row["bytes"]:
                    errors.append(f"output integrity failed: {case_id}/{run_id}/{name}")
            errors.extend(
                f"{case_id}/{run_id}: {message}"
                for message in case_specific_checks(case_id, result, observation)
            )
            for path in sorted(run_dir.iterdir()):
                if path.is_file():
                    raw_files.append(
                        {
                            "relative_path": path.relative_to(ROOT).as_posix(),
                            "sha256": sha256(path),
                            "bytes": path.stat().st_size,
                        }
                    )
            pair.append(payloads)

        if len(pair) != 2:
            continue
        left, right = pair
        left_result = {k: v for k, v in left["case_result.json"].items() if k != "run_id"}
        right_result = {k: v for k, v in right["case_result.json"].items() if k != "run_id"}
        checks = {
            "case_result_equal_after_run_id_normalization": left_result == right_result,
            "runtime_semantic_fingerprint_equal":
                left["runtime_observation.json"]["semantic_fingerprint"]
                == right["runtime_observation.json"]["semantic_fingerprint"],
            "event_ledger_semantic_fingerprint_equal":
                left["event_ledger.json"]["semantic_fingerprint"]
                == right["event_ledger.json"]["semantic_fingerprint"],
            "input_hashes_equal":
                left["case_manifest.json"]["inputs"]
                == right["case_manifest.json"]["inputs"],
            "verdict_equal":
                left["case_result.json"]["four_way_verdict"]
                == right["case_result.json"]["four_way_verdict"],
            "both_pass_flag_true":
                left["case_result.json"]["pass_flag"]
                and right["case_result.json"]["pass_flag"],
        }
        duplicate_pass = all(checks.values())
        if not duplicate_pass:
            errors.append("duplicate gate failed: " + case_id)
        duplicates.append(
            {
                "case_id": case_id,
                **checks,
                "run_1_semantic_fingerprint":
                    left["runtime_observation.json"]["semantic_fingerprint"],
                "run_2_semantic_fingerprint":
                    right["runtime_observation.json"]["semantic_fingerprint"],
                "observed_verdict": left["case_result.json"]["four_way_verdict"],
                "duplicate_gate_pass": duplicate_pass,
            }
        )
        case_rows.append(
            {
                "case_id": case_id,
                "subject_id": left["case_manifest.json"]["subject_id"],
                "expected_verdict": EXPECTED[case_id],
                "observed_verdict": left["case_result.json"]["four_way_verdict"],
                "formal_repetitions": 2,
                "all_repetitions_passed": checks["both_pass_flag_true"],
                "duplicate_gate_pass": duplicate_pass,
            }
        )

    if len(raw_files) != 32:
        errors.append(f"raw file count {len(raw_files)} != 32")
    if dict(verdicts) != EXPECTED_RUN_COUNTS:
        errors.append("held-out verdict distribution differs from freeze")
    if errors:
        raise SystemExit("\n".join(errors))
    if FINAL.exists():
        raise FileExistsError("held-out final evidence directory already exists")
    FINAL.mkdir(parents=False, exist_ok=False)

    duplicate_path = FINAL / "P5B3_heldout_duplicate_comparison.json"
    write_json_new(
        duplicate_path,
        {
            "schema_version": "JSS-P5B3-HELDOUT-DUPLICATE-COMPARISON-1.0",
            "status": "PASS",
            "case_count": 4,
            "fresh_process_repetitions_per_case": 2,
            "all_duplicate_gates_passed": True,
            "comparisons": duplicates,
        },
    )
    raw_files = sorted(raw_files, key=lambda row: row["relative_path"])
    raw_aggregate = hashlib.sha256(
        "\n".join(
            f"{row['relative_path']}|{row['sha256']}" for row in raw_files
        ).encode("utf-8")
    ).hexdigest()
    raw_manifest_path = FINAL / "P5B3_heldout_raw_manifest.json"
    write_json_new(
        raw_manifest_path,
        {
            "schema_version": "JSS-P5B3-HELDOUT-RAW-MANIFEST-1.0",
            "status": "RAW_EVIDENCE_FROZEN",
            "formal_case_count": 4,
            "formal_process_count": 8,
            "raw_file_count": 32,
            "aggregate_spec": "sorted <relative_path>|<sha256>, UTF-8, LF, no final newline",
            "aggregate_sha256": raw_aggregate,
            "files": raw_files,
            "manifest_self_hash_embedded": False,
        },
    )
    development = read_json(
        ROOT / "results" / "development" / "final" / "P5B1_development_final_summary.json"
    )
    if development["formal_case_count"] != 16 or development["formal_process_count"] != 32:
        raise SystemExit("development summary drift during held-out finalization")
    summary_path = FINAL / "P5B3_heldout_final_summary.json"
    write_json_new(
        summary_path,
        {
            "schema_version": "JSS-P5B3-HELDOUT-SUMMARY-1.0",
            "status": "HELD_OUT_COMPLETE_FROZEN_MATRIX_COMPLETE",
            "evidence_status": "OBSERVED-P5B-HELDOUT",
            "design_version": "JSS-P5B.0",
            "implementation_version": "JSS-P5B-IMPL-1.0a",
            "heldout_execution_revision": "JSS-P5B3-HELDOUT-1.0",
            "formal_case_count": 4,
            "formal_process_count": 8,
            "fresh_process_repetitions_per_case": 2,
            "processes_per_repetition": 1,
            "threads_per_process": 1,
            "all_cases_passed_frozen_verdict": True,
            "all_duplicate_gates_passed": True,
            "verdict_counts_by_run": EXPECTED_RUN_COUNTS,
            "subject_counts_by_run": dict(sorted(subjects.items())),
            "case_results": case_rows,
            "combined_p5b_case_count": 20,
            "combined_p5b_process_count": 40,
            "combined_verdict_counts_by_run": {
                "PASS_INVARIANT": 10,
                "DETECT_LIFECYCLE_DRIFT": 10,
                "INVALID": 10,
                "NOT_SUPPORTED": 10,
            },
            "abaqus_used": False,
            "production_project_used": False,
            "performance_evaluated": False,
            "does_not_establish_detection_rate": True,
            "does_not_establish_false_positive_rate": True,
            "does_not_establish_general_solver_safety": True,
        },
    )
    report_path = FINAL / "P5B3_heldout_result_report.md"
    lines = [
        "# P5B.3 held-out formal execution report",
        "",
        "Status: HELD_OUT_COMPLETE_FROZEN_MATRIX_COMPLETE.",
        "",
        "Four predeclared held-out cases were each executed in two fresh,",
        "single-process, single-thread repetitions. All eight runs matched the",
        "frozen four-way verdict, and every duplicate semantic gate passed.",
        "",
        "| Case | Subject | Expected and observed verdict | Runs | Duplicate |",
        "|---|---|---|---:|---|",
    ]
    lines.extend(
        f"| {row['case_id']} | {row['subject_id']} | {row['observed_verdict']} | 2/2 | PASS |"
        for row in case_rows
    )
    lines.extend(
        (
            "",
            "## Evidence boundary",
            "",
            "This package establishes the outcomes of four frozen held-out cases",
            "under the existing P5B adjudication contract. INVALID and",
            "NOT_SUPPORTED are bounded decisions rather than failed solves.",
            "The results do not estimate population detection or false-positive",
            "rates, performance, thread safety, Abaqus behavior, production-model",
            "readiness, or general solver safety.",
        )
    )
    write_text_new(report_path, "\n".join(lines))

    execution_manifest_path = FINAL / "P5B3_heldout_execution_manifest.json"
    write_json_new(
        execution_manifest_path,
        {
            "schema_version": "JSS-P5B3-HELDOUT-EXECUTION-MANIFEST-1.0",
            "status": "HELD_OUT_COMPLETE_FROZEN_MATRIX_COMPLETE",
            "created_date": date.today().isoformat(),
            "raw_manifest_sha256": sha256(raw_manifest_path),
            "duplicate_comparison_sha256": sha256(duplicate_path),
            "final_summary_sha256": sha256(summary_path),
            "result_report_sha256": sha256(report_path),
            "authorization_sha256": sha256(ROOT / "P5B3_HELDOUT_EXECUTION_AUTHORIZATION.json"),
            "implementation_manifest_sha256": sha256(ROOT / "P5B3_IMPLEMENTATION_MANIFEST.json"),
            "p5b2_activation_sha256": P5B2_HASHES[
                "00_frozen_inputs/P5B2/P5B2_HELDOUT_ACTIVATION_MANIFEST.json"
            ],
            "no_abaqus_execution": True,
            "no_production_model_execution": True,
            "no_post_hoc_threshold_or_case_change": True,
            "manifest_self_hash_embedded": False,
        },
    )
    final_qa_path = ROOT / "P5B3_HELDOUT_FINAL_QA.md"
    write_text_new(
        final_qa_path,
        "\n".join(
            (
                "# P5B.3 held-out final QA",
                "",
                "Status: PASS_HELD_OUT_COMPLETE_FROZEN_MATRIX_COMPLETE.",
                "",
                "- Held-out cases: 4/4.",
                "- Fresh-process runs: 8/8.",
                "- Raw result files: 32/32.",
                "- Frozen verdict matches: 8/8.",
                "- Duplicate semantic gates: 4/4.",
                "- Held-out run verdicts: 2 PASS, 2 DETECT, 2 INVALID, 2 NOT_SUPPORTED.",
                "- Combined P5B matrix: 20 cases and 40 fresh processes.",
                "- Protected P5B.1 and P5B.2 evidence mismatches: 0.",
                "- Abaqus and production models were not used.",
            )
        ),
    )
    source_manifest_path = ROOT / "P5B3_SOURCE_MANIFEST.json"
    source_rows = []
    for path in sorted(p for p in ROOT.rglob("*") if p.is_file()):
        if path != source_manifest_path:
            source_rows.append(
                {
                    "relative_path": path.relative_to(ROOT).as_posix(),
                    "sha256": sha256(path),
                    "bytes": path.stat().st_size,
                }
            )
    source_aggregate = hashlib.sha256(
        "\n".join(
            f"{row['relative_path']}|{row['sha256']}" for row in source_rows
        ).encode("utf-8")
    ).hexdigest()
    write_json_new(
        source_manifest_path,
        {
            "schema_version": "JSS-P5B3-SOURCE-MANIFEST-1.0",
            "package_status": "HELD_OUT_COMPLETE_FROZEN_MATRIX_COMPLETE",
            "file_count": len(source_rows),
            "aggregate_spec": "sorted <relative_path>|<sha256>, UTF-8, LF, no final newline",
            "aggregate_sha256": source_aggregate,
            "files": source_rows,
            "manifest_self_hash_embedded": False,
        },
    )
    print(
        json.dumps(
            {
                "status": "HELD_OUT_COMPLETE_FROZEN_MATRIX_COMPLETE",
                "formal_case_count": 4,
                "formal_process_count": 8,
                "raw_file_count": 32,
                "raw_aggregate_sha256": raw_aggregate,
                "source_manifest_sha256": sha256(source_manifest_path),
                "source_aggregate_sha256": source_aggregate,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
