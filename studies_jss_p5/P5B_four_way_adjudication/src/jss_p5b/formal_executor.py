from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .adapters import adapter_for_subject
from .adjudication import adjudicate
from .cases import load_case_matrix
from .development_guard import select_development_case
from .runtime import RUNTIME_IMPLEMENTATION_REVISION, RuntimeRecord, jsonable
from .runtime_local import execute_local_runtime
from .runtime_mapping import mapping_for_case
from .runtime_s01 import execute_s01_runtime
from .runtime_schema import validate_runtime_observation_payload
from .schema import validate_case_result_payload


CASE_MANIFEST_SCHEMA = "JSS-P5B1-CASE-MANIFEST-1.0"
EVENT_LEDGER_SCHEMA = "JSS-P5B1-EVENT-LEDGER-1.0"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json_new(path: Path, payload: Any) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(jsonable(payload), handle, indent=2, sort_keys=True, ensure_ascii=True)
        handle.write("\n")


def _input_hashes(root: Path) -> dict[str, str]:
    paths = (
        "P5B_DEVELOPMENT_ACTIVATION.json",
        "P5B_FORMAL_IMPLEMENTATION_FREEZE.json",
        "P5B1_EXECUTION_ADAPTER_FREEZE.json",
        "P5B1_CASE_RUNTIME_MAPPING.csv",
        "src/jss_p5b/adjudication.py",
        "src/jss_p5b/adapters.py",
        "src/jss_p5b/formal_executor.py",
        "src/jss_p5b/runtime.py",
        "src/jss_p5b/runtime_local.py",
        "src/jss_p5b/runtime_s01.py",
    )
    return {relative: _sha256(root / relative) for relative in paths}


def execute_development_case(
    root: Path,
    *,
    case_id: str,
    run_id: str,
    case_result_path: Path,
) -> dict[str, Any]:
    cases = load_case_matrix(root)
    case = select_development_case(cases, case_id)
    mapping = mapping_for_case(root, case)
    if case.subject_id == "JSS-S01":
        record = execute_s01_runtime(case, run_id, mapping.runtime_mode)
    else:
        record = execute_local_runtime(case, run_id, mapping.runtime_mode)
    if not isinstance(record, RuntimeRecord):
        raise TypeError("runtime adapter did not return RuntimeRecord")
    if tuple(record.raw.evidence_tokens) != mapping.evidence_tokens:
        raise RuntimeError(f"runtime evidence token drift for {case_id}")
    if record.raw.lifecycle_signals.active_names != mapping.lifecycle_signals:
        raise RuntimeError(f"runtime lifecycle signal drift for {case_id}")
    if record.raw.packet_a.differing_fields(record.raw.packet_b) != mapping.expected_packet_mismatch:
        raise RuntimeError(f"runtime replay packet mismatch drift for {case_id}")

    request = adapter_for_subject(case.subject_id).adapt(case, record.raw, run_id=run_id)
    result = adjudicate(request)
    case_payload = result.to_dict()
    validate_case_result_payload(case_payload)
    if not case_payload["pass_flag"]:
        raise RuntimeError(
            f"formal DEVELOPMENT case missed its frozen verdict: {case_id} -> "
            f"{case_payload['observed_outcome']}"
        )

    run_dir = case_result_path.parent
    if run_dir.exists():
        raise FileExistsError(f"formal run directory already exists: {run_dir}")
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
            "implementation_revision": RUNTIME_IMPLEMENTATION_REVISION,
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
            "implementation_revision": RUNTIME_IMPLEMENTATION_REVISION,
            "case_id": case_id,
            "run_id": run_id,
            "subject_id": case.subject_id,
            "partition": "DEVELOPMENT",
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
