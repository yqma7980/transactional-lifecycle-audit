from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results" / "P4d2_formal_20260731"
LOGS = ROOT / "formal_execution_logs" / "P4d2_formal_20260731"
FINAL = RESULTS / "final"
PAIRED_CASES = ("P4D-REF-01", "P4D-CONST-01", "P4D-SAFE-DIR-01")
EXPECTED_RUNS = {
    "P4D-REF-01": ("run_1", "run_2"),
    "P4D-CONST-01": ("run_1", "run_2"),
    "P4D-SAFE-DIR-01": ("run_1", "run_2"),
    "P4D-SAFE-LS-01": ("run_1",),
}
EXPECTED_VERDICTS = {
    "P4D-REF-01": (True, "REFERENCE_GATE_PASS"),
    "P4D-CONST-01": (True, "CONSTITUTIVE_ORACLE_PASS"),
    "P4D-SAFE-DIR-01": (True, "PASS_REPLAY_INVARIANCE_WITHIN_TESTED_CLASS"),
    "P4D-SAFE-LS-01": (False, "P4D-SAFE-LS-01_CONTRACT_FAIL"),
}
UNSTARTED_CASES = (
    "P4D-SAFE-RT-01",
    "P4D-SAFE-RS-01",
    "P4D-NC-CACHE-01",
    "P4D-NC-OUTPUT-01",
    "P4D-VER-01",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def normalize(value: object) -> object:
    if isinstance(value, dict):
        return {key: normalize(item) for key, item in value.items() if key != "run_id"}
    if isinstance(value, list):
        return [normalize(item) for item in value]
    if isinstance(value, str):
        return value.replace("run_1", "<run>").replace("run_2", "<run>")
    return value


def compare_json(left: Path, right: Path) -> bool:
    return normalize(json.loads(left.read_text(encoding="utf-8"))) == normalize(
        json.loads(right.read_text(encoding="utf-8"))
    )


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        return [dict(row) for row in csv.DictReader(stream)]


def compare_csv(left: Path, right: Path) -> bool:
    return normalize(read_csv(left)) == normalize(read_csv(right))


def compare_npz(left: Path, right: Path) -> bool:
    with np.load(left, allow_pickle=False) as a, np.load(right, allow_pickle=False) as b:
        if sorted(a.files) != sorted(b.files):
            return False
        return all(
            a[key].dtype == b[key].dtype
            and a[key].shape == b[key].shape
            and np.array_equal(a[key], b[key])
            for key in a.files
        )


def semantic_file_equal(left: Path, right: Path) -> bool:
    if left.suffix == ".json":
        return compare_json(left, right)
    if left.suffix == ".csv":
        return compare_csv(left, right)
    if left.suffix == ".npz":
        return compare_npz(left, right)
    return left.read_bytes() == right.read_bytes()


def verify_case_manifest(run_dir: Path) -> dict[str, object]:
    manifest_path = run_dir / "case_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    declared = {item["path"]: item for item in manifest["files"]}
    actual = {
        path.relative_to(run_dir).as_posix()
        for path in run_dir.rglob("*")
        if path.is_file() and path.name != "case_manifest.json"
    }
    if set(declared) != actual:
        raise RuntimeError(f"manifest inventory mismatch: {run_dir}")
    for relative, item in declared.items():
        path = run_dir / relative
        if path.stat().st_size != item["bytes"] or sha256(path) != item["sha256"]:
            raise RuntimeError(f"manifest hash mismatch: {path}")
    return manifest


def compare_pair(case_id: str) -> dict[str, object]:
    left = RESULTS / case_id / "run_1"
    right = RESULTS / case_id / "run_2"
    left_files = {
        path.relative_to(left).as_posix()
        for path in left.rglob("*")
        if path.is_file() and path.name != "case_manifest.json"
    }
    right_files = {
        path.relative_to(right).as_posix()
        for path in right.rglob("*")
        if path.is_file() and path.name != "case_manifest.json"
    }
    file_results = []
    for relative in sorted(left_files | right_files):
        present_both = relative in left_files and relative in right_files
        equal = present_both and semantic_file_equal(left / relative, right / relative)
        file_results.append(
            {"path": relative, "present_in_both": present_both, "semantic_equal": equal}
        )
    return {
        "case_id": case_id,
        "run_1": "run_1",
        "run_2": "run_2",
        "inventory_equal": left_files == right_files,
        "all_semantic_files_equal": all(item["semantic_equal"] for item in file_results),
        "file_comparisons": file_results,
    }


def raw_file_records() -> list[dict[str, object]]:
    paths = [path for path in RESULTS.rglob("*") if path.is_file() and FINAL not in path.parents]
    paths.extend(path for path in LOGS.rglob("*") if path.is_file())
    paths.extend(
        ROOT / name
        for name in (
            "P4d2_formal_execution_freeze_20260731.json",
            "run_p4d2_formal_matrix.ps1",
        )
    )
    return [
        {
            "path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        for path in sorted(paths, key=lambda item: item.relative_to(ROOT).as_posix())
    ]


def main() -> int:
    if FINAL.exists():
        raise SystemExit(f"refusing to overwrite {FINAL}")
    progress = json.loads((LOGS / "formal_matrix_progress.json").read_text(encoding="utf-8"))
    if progress["status"] != "STOPPED_ON_FAILURE" or progress["completed_process_count"] != 6:
        raise RuntimeError("formal progress does not match the frozen stop state")

    actual_case_dirs = sorted(path.name for path in RESULTS.iterdir() if path.is_dir())
    if actual_case_dirs != sorted(EXPECTED_RUNS):
        raise RuntimeError(f"unexpected formal case directories: {actual_case_dirs}")

    run_results = []
    for case_id, run_ids in EXPECTED_RUNS.items():
        actual_runs = sorted(path.name for path in (RESULTS / case_id).iterdir() if path.is_dir())
        if actual_runs != sorted(run_ids):
            raise RuntimeError(f"unexpected run directories for {case_id}: {actual_runs}")
        for run_id in run_ids:
            run_dir = RESULTS / case_id / run_id
            verify_case_manifest(run_dir)
            result = json.loads((run_dir / "case_result.json").read_text(encoding="utf-8"))
            expected_pass, expected_observed_verdict = EXPECTED_VERDICTS[case_id]
            if bool(result["pass_flag"]) != expected_pass:
                raise RuntimeError(f"unexpected pass flag: {case_id}/{run_id}")
            if result["primary_verdict"] != expected_observed_verdict:
                raise RuntimeError(f"unexpected observed verdict: {case_id}/{run_id}")
            if result.get("formal_execution") != 1:
                raise RuntimeError(f"formal flag missing: {case_id}/{run_id}")
            run_results.append(
                {
                    "case_id": case_id,
                    "run_id": run_id,
                    "pass_flag": bool(result["pass_flag"]),
                    "primary_verdict": result["primary_verdict"],
                    "expected_primary_verdict": result["expected_primary_verdict"],
                    "case_result_sha256": sha256(run_dir / "case_result.json"),
                    "case_manifest_sha256": sha256(run_dir / "case_manifest.json"),
                }
            )

    failed = json.loads(
        (RESULTS / "P4D-SAFE-LS-01" / "run_1" / "case_result.json").read_text(encoding="utf-8")
    )
    line_search = failed["native_line_search"]
    expected_line_search = {
        "candidate_event_count": 29,
        "candidate_to_python_packet_correlation_count": 29,
        "candidate_to_python_packet_correlation_present": 1,
        "postcheck_flags_read_only": 1,
        "selected_event_count": 29,
        "structured_unselected_candidate_count": 0,
        "structured_unselected_candidate_present": 0,
    }
    if line_search != expected_line_search:
        raise RuntimeError("line-search failure packet changed during finalization")
    if failed["mechanics_gates_pass"] != 1 or failed["direct_final_field_parity"] != 1:
        raise RuntimeError("line-search mechanics/parity packet is inconsistent")

    duplicate = {
        "schema_version": "CMAME-P4D2-FORMAL-DUPLICATE-1.0",
        "comparison_rule": "remove run_id semantics only; compare JSON/CSV semantically and NPZ arrays exactly",
        "cases": [compare_pair(case_id) for case_id in PAIRED_CASES],
    }
    duplicate["all_completed_pairs_equal"] = all(
        item["inventory_equal"] and item["all_semantic_files_equal"] for item in duplicate["cases"]
    )

    raw_manifest = {
        "schema_version": "CMAME-P4D2-FORMAL-RAW-MANIFEST-1.0",
        "formal_matrix_complete": False,
        "raw_run_count": 7,
        "raw_files": raw_file_records(),
        "manifest_self_hash_embedded": False,
    }

    case_status = [
        {"case_id": case_id, "status": "PASS_TWO_FRESH_PROCESS", "formal_runs": 2}
        for case_id in PAIRED_CASES
    ]
    case_status.append(
        {
            "case_id": "P4D-SAFE-LS-01",
            "status": "NOT_SUPPORTED_BY_FROZEN_HISTORY",
            "formal_runs": 1,
            "raw_primary_verdict": "P4D-SAFE-LS-01_CONTRACT_FAIL",
            "reason": "no structured PETSc-native unselected line-search candidate",
        }
    )
    case_status.extend(
        {"case_id": case_id, "status": "NOT_STARTED_PREREQUISITE_STOP", "formal_runs": 0}
        for case_id in UNSTARTED_CASES
    )
    summary = {
        "schema_version": "CMAME-P4D2-FORMAL-STOP-SUMMARY-1.0",
        "final_status": "STOPPED_NOT_SUPPORTED_BY_FROZEN_HISTORY",
        "formal_matrix_complete": False,
        "planned_case_count": 9,
        "planned_process_count": 18,
        "raw_run_count": 7,
        "passed_process_count": 6,
        "failed_or_not_supported_process_count": 1,
        "unstarted_process_count": 11,
        "completed_two_run_case_count": 3,
        "all_completed_pairs_equal": duplicate["all_completed_pairs_equal"],
        "failed_case_id": "P4D-SAFE-LS-01",
        "failed_run_id": "run_1",
        "raw_primary_verdict": "P4D-SAFE-LS-01_CONTRACT_FAIL",
        "frozen_protocol_adjudication": "NOT_SUPPORTED_BY_FROZEN_HISTORY",
        "candidate_event_count": 29,
        "selected_event_count": 29,
        "structured_unselected_candidate_count": 0,
        "candidate_to_python_packet_correlation_count": 29,
        "mechanics_gates_pass": True,
        "direct_final_field_parity": True,
        "all_observed_values_finite": all(
            attempt["mechanics"]["all_values_finite"] == 1 for attempt in failed["attempts"]
        ),
        "case_status": case_status,
        "run_results": run_results,
        "evidence_boundary": {
            "observed_p4d_matrix_pass": False,
            "native_rejected_callback_coverage_observed": False,
            "abaqus_or_production_evidence": False,
            "manuscript_claim_expansion_authorized": False,
            "raw_failure_may_not_be_relabelled_as_pass": True,
        },
    }

    FINAL.mkdir(parents=False)
    duplicate_path = FINAL / "p4d2_duplicate_run_comparison.json"
    raw_manifest_path = FINAL / "p4d2_formal_raw_manifest.json"
    summary_path = FINAL / "p4d2_formal_stop_summary.json"
    write_json(duplicate_path, duplicate)
    write_json(raw_manifest_path, raw_manifest)
    write_json(summary_path, summary)

    report = f"""# P4d.2 formal execution stop report

Final status: `STOPPED_NOT_SUPPORTED_BY_FROZEN_HISTORY`

## Execution outcome

- The frozen matrix planned 9 cases and 18 fresh-process runs.
- `P4D-REF-01`, `P4D-CONST-01`, and `P4D-SAFE-DIR-01` each passed in two fresh processes.
- Their normalized semantic outputs are equal: `{str(duplicate['all_completed_pairs_equal']).lower()}`.
- `P4D-SAFE-LS-01/run_1` completed the load path with finite values, mechanics gates, and direct-field parity, but returned `P4D-SAFE-LS-01_CONTRACT_FAIL`.
- The PETSc C observer recorded 29 candidates and correlated all 29 with Python packets. All 29 were selected; the structured unselected-candidate count was 0.
- Frozen lifecycle gate L3 therefore adjudicates the history as `NOT_SUPPORTED_BY_FROZEN_HISTORY` and requires a stop without changing load, tangent, or line-search settings.
- `P4D-SAFE-LS-01/run_2` and all dependent cases were not started.

## Scientific boundary

This result is not an `OBSERVED-P4D` matrix pass. It does not establish native rejected-callback coverage, Abaqus behavior, production readiness, thread safety, two-way coupling, or CO2 application validity. The raw contract-failure label is preserved and is not rewritten as a passing verdict.

## Evidence files

- `p4d2_formal_stop_summary.json`
- `p4d2_duplicate_run_comparison.json`
- `p4d2_formal_raw_manifest.json`
- `p4d2_formal_execution_manifest.json`
"""
    report_path = FINAL / "p4d2_formal_stop_report.md"
    report_path.write_text(report, encoding="utf-8")

    execution_manifest = {
        "schema_version": "CMAME-P4D2-FORMAL-EXECUTION-MANIFEST-1.0",
        "final_status": summary["final_status"],
        "raw_evidence_preserved": True,
        "benchmark_rerun_after_failure": False,
        "threshold_or_oracle_changed": False,
        "formal_execution_freeze_sha256": sha256(ROOT / "P4d2_formal_execution_freeze_20260731.json"),
        "matrix_runner_sha256": sha256(ROOT / "run_p4d2_formal_matrix.ps1"),
        "implementation_source_manifest_sha256": sha256(ROOT / "P4d2_source_manifest.json"),
        "formal_progress_sha256": sha256(LOGS / "formal_matrix_progress.json"),
        "derived_files": [
            {"path": path.name, "bytes": path.stat().st_size, "sha256": sha256(path)}
            for path in (duplicate_path, raw_manifest_path, summary_path, report_path)
        ],
        "manifest_self_hash_embedded": False,
    }
    write_json(FINAL / "p4d2_formal_execution_manifest.json", execution_manifest)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
