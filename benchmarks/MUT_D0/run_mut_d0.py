from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import sys
from pathlib import Path

FEH_ROOT = Path(__file__).resolve().parents[1] / "FEH_D0"
sys.path.insert(0, str(FEH_ROOT))

from feh_model import (  # noqa: E402
    audit_holdout_pair,
    audit_replay_pair,
    compare_histories,
    run_history,
    run_holdout_history,
)


STRENGTHS = (
    0.0, 1e-12, 3e-12, 1e-11, 3e-11, 1e-10, 3e-10, 1e-9, 3e-9,
    1e-8, 3e-8, 1e-7, 3e-7, 1e-6, 3e-6, 1e-5, 3e-5, 1e-4,
    3e-4, 1e-3, 3e-3, 1e-2,
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def classify(conventional: dict, audit: dict) -> tuple[str, bool, bool]:
    accuracy = max(
        conventional[key]
        for key in (
            "displacement_relative_error",
            "reaction_relative_error",
            "stress_relative_error",
            "kappa_relative_error",
        )
    )
    conventional_pass = (
        conventional["left_pass"]
        and conventional["right_pass"]
        and conventional["all_values_finite"]
        and conventional["right_balance"] <= 1e-9
        and accuracy <= 1e-5
    )
    drift = max(audit["residual_relative_drift"], audit["tangent_relative_drift"])
    operator_replay_drift_detected = audit["all_values_finite"] and drift > 1e-10
    if conventional_pass and operator_replay_drift_detected:
        classification = "OPERATOR_REPLAY_DRIFT_DETECTED_WITH_CONVENTIONAL_GATES_PASS"
    elif conventional_pass:
        classification = "BELOW_OPERATOR_REPLAY_DRIFT_THRESHOLD"
    elif operator_replay_drift_detected:
        classification = "OPERATOR_REPLAY_DRIFT_DETECTED_WITH_CONVENTIONAL_GATE_FAILURE"
    else:
        classification = "INVALID_RUN"
    return classification, conventional_pass, operator_replay_drift_detected


def execute_development(strength: float) -> tuple[dict, list[dict]]:
    safe = run_history("direct", variant="safe_transactional", mutation_strength=0.0)
    mutated = run_history(
        "rejected_line_search",
        variant="unsafe_trial_cache",
        mutation_strength=strength,
    )
    conventional = compare_histories(safe, mutated)
    audit, audit_ledger = audit_replay_pair("unsafe_trial_cache", strength)
    classification, conventional_pass, operator_replay_drift_detected = classify(conventional, audit)
    payload = {
        "study": "development",
        "strength": strength,
        "classification": classification,
        "conventional_pass": conventional_pass,
        "operator_replay_drift_detected": operator_replay_drift_detected,
        "a4_persistent_compatibility_satisfied": False,
        "full_tla_replay_verdict": "INVALID_A4_PERSISTENT_STATE_INCOMPATIBLE",
        "comparison_scope": "SEEDED_NEGATIVE_CONTROL_OPERATOR_REPLAY_SENSITIVITY",
        "reporting_contract": "MUT-D0-v2.9",
        "conventional": conventional,
        "audit": audit,
        "finite": conventional["all_values_finite"] and audit["all_values_finite"],
    }
    ledger = []
    for row in mutated.ledger.rows:
        ledger.append({"ledger_source": "mutated_full_history", **row})
    for row in audit_ledger.rows:
        ledger.append({"ledger_source": "equal_declared_audit", **row})
    return payload, ledger


def execute_confirmation(strength: float) -> tuple[dict, list[dict]]:
    safe = run_holdout_history("safe_transactional", 0.0, False)
    mutated = run_holdout_history("unsafe_trial_cache", strength, True)
    conventional = compare_histories(safe, mutated)
    audit, audit_ledger = audit_holdout_pair("unsafe_trial_cache", strength)
    classification, conventional_pass, operator_replay_drift_detected = classify(conventional, audit)
    passed = classification == "OPERATOR_REPLAY_DRIFT_DETECTED_WITH_CONVENTIONAL_GATES_PASS"
    payload = {
        "study": "predeclared_confirmation",
        "strength": strength,
        "classification": "PASS_PREDECLARED_CONFIRMATION_OPERATOR_DRIFT" if passed else "FAIL_PREDECLARED_CONFIRMATION_OPERATOR_DRIFT",
        "pass_flag": passed,
        "conventional_pass": conventional_pass,
        "operator_replay_drift_detected": operator_replay_drift_detected,
        "a4_persistent_compatibility_satisfied": False,
        "full_tla_replay_verdict": "INVALID_A4_PERSISTENT_STATE_INCOMPATIBLE",
        "comparison_scope": "SEEDED_NEGATIVE_CONTROL_OPERATOR_REPLAY_SENSITIVITY",
        "reporting_contract": "MUT-D0-v2.9",
        "conventional": conventional,
        "audit": audit,
        "finite": conventional["all_values_finite"] and audit["all_values_finite"],
    }
    ledger = []
    for row in mutated.ledger.rows:
        ledger.append({"ledger_source": "mutated_holdout_history", **row})
    for row in audit_ledger.rows:
        ledger.append({"ledger_source": "equal_declared_holdout_audit", **row})
    return payload, ledger


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--strength-index", type=int)
    group.add_argument("--confirmation-strength", type=float)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--execute-authorized", action="store_true")
    args = parser.parse_args()
    if not args.execute_authorized or os.environ.get("MUT_D0_EXECUTION_AUTHORIZED") != "YES":
        raise SystemExit("MUT-D0 execution requires CLI and environment authorization")
    if args.strength_index is not None:
        if args.strength_index < 0 or args.strength_index >= len(STRENGTHS):
            raise SystemExit("Invalid strength index")
        strength = STRENGTHS[args.strength_index]
        case_id = f"MUT-DEV-{args.strength_index:02d}"
        payload, ledger = execute_development(strength)
    else:
        strength = float(args.confirmation_strength)
        if strength not in STRENGTHS:
            raise SystemExit("Confirmation strength must be a frozen tested strength")
        case_id = "MUT-HOLDOUT-01"
        payload, ledger = execute_confirmation(strength)
    output = Path(args.output_root) / case_id / args.run_id
    if output.exists():
        raise SystemExit(f"Refusing to overwrite {output}")
    output.mkdir(parents=True)
    payload.update(
        {
            "case_id": case_id,
            "run_id": args.run_id,
            "design_version": "MUT-D0.0",
            "reporting_contract": "MUT-D0-v2.9",
            "processes": 1,
            "threads": 1,
        }
    )
    result = output / "case_result.json"
    events = output / "event_ledger.csv"
    result.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    write_csv(events, ledger)
    manifest = {
        "case_id": case_id,
        "run_id": args.run_id,
        "python": sys.version,
        "platform": platform.platform(),
        "thread_environment": {
            key: os.environ.get(key)
            for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")
        },
        "outputs": {result.name: sha256(result), events.name: sha256(events)},
    }
    (output / "case_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps({"case_id": case_id, "run_id": args.run_id, "classification": payload["classification"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
