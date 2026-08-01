from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import sys
from pathlib import Path

import numpy as np

from feh_model import (
    SERIALIZER_VERSION,
    audit_replay_pair,
    case_payload,
    compare_histories,
    patch_oracle,
    run_history,
)


CASES = {
    "FEH-REF-01",
    "FEH-LC-01",
    "FEH-LC-02",
    "FEH-LC-03",
    "FEH-LC-04",

    "FEH-NC-01",
    "FEH-NC-02",
    "FEH-NC-03",
}


INVALID_A4 = "INVALID_A4_PERSISTENT_STATE_INCOMPATIBLE"

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def classify_replay_comparison(
    variant: str,
    legacy_expected_classification: str,
    direct_pass: bool,
    perturbed_pass: bool,
    comparison: dict,
) -> dict:
    """Return separate full-TLA and seeded-sensitivity verdicts."""
    finite = bool(comparison["all_values_finite"])
    persistent_compatible = bool(
        comparison["persistent_fingerprint_equal"]
        and comparison["observed_persistent_fingerprint_equal"]
    )
    drift = max(
        float(comparison["residual_relative_drift"]),
        float(comparison["tangent_relative_drift"]),
    )
    operator_drift_detected = finite and drift > 1e-8

    if variant == "safe_transactional":
        parity = (
            comparison["residual_relative_drift"] <= 1e-12
            and comparison["tangent_relative_drift"] <= 1e-12
            and comparison["displacement_relative_error"] <= 1e-11
            and comparison["reaction_relative_error"] <= 1e-11
            and comparison["stress_relative_error"] <= 1e-11
            and comparison["kappa_relative_error"] <= 1e-11
        )
        full_tla_pass = direct_pass and perturbed_pass and parity and persistent_compatible
        full_tla_verdict = (
            legacy_expected_classification if full_tla_pass else "FAIL_ACCEPTANCE_GATES"
        )
        negative_control_gate_pass = None
        formal_case_contract_pass = full_tla_pass
    else:
        negative_control_gate_pass = (
            direct_pass and perturbed_pass and finite and operator_drift_detected
        )
        if persistent_compatible:
            full_tla_pass = negative_control_gate_pass
            full_tla_verdict = (
                legacy_expected_classification
                if full_tla_pass
                else "FAIL_ACCEPTANCE_GATES"
            )
        else:
            full_tla_pass = False
            full_tla_verdict = INVALID_A4
        formal_case_contract_pass = negative_control_gate_pass

    return {
        "a4_persistent_compatibility_satisfied": persistent_compatible,
        "expected_full_tla_verdict": legacy_expected_classification if persistent_compatible else INVALID_A4,
        "full_tla_verdict": full_tla_verdict,
        "full_tla_pass_flag": full_tla_pass,
        "operator_replay_drift_detected": operator_drift_detected,
        "operator_sensitivity_classification": legacy_expected_classification,
        "negative_control_gate_pass": negative_control_gate_pass,
        "formal_case_contract_pass": formal_case_contract_pass,
    }

def execute(case_id: str) -> tuple[dict, list[dict], list[dict]]:
    if case_id == "FEH-REF-01":
        result = run_history("direct", heterogeneous=False)
        oracle = patch_oracle()
        final = result.accepted_rows[-1]
        reaction_error = abs(final["reaction_top"] - oracle["reaction"]) / max(1.0, abs(oracle["reaction"]))
        stress = result.replay_packet.candidate.stress
        stress_error = float(np.max(np.abs(stress[1] - oracle["stress"])))
        kappa_error = float(np.max(np.abs(result.committed.kappa - oracle["kappa"])))
        passed = result.pass_flag and reaction_error <= 1e-10 and stress_error <= 1e-10 and kappa_error <= 1e-10
        payload = case_payload(result)
        payload.update(
            {
                "case_id": case_id,
                "classification": "PASS_ANALYTICAL_PATCH" if passed else "FAIL_ANALYTICAL_PATCH",
                "pass_flag": passed,
                "oracle": oracle,
                "reaction_error": reaction_error,
                "stress_error": stress_error,
                "kappa_error": kappa_error,
            }
        )
        return payload, result.ledger.rows, result.accepted_rows

    if case_id == "FEH-NC-03":
        result = run_history("version_mismatch", variant="operator_version_mismatch")
        payload = case_payload(result)
        payload["case_id"] = case_id
        return payload, result.ledger.rows, result.accepted_rows

    mapping = {
        "FEH-LC-01": ("direct", "safe_transactional", 0.0, "PASS_SAFE_DIRECT"),
        "FEH-LC-02": ("rejected_line_search", "safe_transactional", 0.0, "PASS_SAFE_LINE_SEARCH_PARITY"),
        "FEH-LC-03": ("cutback", "safe_transactional", 0.0, "PASS_SAFE_CUTBACK_PARITY"),
        "FEH-LC-04": ("restart", "safe_transactional", 0.0, "PASS_SAFE_RESTART_PARITY"),
        "FEH-NC-01": ("rejected_line_search", "unsafe_trial_cache", 1e-2, "DETECT_TRIAL_CACHE_DRIFT"),
        "FEH-NC-02": ("rejected_line_search", "unsafe_output_feedback", 1e-2, "DETECT_OUTPUT_FEEDBACK_DRIFT"),
    }
    history, variant, strength, expected = mapping[case_id]
    direct = run_history("direct", variant=variant, mutation_strength=strength)
    perturbed = run_history(history, variant=variant, mutation_strength=strength)
    comparison = compare_histories(direct, perturbed)
    audit_comparison, audit_ledger = audit_replay_pair(variant, strength)
    comparison.update(audit_comparison)
    adjudication = classify_replay_comparison(
        variant, expected, direct.pass_flag, perturbed.pass_flag, comparison
    )
    payload = {
        "case_id": case_id,
        "history": history,
        "variant": variant,
        "strength": strength,
        "legacy_expected_classification": expected,
        "expected_classification": adjudication["expected_full_tla_verdict"],
        "observed_classification": adjudication["full_tla_verdict"],
        "pass_flag": adjudication["full_tla_pass_flag"],
        "direct": case_payload(direct),
        "perturbed": case_payload(perturbed),
        "comparison": comparison,
        **adjudication,
    }
    ledger = []
    for row in direct.ledger.rows:
        ledger.append({"comparison_side": "direct", **row})
    for row in perturbed.ledger.rows:
        ledger.append({"comparison_side": "perturbed", **row})
    for row in audit_ledger.rows:
        ledger.append({"comparison_side": "equal_declared_audit", **row})
    accepted = []
    for row in direct.accepted_rows:
        accepted.append({"comparison_side": "direct", **row})
    for row in perturbed.accepted_rows:
        accepted.append({"comparison_side": "perturbed", **row})
    return payload, ledger, accepted


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-id", required=True, choices=sorted(CASES))
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--execute-authorized", action="store_true")
    args = parser.parse_args()
    if not args.execute_authorized or os.environ.get("FEH_D0_EXECUTION_AUTHORIZED") != "YES":
        raise SystemExit("FEH-D0 execution requires CLI and environment authorization")
    output = Path(args.output_root) / args.case_id / args.run_id
    if output.exists():
        raise SystemExit(f"Refusing to overwrite {output}")
    output.mkdir(parents=True)
    payload, ledger, accepted = execute(args.case_id)
    payload.update(
        {
            "design_version": "FEH-D0.0",
            "host_version": "FEH-SKFEM-1.0",
            "serializer_version": SERIALIZER_VERSION,
            "run_id": args.run_id,
            "processes": 1,
            "threads": 1,
        }
    )
    result_path = output / "case_result.json"
    ledger_path = output / "event_ledger.csv"
    accepted_path = output / "accepted_states.csv"
    result_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    write_csv(ledger_path, ledger)
    write_csv(accepted_path, accepted)
    manifest = {
        "case_id": args.case_id,
        "run_id": args.run_id,
        "python": sys.version,
        "platform": platform.platform(),
        "thread_environment": {
            key: os.environ.get(key)
            for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")
        },
        "outputs": {
            path.name: sha256(path)
            for path in (result_path, ledger_path, accepted_path)
        },
    }
    (output / "case_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    contract_pass = payload.get("formal_case_contract_pass", payload["pass_flag"])
    print(
        json.dumps({"case_id": args.case_id, "run_id": args.run_id, "formal_case_contract_pass": contract_pass})
    )
    return 0 if contract_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
