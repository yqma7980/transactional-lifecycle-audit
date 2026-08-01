from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
TAG = "P5_formal_20260731_fullFE_v1d"
RESULTS = ROOT / "results" / TAG
ORIGINAL_FINAL = RESULTS / "final"
ADJUDICATION = RESULTS / "adjudication_20260731"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json_new(path: Path, payload: Any) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True)
        stream.write("\n")


def normalized(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: normalized(item)
            for key, item in value.items()
            if key not in {
                "run_id",
                "wall_clock_timestamp",
                "absolute_path",
            }
        }
    if isinstance(value, list):
        return [normalized(item) for item in value]
    return value


def main() -> int:
    if not RESULTS.is_dir():
        raise SystemExit(f"missing formal result root: {RESULTS}")
    if ADJUDICATION.exists():
        raise SystemExit(f"refusing to overwrite: {ADJUDICATION}")

    original_execution_manifest_path = (
        ORIGINAL_FINAL / "execution_manifest.json"
    )
    original_matrix_summary_path = ORIGINAL_FINAL / "matrix_summary.json"
    original_manifest = json.loads(
        original_execution_manifest_path.read_text(encoding="utf-8")
    )
    original_summary = json.loads(
        original_matrix_summary_path.read_text(encoding="utf-8")
    )

    raw_mismatches: list[str] = []
    for item in original_manifest["files"]:
        path = RESULTS / item["path"]
        if (
            not path.is_file()
            or path.stat().st_size != int(item["bytes"])
            or sha256(path) != item["sha256"]
        ):
            raw_mismatches.append(item["path"])

    raw_aggregate_lines = [
        f"{item['path']}|{item['sha256']}"
        for item in sorted(
            original_manifest["files"],
            key=lambda row: row["path"],
        )
    ]
    raw_aggregate_sha256 = hashlib.sha256(
        "\n".join(raw_aggregate_lines).encode("utf-8")
    ).hexdigest()

    case_paths = sorted(RESULTS.rglob("case_result.json"))
    log_paths = sorted((RESULTS / "process_logs").rglob("*.log"))
    case_results = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in case_paths
    ]
    case_counts = Counter(row["case_id"] for row in case_results)
    case_manifest_mismatches: list[str] = []
    for case_path in case_paths:
        manifest_path = case_path.with_name("case_manifest.json")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for item in manifest["files"]:
            path = case_path.parent / item["path"]
            if (
                not path.is_file()
                or path.stat().st_size != int(item["bytes"])
                or sha256(path) != item["sha256"]
            ):
                case_manifest_mismatches.append(
                    path.relative_to(RESULTS).as_posix()
                )

    selections = json.loads(
        (ORIGINAL_FINAL / "selected_strengths.json").read_text(
            encoding="utf-8"
        )
    )
    duplicate = json.loads(
        (ORIGINAL_FINAL / "duplicate_comparison.json").read_text(
            encoding="utf-8"
        )
    )
    family_status = {
        row["family_id"]: row["status"]
        for row in duplicate["families"]
    }
    selected_families = sorted(
        family_id
        for family_id, record in selections["families"].items()
        if record["status"] == "SELECTED_PENDING_FRESH_VERIFICATION"
    )
    unsupported_families = sorted(
        family_id
        for family_id, record in selections["families"].items()
        if record["status"] != "SELECTED_PENDING_FRESH_VERIFICATION"
    )

    planned_process_budget = 90
    actual_process_count = len(case_results)
    skipped_runs = [
        f"P5-SCALE-{family_id}-DEV/run_{number}"
        for family_id in unsupported_families
        for number in range(16, 20)
    ]
    if planned_process_budget - actual_process_count != len(skipped_runs):
        raise RuntimeError("conditional process accounting is inconsistent")

    pair_checks: dict[str, bool] = {}
    for family_id in selected_families:
        case_id = f"P5-SCALE-{family_id}-DEV"
        records = {
            row["run_id"]: row
            for row in case_results
            if row["case_id"] == case_id
        }
        pair_checks[f"{family_id}_selected_pair"] = (
            normalized(records["run_16"])
            == normalized(records["run_17"])
        )
        pair_checks[f"{family_id}_next_pair"] = (
            normalized(records["run_18"])
            == normalized(records["run_19"])
        )

    corrected_summary = {
        "execution_tag": TAG,
        "formal_matrix_status": duplicate["status"],
        "evidence_status": "NOT_SUPPORTED_FULL_P5_MATRIX",
        "null_calibration": original_summary["null_calibration"],
        "null_confirmation": original_summary["null_confirmation"],
        "family_status": family_status,
        "selected_families": selected_families,
        "unsupported_families": unsupported_families,
        "planned_process_budget": planned_process_budget,
        "actual_process_count": actual_process_count,
        "conditionally_skipped_process_count": len(skipped_runs),
        "conditionally_skipped_runs": skipped_runs,
        "all_case_pass_flags_true": all(
            bool(row.get("pass_flag")) for row in case_results
        ),
        "all_case_values_finite": all(
            bool(row.get("all_values_finite", True))
            for row in case_results
        ),
        "fresh_pair_checks": pair_checks,
        "raw_evidence_file_count": len(original_manifest["files"]),
        "raw_evidence_aggregate_sha256": raw_aggregate_sha256,
        "original_execution_manifest_sha256": sha256(
            original_execution_manifest_path
        ),
        "original_matrix_summary_sha256": sha256(
            original_matrix_summary_path
        ),
        "original_hardcoded_process_count": original_summary[
            "formal_process_count"
        ],
        "process_count_erratum": (
            "The original runner reported the planned 90-process budget. "
            "The actual count is 82 because F01 and F02 were ineligible for "
            "their four conditional fresh-verification runs."
        ),
        "thresholds_or_frozen_science_changed": False,
        "abaqus_used": False,
        "production_model_used": False,
    }

    qa = {
        "status": (
            "PASS_POSTEXECUTION_QA_WITH_NOT_SUPPORTED_SCIENTIFIC_OUTCOME"
        ),
        "raw_manifest_mismatches": raw_mismatches,
        "case_manifest_mismatches": case_manifest_mismatches,
        "case_result_count": actual_process_count,
        "process_log_count": len(log_paths),
        "case_counts": dict(sorted(case_counts.items())),
        "failed_case_pass_flags": [
            f"{row['case_id']}/{row['run_id']}"
            for row in case_results
            if not row.get("pass_flag")
        ],
        "nonfinite_cases": [
            f"{row['case_id']}/{row['run_id']}"
            for row in case_results
            if not row.get("all_values_finite", True)
        ],
        "fresh_pair_checks": pair_checks,
        "original_raw_evidence_immutable": (
            not raw_mismatches and not case_manifest_mismatches
        ),
        "original_summary_preserved": True,
        "old_execution_tags_preserved": all(
            (ROOT / "results" / tag).is_dir()
            for tag in (
                "P5_formal_20260731_fullFE_v1",
                "P5_formal_20260731_fullFE_v1a",
                "P5_formal_20260731_fullFE_v1b",
                "P5_formal_20260731_fullFE_v1c",
            )
        ),
    }
    if (
        raw_mismatches
        or case_manifest_mismatches
        or actual_process_count != 82
        or len(log_paths) != 82
        or not all(corrected_summary["fresh_pair_checks"].values())
        or not corrected_summary["all_case_pass_flags_true"]
        or not corrected_summary["all_case_values_finite"]
    ):
        raise RuntimeError("P5 v1d postexecution QA failed")

    ADJUDICATION.mkdir(parents=False, exist_ok=False)
    summary_path = ADJUDICATION / "matrix_summary_corrected.json"
    qa_path = ADJUDICATION / "postexecution_QA.json"
    report_path = ADJUDICATION / "P5_formal_v1d_result_report.md"
    write_json_new(summary_path, corrected_summary)
    write_json_new(qa_path, qa)

    report = f"""# P5 formal matrix result: {TAG}

Status: `NOT_SUPPORTED_FULL_P5_MATRIX`

## Decision

The frozen P5 execution completed all unconditional processes and all
conditionally authorized verification processes.  The full matrix is not a
PASS: F01 and F02 returned `NOT_SUPPORTED_DISTINCTIVE_REGION_EMPTY`.  F05 and
F07 independently passed their frozen fresh-process verification pairs.

## Gate results

- Null calibration: `{corrected_summary['null_calibration']}`.
- Null confirmation: `{corrected_summary['null_confirmation']}`.
- F01: `{family_status['F01']}`.
- F02: `{family_status['F02']}`.
- F05: `{family_status['F05']}`; selected indices 5 and 6.
- F07: `{family_status['F07']}`; selected indices 5 and 6.
- All 82 written case results have `pass_flag=true` and finite values.
- All four F05/F07 fresh-process pairs are exactly repeatable after removing
  run-specific fields.

## Process accounting

The frozen matrix declared a maximum budget of 90 processes.  The actual count
is 82: 14 null processes, 60 one-pass strength-sweep processes, and 8 fresh
verification processes for F05/F07.  F01/F02 each skipped four conditional
verification processes because no strength pair was eligible.  The original
runner's hard-coded `formal_process_count=90` is preserved as raw evidence and
superseded for reporting by `matrix_summary_corrected.json`.

## Evidence integrity

The original execution manifest covers {len(original_manifest['files'])} raw
files.  Their path/hash aggregate is
`{raw_aggregate_sha256}`.  All original manifest and case-manifest hashes were
re-read successfully; no prior tag or failure record was overwritten.

## Claim boundary

This result does not establish a full P5 scaled-threshold success.  It supports
bounded family-level fresh-process evidence for F05 and F07, while F01/F02
remain `NOT_SUPPORTED_DISTINCTIVE_REGION_EMPTY`.  No Abaqus, production UEL,
GitHub, Zenodo, DOI, manuscript, or physical-model claim is changed by this
execution.
"""
    report_path.write_text(report, encoding="utf-8")

    delta_files = [
        ROOT / "src" / "p5_fe_history_gatefix.py",
        ROOT / "src" / "p5_case_executor_gatefix.py",
        ROOT / "run_p5_gpfix_v4.py",
        ROOT / "run_p5_matrix_gpfix_v4.py",
        ROOT / "tests" / "test_p5_gateaware_sweep.py",
        ROOT / "tests" / "test_p5_gateaware_executor.py",
        ROOT / "P5_mechanics_gate_recording_erratum_20260731.md",
        ROOT / "postprocess_p5_v1d.py",
    ]
    post_manifest = {
        "execution_tag": TAG,
        "original_evidence": {
            "execution_manifest": {
                "path": original_execution_manifest_path.relative_to(
                    ROOT
                ).as_posix(),
                "sha256": sha256(original_execution_manifest_path),
            },
            "matrix_summary": {
                "path": original_matrix_summary_path.relative_to(
                    ROOT
                ).as_posix(),
                "sha256": sha256(original_matrix_summary_path),
            },
            "raw_file_count": len(original_manifest["files"]),
            "raw_aggregate_sha256": raw_aggregate_sha256,
        },
        "adjudication_outputs": [
            {
                "path": path.relative_to(ROOT).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
            for path in (summary_path, qa_path, report_path)
        ],
        "implementation_delta_files": [
            {
                "path": path.relative_to(ROOT).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
            for path in delta_files
        ],
        "manifest_self_hash_embedded": False,
    }
    write_json_new(
        ADJUDICATION / "postexecution_manifest.json",
        post_manifest,
    )
    print(json.dumps(corrected_summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
