from __future__ import annotations

from dataclasses import asdict
import importlib.util
import json
from pathlib import Path
from typing import Any

from . import IMPLEMENTATION_VERSION, LEDGER_SCHEMA_VERSION
from .common import CaseSpec, file_sha256, write_csv_new, write_json_new
from .metrics import build_common_metrics, evaluate_baselines, full_verdict


def _load_oracle(root: Path):
    path = root / "oracles" / "jss_p22_oracle.py"
    spec = importlib.util.spec_from_file_location("_jss_p22_oracle", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load independent oracle")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _adapter(subject_id: str):
    if subject_id == "JSS-S01":
        from . import s01_adapter as adapter
    elif subject_id == "JSS-S02":
        from . import s02_adapter as adapter
    elif subject_id == "JSS-S03":
        from . import s03_adapter as adapter
    else:
        raise ValueError(f"unsupported subject {subject_id}")
    return adapter


def _event_csv_rows(events: tuple[dict[str, Any], ...]) -> list[dict[str, Any]]:
    fields = (
        "sequence",
        "event_type",
        "accepted",
        "candidate_id",
        "owner",
        "field_name",
        "before_hash",
        "after_hash",
        "source_plane",
        "residual_version",
        "tangent_version",
    )
    return [{field: event.get(field) for field in fields} for event in events]


def execute_case(
    root: Path,
    spec: CaseSpec,
    run_id: str,
    output_directory: Path,
    *,
    operator_drift_gate: float,
) -> dict[str, Any]:
    if output_directory.exists():
        raise FileExistsError(output_directory)
    outcome = _adapter(spec.subject_id).execute(spec, run_id)
    metrics = build_common_metrics(
        spec, outcome, operator_drift_gate=operator_drift_gate
    )
    baselines = evaluate_baselines(spec, metrics)
    verdict = full_verdict(spec, metrics)
    oracle = _load_oracle(root)
    expected_findings = oracle.expected_findings(spec.subject_id, spec.fault_id)
    observed_findings = {
        key: bool(metrics[key]) for key in expected_findings
    }
    oracle_match = observed_findings == expected_findings
    conventional_gates_pass = all(
        bool(metrics[key])
        for key in ("finite", "converged", "accuracy_gate_pass", "balance_gate_pass")
    )
    pass_flag = (
        verdict == spec.expected_verdict
        and oracle_match
        and conventional_gates_pass
        and metrics["all_finding_fields_present"]
    )
    result = {
        "design_version": "JSS-P1.0",
        "implementation_version": IMPLEMENTATION_VERSION,
        "ledger_schema_version": LEDGER_SCHEMA_VERSION,
        "case_id": spec.case_id,
        "run_id": run_id,
        "partition": spec.effective_partition,
        "subject_id": spec.subject_id,
        "fault_id": spec.fault_id,
        "strength_id": spec.strength_id,
        "strength": spec.strength,
        "expected_verdict": spec.expected_verdict,
        "observed_verdict": verdict,
        "pass_flag": pass_flag,
        "conventional_gates_pass": conventional_gates_pass,
        "oracle_match": oracle_match,
        "expected_findings": expected_findings,
        "observed_findings": observed_findings,
        "metrics": metrics,
        "baselines": baselines,
        "adapter_diagnostics": outcome.diagnostics,
        "state_hashes": {
            "direct_accepted": outcome.direct_hash,
            "perturbed_accepted": outcome.perturbed_hash,
            "committed_before": outcome.committed_before_hash,
            "committed_after_trial": outcome.committed_after_trial_hash,
            "persistent_before": outcome.persistent_before_hash,
            "persistent_after": outcome.persistent_after_hash,
        },
    }
    ledger = {
        "ledger_schema_version": LEDGER_SCHEMA_VERSION,
        "case_id": spec.case_id,
        "run_id": run_id,
        "ground_truth": {
            "owner": spec.ground_truth_owner,
            "module": spec.ground_truth_module,
            "event": spec.ground_truth_event,
            "field": spec.ground_truth_field,
            "source_plane": spec.ground_truth_source_plane,
        },
        "events": list(outcome.events),
    }
    baseline_payload = {
        "case_id": spec.case_id,
        "run_id": run_id,
        "baselines": baselines,
        "ranking_weights": {
            "owner_field": 8,
            "event": 4,
            "restoration": 3,
            "output_reachability": 2,
            "version_incompatibility": 4,
            "first_drift_precedence": 1,
        },
    }

    output_directory.mkdir(parents=True, exist_ok=False)
    write_json_new(output_directory / "case_result.json", result)
    write_json_new(output_directory / "evidence_ledger.json", ledger)
    write_json_new(output_directory / "baseline_metrics.json", baseline_payload)
    write_csv_new(output_directory / "event_ledger.csv", _event_csv_rows(outcome.events))
    outputs = [
        "case_result.json",
        "evidence_ledger.json",
        "baseline_metrics.json",
        "event_ledger.csv",
    ]
    manifest = {
        "case_id": spec.case_id,
        "run_id": run_id,
        "files": {
            name: {
                "sha256": file_sha256(output_directory / name),
                "bytes": (output_directory / name).stat().st_size,
            }
            for name in outputs
        },
        "manifest_self_hash_embedded": False,
    }
    write_json_new(output_directory / "case_manifest.json", manifest)
    return result
