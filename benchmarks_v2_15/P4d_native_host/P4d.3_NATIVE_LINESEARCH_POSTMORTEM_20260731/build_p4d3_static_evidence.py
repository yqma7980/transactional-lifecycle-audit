from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
P4D_ROOT = HERE.parent
P4D1 = P4D_ROOT / "P4d.1_IMPLEMENTATION_PREFLIGHT_20260731"
P4D2 = P4D_ROOT / "P4d.2_FULL_IMPLEMENTATION_20260731"
FORMAL_ROOT = P4D2 / "results" / "P4d2_formal_20260731"
SAFE_LS = FORMAL_ROOT / "P4D-SAFE-LS-01" / "run_1"
FINAL = FORMAL_ROOT / "final"


EXPECTED_HASHES = {
    P4D2 / "P4d2_source_manifest.json": "6aa3ab71905fe8b5a54239bcd64de6b92a744dfed08c54336fa072c4d5c29541",
    FINAL / "p4d2_formal_stop_summary.json": "df520423b04e189da13923aa3ef1a0387fa1e0c44720d5bb0482d167c683c73e",
    FINAL / "p4d2_formal_raw_manifest.json": "384b7b4e5a8e1244672c5d076f46a589dae3995a91ec1d10ff0c7d13e0ecb22b",
    FINAL / "p4d2_duplicate_run_comparison.json": "00f469a9eca36016d75c35b03fb03bc0a2625cd2120a332bffcca1223989a5dd",
    FINAL / "p4d2_formal_final_QA.json": "0f3cef984b9a0720ddeb126f1dd29b8a56c58912ca2ae6e75901462bf9c294e4",
    SAFE_LS / "case_result.json": "2ad300d5697d40e026146bc6ee8ebda8960c113164533c2c9cb648ff42516af2",
    SAFE_LS / "c_observer_ledger.jsonl": "9d04ade4086dd7ba600d26b890ca345b8268ffa5c0db175158ad2cc3626cfdab",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(P4D_ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def verify_baseline() -> dict[str, str]:
    observed: dict[str, str] = {}
    for path, expected in EXPECTED_HASHES.items():
        actual = sha256(path)
        if actual != expected:
            raise RuntimeError(f"BLOCKED_RAW_EVIDENCE_DRIFT: {path} expected {expected}, observed {actual}")
        observed[rel(path)] = actual
    return observed


def load_python_trials(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            if row["event_kind"] != "TrialEvaluate":
                continue
            row["primary_vector"] = json.loads(row["primary_vector_hex"])
            rows.append(row)
    return rows


def normalized_hex_vector(values: list[str]) -> tuple[str, ...]:
    """Normalize equivalent PETSc/Python hexadecimal spellings."""
    return tuple(float.fromhex(value).hex() for value in values)


def pair_events(
    source_case: str,
    events: list[dict[str, Any]],
    python_trials: list[dict[str, Any]] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    candidates = {int(e["event_ordinal"]): e for e in events if e.get("callback_kind") == "LINE_SEARCH_CANDIDATE"}
    selected = {int(e["event_ordinal"]): e for e in events if e.get("callback_kind") == "LINE_SEARCH_SELECTED"}
    if set(candidates) != set(selected):
        raise RuntimeError(f"candidate/selected ordinal mismatch for {source_case}")

    by_vector: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    if python_trials is not None:
        for trial in python_trials:
            by_vector[normalized_hex_vector(trial["primary_vector"])].append(trial)
    used_python_ids: set[str] = set()

    rows: list[dict[str, Any]] = []
    for ordinal in sorted(candidates):
        candidate = candidates[ordinal]
        chosen = selected[ordinal]
        exact_matches = by_vector.get(normalized_hex_vector(candidate.get("W_hex_values", [])), [])
        python_match = next((m for m in exact_matches if m["candidate_id"] not in used_python_ids), None)
        if python_match is None and exact_matches:
            python_match = exact_matches[0]
        if python_match is not None:
            used_python_ids.add(python_match["candidate_id"])

        vector_equal = {
            name: candidate.get(f"{name}_hex_values") == chosen.get(f"{name}_hex_values")
            for name in ("X", "F", "Y", "W", "G")
        }
        row = {
            "source_case": source_case,
            "solve_id_candidate": candidate.get("solve_id"),
            "solve_id_selected": chosen.get("solve_id"),
            "event_ordinal": ordinal,
            "nonlinear_iteration_candidate": candidate.get("nonlinear_iteration"),
            "nonlinear_iteration_selected": chosen.get("nonlinear_iteration"),
            "candidate_lambda_hex": candidate.get("lambda_hex"),
            "selected_lambda_hex": chosen.get("lambda_hex"),
            "candidate_reason": candidate.get("line_search_reason"),
            "selected_reason": chosen.get("line_search_reason"),
            "x_equal": vector_equal["X"],
            "f_equal": vector_equal["F"],
            "y_equal": vector_equal["Y"],
            "w_equal": vector_equal["W"],
            "g_equal": vector_equal["G"],
            "all_vectors_equal": all(vector_equal.values()),
            "python_candidate_id": python_match.get("candidate_id") if python_match else "",
            "python_attempt_id": python_match.get("attempt_id") if python_match else "",
            "python_primary_vector_exact_match": python_match is not None,
            "structured_unselected_candidate": not vector_equal["W"],
        }
        rows.append(row)

    attach = [e for e in events if e.get("callback_kind") == "ATTACH"]
    summary = {
        "source_case": source_case,
        "candidate_count": len(candidates),
        "selected_count": len(selected),
        "pair_count": len(rows),
        "all_solve_ids_equal": all(r["solve_id_candidate"] == r["solve_id_selected"] for r in rows),
        "all_iterations_equal": all(r["nonlinear_iteration_candidate"] == r["nonlinear_iteration_selected"] for r in rows),
        "all_candidate_lambdas_one": all(r["candidate_lambda_hex"] == "0x1p+0" for r in rows),
        "all_selected_lambdas_one": all(r["selected_lambda_hex"] == "0x1p+0" for r in rows),
        "all_reasons_zero": all(r["candidate_reason"] == 0 and r["selected_reason"] == 0 for r in rows),
        "all_vectors_equal": all(r["all_vectors_equal"] for r in rows),
        "structured_unselected_candidate_count": sum(bool(r["structured_unselected_candidate"]) for r in rows),
        "python_correlation_count": sum(bool(r["python_primary_vector_exact_match"]) for r in rows),
        "postcheck_change_flags_read_only": bool(attach) and all(e.get("postcheck_change_flags") is False for e in attach),
    }
    return rows, summary


def write_pair_csv(rows: list[dict[str, Any]]) -> None:
    path = HERE / "P4d3_event_pair_audit.csv"
    fields = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    baseline = verify_baseline()
    safe_events = read_jsonl(SAFE_LS / "c_observer_ledger.jsonl")
    python_trials = load_python_trials(SAFE_LS / "event_ledger.csv")
    safe_rows, safe_summary = pair_events("P4D-SAFE-LS-01/run_1", safe_events, python_trials)

    zero_root = P4D1 / "runtime_evidence" / "observer_on_run_1"
    zero_events = read_jsonl(zero_root / "c_ledger.jsonl")
    zero_rows, zero_summary = pair_events("P4d.1/observer_on_run_1", zero_events, None)

    if safe_summary["pair_count"] != 29:
        raise RuntimeError("SAFE-LS pair count is not 29")
    if not all((safe_summary[k] for k in (
        "all_solve_ids_equal", "all_iterations_equal", "all_candidate_lambdas_one",
        "all_selected_lambdas_one", "all_reasons_zero", "all_vectors_equal",
        "postcheck_change_flags_read_only",
    ))):
        raise RuntimeError("SAFE-LS pair audit did not satisfy frozen postmortem facts")
    if safe_summary["python_correlation_count"] != 29 or safe_summary["structured_unselected_candidate_count"] != 0:
        raise RuntimeError("SAFE-LS correlation/unselected counts differ from frozen evidence")
    if zero_summary["structured_unselected_candidate_count"] < 1:
        raise RuntimeError("P4d.1 zero case no longer demonstrates bridge observability")

    bridge_source = P4D2 / "src" / "p4d_observer_bridge.c"
    bridge_text = bridge_source.read_text(encoding="utf-8")
    bridge_contract = {
        "monitor_registered": "SNESLineSearchMonitorSet" in bridge_text,
        "postcheck_registered": "SNESLineSearchSetPostCheck" in bridge_text,
        "direction_change_forced_false": "*changed_direction = PETSC_FALSE;" in bridge_text,
        "work_change_forced_false": "*changed_work = PETSC_FALSE;" in bridge_text,
        "line_search_vectors_read": "SNESLineSearchGetVecs" in bridge_text,
        "line_search_lambda_read": "SNESLineSearchGetLambda" in bridge_text,
        "line_search_reason_read": "SNESLineSearchGetReason" in bridge_text,
    }
    if not all(bridge_contract.values()):
        raise RuntimeError("observer source no longer satisfies the frozen read-only contract")

    final_status = "PASS_P4D3_POSTMORTEM_AND_P4D4_DIAGNOSTIC_FREEZE"
    failure_cause = "FROZEN_HISTORY_DID_NOT_TRIGGER_NATIVE_REJECTION"
    write_pair_csv(safe_rows + zero_rows)

    postmortem_freeze = {
        "schema_version": "CMAME-P4D3-POSTMORTEM-FREEZE-1.0",
        "status": final_status,
        "analysis_kind": "READ_ONLY_POSTMORTEM",
        "formal_case_rerun": False,
        "new_fe_case_execution": False,
        "safe_ls_raw_verdict": "P4D-SAFE-LS-01_CONTRACT_FAIL",
        "derived_adjudication": "NOT_SUPPORTED_BY_FROZEN_HISTORY",
        "failure_cause": failure_cause,
        "safe_ls_pair_summary": safe_summary,
        "p4d1_zero_case_pair_summary": zero_summary,
        "observer_source_contract": bridge_contract,
        "baseline_sha256": baseline,
        "protected_evidence_mutation_allowed": False,
    }
    write_json(HERE / "P4d3_postmortem_freeze.json", postmortem_freeze)

    adjudication = {
        "schema_version": "CMAME-P4D3-FAILURE-ADJUDICATION-1.0",
        "raw_evidence": {
            "case_id": "P4D-SAFE-LS-01",
            "run_id": "run_1",
            "raw_verdict": "P4D-SAFE-LS-01_CONTRACT_FAIL",
            "pass_flag": False,
            "raw_json_rewritten": False,
        },
        "derived_scientific_adjudication": "NOT_SUPPORTED_BY_FROZEN_HISTORY",
        "reason": "The frozen FE load history accepted every observed full Newton step. It never generated the structured unselected line-search candidate required by the frozen L3 contract.",
        "not_a_numerical_failure": True,
        "not_an_observer_failure": True,
        "observer_observability_supported_by_p4d1_zero_case": True,
        "full_p4d_matrix_pass": False,
        "formal_evidence_scope": "The raw contract failure remains preserved; the derived label only identifies why the required event was absent.",
    }
    write_json(HERE / "P4d3_failure_adjudication.json", adjudication)

    diagnostic_cases = [
        {
            "case_id": "P4D4-DIAG-LS-00",
            "source_load": 0.08,
            "target_load": 0.16,
            "operator_relation": "DECLARED_ACCEPTED_STATE_LAG",
            "execution_status": "REFERENCE_EXISTING_P4D2_EVIDENCE_NO_RERUN",
            "evidence_status": "EXPLORATORY_NOT_FORMAL_EVIDENCE",
            "selection_eligible": False,
        },
        {
            "case_id": "P4D4-DIAG-LS-01",
            "source_load": 0.08,
            "target_load": 0.20,
            "operator_relation": "DECLARED_ACCEPTED_STATE_LAG",
            "execution_status": "FROZEN_NOT_EXECUTED",
            "evidence_status": "EXPLORATORY_NOT_FORMAL_EVIDENCE",
            "selection_eligible": True,
        },
        {
            "case_id": "P4D4-DIAG-LS-02",
            "source_load": 0.08,
            "target_load": 0.24,
            "operator_relation": "DECLARED_ACCEPTED_STATE_LAG",
            "execution_status": "FROZEN_NOT_EXECUTED",
            "evidence_status": "EXPLORATORY_NOT_FORMAL_EVIDENCE",
            "selection_eligible": True,
        },
        {
            "case_id": "P4D4-DIAG-LS-03",
            "source_load": 0.08,
            "target_load": 0.28,
            "operator_relation": "DECLARED_ACCEPTED_STATE_LAG",
            "execution_status": "FROZEN_NOT_EXECUTED",
            "evidence_status": "EXPLORATORY_NOT_FORMAL_EVIDENCE",
            "selection_eligible": True,
        },
    ]
    diagnostic_freeze = {
        "schema_version": "CMAME-P4D4-DIAGNOSTIC-FREEZE-1.0",
        "design_status": "FROZEN_NOT_EXECUTED",
        "execution_authorized": False,
        "formal_evidence": False,
        "container": {
            "image": "dolfinx/dolfinx@sha256:1bb0d528457c78db65ba5445421abe37d0cdfa542cc182bf36d3b4aca02f1fab",
            "platform": "linux/amd64",
            "network": "none",
            "mpi_ranks": 1,
            "processes_per_case": 1,
            "threads_per_process": 1,
        },
        "unchanged_host_contract": {
            "mesh": "4x4 squares with fixed diagonal split; 32 P1 triangles; 25 nodes",
            "quadrature": "degree-2 triangle; 3 points per cell; 96 integration points",
            "material": {"G": 10.0, "tau_y0": 1.0, "hardening": 2.0},
            "snes_options": {
                "snes_type": "newtonls", "snes_linesearch_type": "bt",
                "snes_atol": 1.0e-11, "snes_rtol": 1.0e-10,
                "snes_stol": 1.0e-12, "snes_max_it": 25,
                "ksp_type": "preonly", "pc_type": "lu",
            },
            "observer": "unchanged P4d.2 read-only C observer",
            "source_state": "same cyclic reload committed state at load 0.08",
            "line_search_parameter_changes_allowed": False,
            "material_parameter_changes_allowed": False,
            "mesh_changes_allowed": False,
        },
        "diagnostic_cases": diagnostic_cases,
        "execution_rule": "When separately authorized, run DIAG-LS-01, DIAG-LS-02, and DIAG-LS-03 exactly once each; do not stop after the first trigger and do not tune parameters.",
        "heldout_rule": {
            "first_trigger_0.20": 0.22,
            "first_trigger_0.24": 0.26,
            "first_trigger_0.28": 0.30,
            "no_trigger": "NOT_SUPPORTED_BY_DIAGNOSTIC_ENVELOPE",
        },
    }
    write_json(HERE / "P4d4_diagnostic_freeze.json", diagnostic_freeze)

    with (HERE / "P4d4_diagnostic_case_matrix.csv").open("w", encoding="utf-8", newline="") as stream:
        fields = list(diagnostic_cases[0])
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(diagnostic_cases)

    observer_md = f"""# P4d.3 observer semantics

## Conclusion

The PETSc C bridge is capable of distinguishing a full-step line-search candidate from the selected work vector. The missing rejected candidate in P4D-SAFE-LS-01 is attributed to the frozen history not triggering backtracking, not to an observer-API limitation.

## Read-only attachment

- SNESLineSearchMonitorSet records LINE_SEARCH_CANDIDATE before selection.
- SNESLineSearchSetPostCheck records LINE_SEARCH_SELECTED after selection.
- SNESLineSearchGetVecs, GetLambda, and GetReason read X/F/Y/W/G, lambda, and reason.
- changed_direction and changed_work are always set to PETSC_FALSE.
- The bridge does not change vectors, solver options, material state, lambda, or reason.

## P4D-SAFE-LS-01

- Candidate/selected pairs: {safe_summary['pair_count']}.
- Candidate and selected lambda equal one: {safe_summary['all_candidate_lambdas_one'] and safe_summary['all_selected_lambdas_one']}.
- Exact X/F/Y/W/G equality for all pairs: {safe_summary['all_vectors_equal']}.
- Exact C-to-Python primary-vector correlations: {safe_summary['python_correlation_count']}/{safe_summary['candidate_count']}.
- Structured unselected candidates: {safe_summary['structured_unselected_candidate_count']}.

## P4d.1 zero-case comparison

- Candidate/selected pairs: {zero_summary['pair_count']}.
- Structured unselected candidates: {zero_summary['structured_unselected_candidate_count']}.
- This prior zero case includes a full-step candidate followed by a selected backtracked state, demonstrating the required public-interface observability.

## Boundary

This is a read-only postmortem. It does not convert the raw contract failure into a formal pass and does not establish complete P4d matrix support.
"""
    (HERE / "P4d3_observer_semantics.md").write_text(observer_md, encoding="utf-8", newline="\n")

    dag_md = """# P4d.3 branch dependency DAG

## Static dependency proposal

REF -> CONST -> DIR

DIR -> native line-search branch

DIR -> driver-retry branch

DIR checkpoint -> restart branch

driver-retry -> cache/output negative controls

CONST -> version-guard branch

## Decision rule

A NOT_SUPPORTED result in one branch does not automatically block a logically independent branch. Prerequisites within each branch remain mandatory. The complete P4d matrix cannot be labeled PASS while any required branch is NOT_SUPPORTED, failed, or unexecuted.

## Current application

The native line-search branch remains NOT_SUPPORTED_BY_FROZEN_HISTORY. This static DAG does not authorize any downstream execution and does not retroactively change P4d.2 results.
"""
    (HERE / "P4d3_dependency_dag.md").write_text(dag_md, encoding="utf-8", newline="\n")

    heldout_md = """# P4d.4 held-out selection rule

## Diagnostic execution requirement

After separate authorization, execute DIAG-LS-01, DIAG-LS-02, and DIAG-LS-03 exactly once each. All are exploratory and must be completed even if an earlier target triggers an unselected candidate. Do not tune parameters or add a fourth diagnostic target.

## Trigger definition

A diagnostic triggers only when all conditions hold:

1. SNES reason is positive.
2. At least one structured unselected line-search candidate is present.
3. Every C candidate has an exact Python TrialEvaluate primary-vector correlation.
4. Mechanics and finite gates pass.
5. The observer remains read-only.

## Deterministic held-out mapping

- If 0.20 is the first triggering target, select held-out target 0.22.
- If 0.24 is the first triggering target, select held-out target 0.26.
- If 0.28 is the first triggering target, select held-out target 0.30.
- If none triggers, adjudicate NOT_SUPPORTED_BY_DIAGNOSTIC_ENVELOPE.

## Future formal requirement

The selected held-out target must include an exact-current direct control and a declared-accepted-state-lag native line-search case, each repeated in two fresh single-process, single-thread runs. This document does not authorize those runs.
"""
    (HERE / "P4d4_heldout_selection_rule.md").write_text(heldout_md, encoding="utf-8", newline="\n")

    gates_md = """# P4d.4 acceptance gates

## Exploratory diagnostic gates

- Frozen image, mesh, material, cyclic reload state, PETSc types, tolerances, and observer are unchanged.
- Positive SNES reason.
- At least one structured unselected candidate.
- Complete exact C-to-Python candidate correlation.
- Post-check change flags remain false.
- All values finite.
- Free-DOF equilibrium, reaction balance, alpha bounds, and yield-consistency gates pass.
- Each diagnostic is labeled EXPLORATORY_NOT_FORMAL_EVIDENCE.

## Held-out formal gates

- Target is selected only by the predeclared mapping.
- Exact-current direct and declared-lag histories share the same declared source state and target load.
- Each history has two fresh-process repetitions with semantic duplicate equality.
- Native unselected candidate evidence is structured and correlated.
- Accepted output is post-commit and rejected candidates are unreachable.
- Mechanics, finite, operator-version, and lifecycle gates pass.

## Prohibitions

No diagnostic threshold tuning, line-search option change, material or mesh change, extra target, retrospective selection, or reuse of exploratory runs as formal evidence is allowed.
"""
    (HERE / "P4d4_acceptance_gates.md").write_text(gates_md, encoding="utf-8", newline="\n")

    report_md = f"""# P4d.3 native line-search postmortem and P4d.4 static freeze

## Final status

{final_status}

## Findings

The seven protected P4d.2 hashes match their frozen values. P4D-SAFE-LS-01/run_1 contains {safe_summary['pair_count']} candidate/selected pairs. Every candidate and selection used lambda=1, reason=0, and identical X/F/Y/W/G vectors; all {safe_summary['python_correlation_count']} candidates correlate exactly to Python TrialEvaluate primary vectors. No structured unselected candidate occurred.

The P4d.1 zero case contains {zero_summary['structured_unselected_candidate_count']} structured unselected candidate, proving that the same public PETSc observation pattern can distinguish a full-step candidate from the selected backtracked state. The evidence therefore supports {failure_cause} rather than an observer limitation.

## Adjudication

- Preserved raw verdict: P4D-SAFE-LS-01_CONTRACT_FAIL.
- Read-only derived adjudication: NOT_SUPPORTED_BY_FROZEN_HISTORY.
- The run is not relabeled PASS, numerical failure, or observer failure.
- The complete P4d matrix remains not passed.

## P4d.4 freeze

DIAG-LS-00 records the existing 0.08 -> 0.16 observation without rerun. DIAG-LS-01/02/03 statically freeze targets 0.20, 0.24, and 0.28 from the same 0.08 cyclic reload state with declared accepted-state lag. All future diagnostic outputs remain EXPLORATORY_NOT_FORMAL_EVIDENCE. The held-out mapping is fixed at 0.22, 0.26, or 0.30 according to the first trigger.

## Evidence boundary

No FE solve or benchmark was executed for this postmortem. No old result, threshold, manuscript, claim matrix, figure, GitHub, Zenodo, DOI, Abaqus, COMSOL, OpenSees, or production artifact was modified.
"""
    (HERE / "P4d3_final_report.md").write_text(report_md, encoding="utf-8", newline="\n")

    input_files = list(EXPECTED_HASHES) + [
        SAFE_LS / "event_ledger.csv",
        SAFE_LS / "case_manifest.json",
        P4D1 / "runtime_evidence" / "observer_on_run_1" / "c_ledger.jsonl",
        P4D1 / "runtime_evidence" / "observer_on_run_1" / "result.json",
        P4D1 / "src" / "p4d_observer_bridge.c",
        P4D2 / "src" / "p4d_observer_bridge.c",
        P4D2 / "src" / "p4d_observer.py",
        P4D2 / "src" / "p4d_config.py",
        P4D2 / "P4d2_implementation_freeze.json",
        P4D2 / "P4d2_formal_execution_freeze_20260731.json",
    ]
    output_names = [
        "build_p4d3_static_evidence.py",
        "P4d3_postmortem_freeze.json",
        "P4d3_event_pair_audit.csv",
        "P4d3_observer_semantics.md",
        "P4d3_failure_adjudication.json",
        "P4d3_dependency_dag.md",
        "P4d4_diagnostic_freeze.json",
        "P4d4_diagnostic_case_matrix.csv",
        "P4d4_heldout_selection_rule.md",
        "P4d4_acceptance_gates.md",
        "P4d3_final_report.md",
    ]
    manifest = {
        "schema_version": "CMAME-P4D3-SOURCE-MANIFEST-1.0",
        "final_status": final_status,
        "source_inputs": [
            {"path": rel(path), "sha256": sha256(path), "size_bytes": path.stat().st_size}
            for path in sorted(set(input_files), key=lambda p: rel(p))
        ],
        "generated_outputs": [
            {"path": name, "sha256": sha256(HERE / name), "size_bytes": (HERE / name).stat().st_size}
            for name in output_names
        ],
        "manifest_self_hash_embedded": False,
        "no_fe_case_execution": True,
        "no_abaqus_execution": True,
        "no_old_evidence_modification": True,
    }
    write_json(HERE / "P4d3_source_manifest.json", manifest)

    verify_baseline()
    print(json.dumps({
        "status": final_status,
        "safe_ls": safe_summary,
        "zero_case": zero_summary,
        "generated_file_count": len(output_names) + 1,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
