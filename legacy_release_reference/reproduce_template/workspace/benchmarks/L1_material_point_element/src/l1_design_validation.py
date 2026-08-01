"""Static validation of the frozen L1-D1.0 design inputs."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any


DESIGN_VERSION = "L1-D1.0"
SUMMARY_STATUSES = {"COMPLETE", "STOPPED_AT_MP_GATE", "STOPPED_AT_E1_GATE", "INVALID"}
SUBLEVEL_STATUSES = {"PASS", "FAIL", "BLOCKED", "INVALID"}
GATE_STATUSES = {"PASS", "FAIL", "BLOCKED", "NOT_APPLICABLE"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_summary_document(document: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = {
        "design_version",
        "execution_status",
        "implementation_hash",
        "case_count",
        "scenario_variant_count",
        "sublevels",
        "gate_families",
        "overall_pass",
        "claim_boundary",
    }
    missing = sorted(required - set(document))
    if missing:
        errors.append(f"missing summary fields: {missing}")
        return errors
    if document["design_version"] != DESIGN_VERSION:
        errors.append("design_version must be L1-D1.0")
    if document["execution_status"] not in SUMMARY_STATUSES:
        errors.append("invalid execution_status")
    implementation_hash = document["implementation_hash"]
    if not isinstance(implementation_hash, str) or len(implementation_hash) != 64:
        errors.append("implementation_hash must be a 64-character SHA-256")
    if document["case_count"] != 20:
        errors.append("case_count must equal 20")
    if document["scenario_variant_count"] != 45:
        errors.append("scenario_variant_count must equal 45")
    if not isinstance(document["overall_pass"], bool):
        errors.append("overall_pass must be boolean")
    if not isinstance(document["claim_boundary"], str) or len(document["claim_boundary"]) < 20:
        errors.append("claim_boundary is missing or too short")

    sublevels = document.get("sublevels", {})
    if set(sublevels) != {"L1-MP", "L1-E1"}:
        errors.append("sublevels must contain exactly L1-MP and L1-E1")
    else:
        for name, value in sublevels.items():
            if set(value) != {"status", "passed_cases", "failed_cases", "blocked_cases"}:
                errors.append(f"invalid sublevel fields for {name}")
            if value.get("status") not in SUBLEVEL_STATUSES:
                errors.append(f"invalid sublevel status for {name}")
            for field in ("passed_cases", "failed_cases", "blocked_cases"):
                if not isinstance(value.get(field), int) or value[field] < 0:
                    errors.append(f"invalid {field} for {name}")

    gates = document.get("gate_families", {})
    if not isinstance(gates, dict) or len(gates) < 8:
        errors.append("gate_families must contain at least eight gates")
    else:
        for name, value in gates.items():
            if set(value) != {"status", "hard_gate", "evidence"}:
                errors.append(f"invalid gate fields for {name}")
            if value.get("status") not in GATE_STATUSES:
                errors.append(f"invalid gate status for {name}")
            if not isinstance(value.get("hard_gate"), bool):
                errors.append(f"hard_gate must be boolean for {name}")
            if not isinstance(value.get("evidence"), list):
                errors.append(f"evidence must be a list for {name}")
    return errors


def synthetic_valid_summary() -> dict[str, Any]:
    gate = {"status": "PASS", "hard_gate": True, "evidence": ["synthetic"]}
    return {
        "design_version": DESIGN_VERSION,
        "execution_status": "STOPPED_AT_E1_GATE",
        "implementation_hash": "0" * 64,
        "case_count": 20,
        "scenario_variant_count": 45,
        "sublevels": {
            "L1-MP": {"status": "PASS", "passed_cases": 12, "failed_cases": 0, "blocked_cases": 0},
            "L1-E1": {"status": "BLOCKED", "passed_cases": 0, "failed_cases": 0, "blocked_cases": 8},
        },
        "gate_families": {f"gate_{index}": dict(gate) for index in range(8)},
        "overall_pass": False,
        "claim_boundary": "Synthetic schema-validation document only.",
    }



def validate_design(root: Path) -> dict[str, Any]:
    errors: list[str] = []
    with (root / "L1_case_matrix.csv").open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    case_ids = [row["case_id"] for row in rows]
    if len(rows) != 20 or len(set(case_ids)) != 20:
        errors.append("case matrix must contain 20 unique case IDs")
    outcome_count = sum(len(row["variants_required"].split(";")) for row in rows)
    if outcome_count != 45:
        errors.append(f"expanded outcome count is {outcome_count}, expected 45")
    mp_rows = [row for row in rows if row["sublevel"] == "L1-MP"]
    mp_outcomes = sum(len(row["variants_required"].split(";")) for row in mp_rows)
    if len(mp_rows) != 12 or mp_outcomes != 25:
        errors.append("L1-MP must contain 12 cases and 25 outcomes")
    e1_rows = [row for row in rows if row["sublevel"] == "L1-E1"]
    e1_outcomes = sum(len(row["variants_required"].split(";")) for row in e1_rows)
    if len(e1_rows) != 8 or e1_outcomes != 20:
        errors.append("L1-E1 must contain 8 cases and 20 outcomes")

    for row in rows:
        if row["hard_gate"] != "yes":
            errors.append(f"case is not a hard gate: {row['case_id']}")
        if not row["reference_oracle"] or not row["expected_safe"]:
            errors.append(f"missing oracle or expected safe result: {row['case_id']}")

    expected = json.loads((root / "expected_results_template.json").read_text(encoding="utf-8"))
    if expected.get("design_version") != DESIGN_VERSION:
        errors.append("expected-results design version mismatch")
    if expected.get("execution_status") != "OPEN_NOT_EXECUTED":
        errors.append("expected-results template was not preserved as design-only")

    schema = json.loads((root / "schemas" / "l1_run_summary.schema.json").read_text(encoding="utf-8"))
    required_summary_fields = set(schema.get("required", []))
    if required_summary_fields != {
        "design_version",
        "execution_status",
        "implementation_hash",
        "case_count",
        "scenario_variant_count",
        "sublevels",
        "gate_families",
        "overall_pass",
        "claim_boundary",
    }:
        errors.append("run-summary schema required fields changed")
    valid = synthetic_valid_summary()
    if validate_summary_document(valid):
        errors.append("synthetic valid summary was rejected")
    invalid = dict(valid)
    invalid["case_count"] = 19
    if not validate_summary_document(invalid):
        errors.append("synthetic invalid summary was accepted")

    with (root / "schemas" / "l1_call_ledger_columns.csv").open(

        "r", encoding="utf-8", newline=""
    ) as handle:
        ledger_columns = list(csv.DictReader(handle))
    if len(ledger_columns) != 40:
        errors.append(f"ledger has {len(ledger_columns)} columns, expected 40")

    manifest = json.loads((root / "design_manifest.json").read_text(encoding="utf-8"))
    for relative_path, expected_hash in manifest.get("source_sha256", {}).items():
        actual_hash = sha256_file(root / Path(relative_path))
        if actual_hash.lower() != expected_hash.lower():
            errors.append(f"design hash mismatch: {relative_path}")

    freeze = json.loads((root / "L1_MP_execution_freeze.json").read_text(encoding="utf-8"))
    if freeze.get("design_version") != DESIGN_VERSION or freeze.get("execution_scope") != "L1-MP_ONLY":
        errors.append("invalid L1-MP execution freeze")
    if freeze.get("e1_authorized") is not False:
        errors.append("L1-E1 must remain unauthorized")

    e1_freeze = json.loads(
        (root / "L1_E1_execution_freeze.json").read_text(encoding="utf-8")
    )
    if e1_freeze.get("design_version") != DESIGN_VERSION:
        errors.append("invalid L1-E1 design version")
    if e1_freeze.get("execution_scope") != "L1-E1_ONLY_AFTER_MP_PASS":
        errors.append("invalid L1-E1 execution scope")
    if e1_freeze.get("e1_authorized") is not True:
        errors.append("L1-E1 must be explicitly authorized")

    return {
        "passed": not errors,
        "errors": errors,
        "case_count": len(rows),
        "scenario_variant_count": outcome_count,
        "mp_case_count": len(mp_rows),
        "mp_scenario_variant_count": mp_outcomes,
        "e1_case_count": len(e1_rows),
        "e1_scenario_variant_count": e1_outcomes,
        "ledger_column_count": len(ledger_columns),
    }

