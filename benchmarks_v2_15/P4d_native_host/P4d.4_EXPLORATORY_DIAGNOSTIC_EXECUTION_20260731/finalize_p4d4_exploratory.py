from __future__ import annotations

import hashlib
import json
import pathlib
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parent
P4D_ROOT = ROOT.parent
P4D2 = P4D_ROOT / "P4d.2_FULL_IMPLEMENTATION_20260731"
P4D3 = P4D_ROOT / "P4d.3_NATIVE_LINESEARCH_POSTMORTEM_20260731"
RESULTS = ROOT / "results" / "P4d4_exploratory_20260731"
FINAL = RESULTS / "final"
CASES = (
    "P4D4-DIAG-LS-01",
    "P4D4-DIAG-LS-02",
    "P4D4-DIAG-LS-03",
)
TARGETS = {
    "P4D4-DIAG-LS-01": 0.20,
    "P4D4-DIAG-LS-02": 0.24,
    "P4D4-DIAG-LS-03": 0.28,
}
HELDOUT = {0.20: 0.22, 0.24: 0.26, 0.28: 0.30}


def protected_files() -> dict[pathlib.Path, str]:
    final = P4D2 / "results" / "P4d2_formal_20260731" / "final"
    return {
        P4D2 / "P4d2_source_manifest.json":
            "6aa3ab71905fe8b5a54239bcd64de6b92a744dfed08c54336fa072c4d5c29541",
        final / "p4d2_formal_stop_summary.json":
            "df520423b04e189da13923aa3ef1a0387fa1e0c44720d5bb0482d167c683c73e",
        final / "p4d2_formal_raw_manifest.json":
            "384b7b4e5a8e1244672c5d076f46a589dae3995a91ec1d10ff0c7d13e0ecb22b",
        final / "p4d2_duplicate_run_comparison.json":
            "00f469a9eca36016d75c35b03fb03bc0a2625cd2120a332bffcca1223989a5dd",
        final / "p4d2_formal_final_QA.json":
            "0f3cef984b9a0720ddeb126f1dd29b8a56c58912ca2ae6e75901462bf9c294e4",
        P4D3 / "P4d3_source_manifest.json":
            "68ab051fcc3a85ebdf0420cc662e09954b5bf48f467ce0db54a983e7642ee45c",
        P4D3 / "P4d4_diagnostic_freeze.json":
            "7731986244476c90b4769205bab6169462f6a82997ac5cc01d620abacf13b166",
        P4D3 / "P4d4_diagnostic_case_matrix.csv":
            "a97d1a97e88e7912bc2da5d6cac311b16c63dca2b9f355bf1f1881bae017f2a7",
        P4D3 / "P4d4_heldout_selection_rule.md":
            "622516e3f06370c06cc306e21b2b5fb356e84f527220c4db529f902d76b6afc1",
        P4D3 / "P4d4_acceptance_gates.md":
            "c238c060a140e8cca0d173ddf1cf305849d3273350234c23b582e5a8e9449f25",
    }


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json_new(path: pathlib.Path, value: Any) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def verify_case_manifest(case_dir: pathlib.Path) -> list[dict[str, Any]]:
    manifest = json.loads((case_dir / "case_manifest.json").read_text())
    for item in manifest["files"]:
        path = case_dir / item["path"]
        if not path.is_file() or sha256(path) != item["sha256"]:
            raise RuntimeError(f"case manifest mismatch: {path}")
    return manifest["files"]


def main() -> int:
    protected_status = []
    for path, expected in protected_files().items():
        actual = sha256(path)
        protected_status.append(
            {
                "path": path.relative_to(P4D_ROOT).as_posix(),
                "expected_sha256": expected,
                "actual_sha256": actual,
                "match": actual == expected,
            }
        )
    if not all(row["match"] for row in protected_status):
        raise RuntimeError("protected evidence drift")
    if FINAL.exists():
        raise RuntimeError("refusing to overwrite final directory")

    cases = []
    raw_files = []
    environments = []
    for case_id in CASES:
        case_dir = RESULTS / case_id / "run_1"
        files = verify_case_manifest(case_dir)
        result = json.loads((case_dir / "case_result.json").read_text())
        if result["evidence_status"] != "EXPLORATORY_NOT_FORMAL_EVIDENCE":
            raise RuntimeError(f"invalid evidence status for {case_id}")
        if result["formal_execution"] or result["formal_evidence"]:
            raise RuntimeError(f"formal evidence leakage for {case_id}")
        if result["target_load"] != TARGETS[case_id]:
            raise RuntimeError(f"target mismatch for {case_id}")
        native = result["native_line_search"]
        cases.append(
            {
                "case_id": case_id,
                "target_load": result["target_load"],
                "execution_completed": result["execution_completed"],
                "snes_reason": result["diagnostic_snes_reason"],
                "positive_snes_reason": result["diagnostic_positive_snes_reason"],
                "mechanics_gates_pass": result["diagnostic_mechanics_gates_pass"],
                "all_values_finite": result["all_values_finite"],
                "candidate_event_count": native["candidate_event_count"],
                "structured_unselected_candidate_count":
                    native["structured_unselected_candidate_count"],
                "complete_c_python_correlation":
                    native["candidate_to_python_packet_correlation_complete"],
                "observer_read_only": native["postcheck_flags_read_only"],
                "diagnostic_trigger": result["diagnostic_trigger"],
                "case_result_sha256": sha256(case_dir / "case_result.json"),
                "case_manifest_sha256": sha256(case_dir / "case_manifest.json"),
            }
        )
        environment = json.loads((case_dir / "environment.json").read_text())
        environments.append(
            {key: value for key, value in environment.items() if key != "run_id"}
        )
        for item in files:
            raw_files.append(
                {
                    "path": (
                        pathlib.Path(case_id) / "run_1" / item["path"]
                    ).as_posix(),
                    "sha256": item["sha256"],
                    "bytes": item["bytes"],
                }
            )
        manifest_path = case_dir / "case_manifest.json"
        raw_files.append(
            {
                "path": f"{case_id}/run_1/case_manifest.json",
                "sha256": sha256(manifest_path),
                "bytes": manifest_path.stat().st_size,
            }
        )

    environment_equal = all(item == environments[0] for item in environments[1:])
    first = next((row for row in cases if row["diagnostic_trigger"]), None)
    if first is None:
        adjudication = {
            "selection_status": "NOT_SUPPORTED_BY_DIAGNOSTIC_ENVELOPE",
            "first_trigger_case": None,
            "first_trigger_target": None,
            "heldout_target": None,
            "heldout_execution_authorized": False,
        }
    else:
        target = float(first["target_load"])
        adjudication = {
            "selection_status": "HELDOUT_TARGET_SELECTED_NOT_EXECUTED",
            "first_trigger_case": first["case_id"],
            "first_trigger_target": target,
            "heldout_target": HELDOUT[target],
            "heldout_execution_authorized": False,
        }

    all_completed = all(row["execution_completed"] for row in cases)
    summary = {
        "schema_version": "CMAME-P4D4-EXPLORATORY-SUMMARY-1.0",
        "final_status": (
            "PASS_P4D4_EXPLORATORY_DIAGNOSTICS_COMPLETE"
            if all_completed
            else "P4D4_EXPLORATORY_DIAGNOSTICS_COMPLETED_WITH_CASE_FAILURE"
        ),
        "evidence_status": "EXPLORATORY_NOT_FORMAL_EVIDENCE",
        "formal_case_count": 0,
        "exploratory_case_count": 3,
        "fresh_process_count": 3,
        "all_three_executed": all_completed,
        "run_all_cases_even_after_trigger": True,
        "environment_semantic_equality": environment_equal,
        "cases": cases,
        "heldout_adjudication": adjudication,
        "heldout_executed": False,
        "abaqus_used": False,
        "production_model_used": False,
    }

    FINAL.mkdir(parents=True)
    write_json_new(FINAL / "p4d4_exploratory_summary.json", summary)
    write_json_new(FINAL / "p4d4_heldout_adjudication.json", adjudication)
    write_json_new(
        FINAL / "p4d4_exploratory_raw_manifest.json",
        {
            "schema_version": "CMAME-P4D4-EXPLORATORY-RAW-MANIFEST-1.0",
            "raw_file_count": len(raw_files),
            "files": sorted(raw_files, key=lambda item: item["path"]),
            "manifest_self_hash_embedded": False,
        },
    )
    write_json_new(
        FINAL / "p4d4_protected_evidence_QA.json",
        {
            "all_protected_hashes_match": all(
                row["match"] for row in protected_status
            ),
            "protected_files": protected_status,
            "environment_semantic_equality": environment_equal,
            "formal_evidence_created": False,
            "heldout_executed": False,
        },
    )
    lines = [
        "# P4d.4 exploratory diagnostic result",
        "",
        "**Evidence status:** EXPLORATORY_NOT_FORMAL_EVIDENCE",
        "",
        "All three frozen diagnostic targets were executed exactly once in fresh, "
        "single-process, single-thread containers. These runs select or fail to "
        "select a future held-out target; they are not formal P4d evidence.",
        "",
        "## Case outcomes",
        "",
        "| Case | Target | SNES reason | Unselected candidates | Complete correlation | Mechanics/finite | Trigger |",
        "|---|---:|---:|---:|---|---|---|",
    ]
    for row in cases:
        lines.append(
            f"| {row['case_id']} | {row['target_load']:.2f} | "
            f"{row['snes_reason']} | "
            f"{row['structured_unselected_candidate_count']} | "
            f"{row['complete_c_python_correlation']} | "
            f"{row['mechanics_gates_pass'] and row['all_values_finite']} | "
            f"{row['diagnostic_trigger']} |"
        )
    lines.extend(
        [
            "",
            "## Deterministic adjudication",
            "",
            f"- Selection status: {adjudication['selection_status']}",
            f"- First trigger: {adjudication['first_trigger_case']}",
            f"- Held-out target: {adjudication['heldout_target']}",
            "- Held-out execution: not authorized and not performed.",
            "",
            "No P4d formal PASS, manuscript claim, GitHub/Zenodo update, or "
            "production-model inference is created by this diagnostic package.",
        ]
    )
    report = FINAL / "P4d4_exploratory_result_report.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0 if all_completed else 2


if __name__ == "__main__":
    raise SystemExit(main())
