from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .adapters import adapter_for_subject
from .adjudication import adjudicate
from .cases import load_case_matrix
from .heldout_guard import select_heldout_case
from .heldout_mapping import heldout_mapping_for_case
from .heldout_runtime import execute_heldout_runtime
from .runtime import RUNTIME_IMPLEMENTATION_REVISION, RuntimeRecord, jsonable
from .runtime_schema import validate_runtime_observation_payload
from .schema import validate_case_result_payload


CASE_MANIFEST_SCHEMA = "JSS-P5B3-HELDOUT-CASE-MANIFEST-1.0"
EVENT_LEDGER_SCHEMA = "JSS-P5B3-HELDOUT-EVENT-LEDGER-1.0"
HELDOUT_EXECUTION_REVISION = "JSS-P5B3-HELDOUT-1.0"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json_new(path: Path, payload: Any) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(jsonable(payload), handle, indent=2, sort_keys=True, ensure_ascii=True)
        handle.write("\n")


def _input_hashes(root: Path) -> dict[str, str]:
    paths = (
        "P5B3_HELDOUT_EXECUTION_AUTHORIZATION.json",
        "P5B3_HELDOUT_RUNTIME_MAPPING.csv",
        "00_frozen_inputs/P5B2/P5B2_HELDOUT_ACTIVATION_MANIFEST.json",
        "00_frozen_inputs/P5B2/P5B2_heldout_case_matrix.csv",
        "00_frozen_inputs/P5B2/P5B2_SOURCE_MANIFEST.json",
        "src/jss_p5b/adjudication.py",
        "src/jss_p5b/adapters.py",
        "src/jss_p5b/heldout_guard.py",
        "src/jss_p5b/heldout_mapping.py",
        "src/jss_p5b/heldout_runtime.py",
        "src/jss_p5b/heldout_executor.py",
    )
    return {relative: _sha256(root / relative) for relative in paths}


def execute_heldout_case(
    root: Path,
    *,
    case_id: str,
    run_id: str,
    case_result_path: Path,
) -> dict[str, Any]:
    case = select_heldout_case(load_case_matrix(root), case_id)
    mapping = heldout_mapping_for_case(root, case)
    record = execute_heldout_runtime(case, run_id, mapping.runtime_mode)
    if not isinstance(record, RuntimeRecord):
        raise TypeError("held-out runtime adapter did not return RuntimeRecord")
    if tuple(record.raw.evidence_tokens) != mapping.evidence_tokens:
        raise RuntimeError(f"held-out evidence token drift for {case_id}")
    if record.raw.lifecycle_signals.active_names != mapping.lifecycle_signals:
        raise RuntimeError(f"held-out lifecycle signal drift for {case_id}")
    if record.raw.packet_a.differing_fields(record.raw.packet_b) != mapping.expected_packet_mismatch:
        raise RuntimeError(f"held-out replay packet mismatch drift for {case_id}")

    request = adapter_for_subject(case.subject_id).adapt(case, record.raw, run_id=run_id)
    result = adjudicate(request)
    case_payload = result.to_dict()
    validate_case_result_payload(case_payload)
    if not case_payload["pass_flag"]:
        raise RuntimeError(
            f"held-out case missed its frozen verdict: {case_id} -> "
            f"{case_payload['observed_outcome']}"
        )

    run_dir = case_result_path.parent
    if run_dir.exists():
        raise FileExistsError(f"held-out run directory already exists: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=False)
    observation_path = run_dir / "runtime_observation.json"
    ledger_path = run_dir / "event_ledger.json"
    manifest_path = run_dir / "case_manifest.json"
    observation_payload = record.to_dict()
    validate_runtime_observation_payload(observation_payload)
    _write_json_new(case_result_path, case_payload)
    _write_json_new(observation_path, observation_payload)
    _write_json_new(
        ledger_path,
        {
            "schema_version": EVENT_LEDGER_SCHEMA,
            "execution_revision": HELDOUT_EXECUTION_REVISION,
            "runtime_implementation_revision": RUNTIME_IMPLEMENTATION_REVISION,
            "case_id": case_id,
            "run_id": run_id,
            "subject_id": case.subject_id,
            "event_count": len(record.events),
            "events": record.events,
            "semantic_fingerprint": record.semantic_fingerprint,
        },
    )
    output_files = {
        path.name: {"sha256": _sha256(path), "bytes": path.stat().st_size}
        for path in (case_result_path, observation_path, ledger_path)
    }
    _write_json_new(
        manifest_path,
        {
            "schema_version": CASE_MANIFEST_SCHEMA,
            "execution_revision": HELDOUT_EXECUTION_REVISION,
            "runtime_implementation_revision": RUNTIME_IMPLEMENTATION_REVISION,
            "case_id": case_id,
            "run_id": run_id,
            "subject_id": case.subject_id,
            "partition": "HELD_OUT",
            "expected_verdict": case.target_verdict.value,
            "observed_verdict": case_payload["four_way_verdict"],
            "pass_flag": case_payload["pass_flag"],
            "fresh_process": True,
            "processes": 1,
            "threads": 1,
            "runtime_semantic_fingerprint": record.semantic_fingerprint,
            "inputs": _input_hashes(root),
            "outputs": output_files,
            "manifest_self_hash_embedded": False,
        },
    )
    return {
        "case_id": case_id,
        "run_id": run_id,
        "verdict": case_payload["four_way_verdict"],
        "pass_flag": case_payload["pass_flag"],
        "runtime_semantic_fingerprint": record.semantic_fingerprint,
        "run_directory": run_dir.as_posix(),
        "manifest_sha256": _sha256(manifest_path),
    }
