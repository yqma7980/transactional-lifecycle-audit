from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Mapping

from .cases import CaseSpec, load_case_matrix
from .model import ContractError
from .runner_guard import validate_protected_inputs


ACTIVATION_FILENAME = "P5B_DEVELOPMENT_ACTIVATION.json"
ENVIRONMENT_LOCK = "JSS_P5B_DEVELOPMENT_AUTHORIZED"
ENVIRONMENT_UNLOCK_VALUE = "YES"
RUN_ID_PATTERN = re.compile(r"run_[12]\Z")
EXPECTED_STATUS = "DEVELOPMENT_ACTIVE_NOT_EXECUTED"
EXPECTED_DESIGN_VERSION = "JSS-P5B.0"
EXPECTED_IMPLEMENTATION_VERSION = "JSS-P5B-IMPL-1.0a"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _partition_ids(cases: tuple[CaseSpec, ...], partition: str) -> tuple[str, ...]:
    return tuple(sorted(case.case_id for case in cases if case.partition == partition))


def select_development_case(cases: tuple[CaseSpec, ...], case_id: str) -> CaseSpec:
    matches = [case for case in cases if case.case_id == case_id]
    if len(matches) != 1:
        raise ContractError(f"unknown formal case ID: {case_id}")
    case = matches[0]
    if case.partition == "HELD_OUT":
        raise ContractError(f"held-out case remains sealed: {case_id}")
    if case.partition != "DEVELOPMENT":
        raise ContractError(f"case is not a development case: {case_id}")
    return case


def validate_activation_payload(
    payload: Mapping[str, Any],
    cases: tuple[CaseSpec, ...],
) -> None:
    required = {
        "activation_id",
        "activation_status",
        "design_version",
        "implementation_version",
        "development_execution_authorized",
        "held_out_access_authorized",
        "formal_results_exist",
        "development_case_ids",
        "held_out_case_ids",
        "required_cli_lock",
        "required_environment_lock",
        "required_environment_value",
        "allowed_run_ids",
        "protected_implementation_files",
        "formal_review_freeze_sha256",
    }
    if set(payload) != required:
        raise ContractError("development activation keys differ from the frozen contract")
    if payload["activation_status"] != EXPECTED_STATUS:
        raise ContractError("development activation is not active")
    if payload["design_version"] != EXPECTED_DESIGN_VERSION:
        raise ContractError("development activation design version drift")
    if payload["implementation_version"] != EXPECTED_IMPLEMENTATION_VERSION:
        raise ContractError("development activation implementation version drift")
    if payload["development_execution_authorized"] is not True:
        raise ContractError("development execution is not authorized")
    if payload["held_out_access_authorized"] is not False:
        raise ContractError("held-out access is unexpectedly authorized")
    if payload["formal_results_exist"] is not False:
        raise ContractError("activation cannot claim pre-existing formal results")
    if tuple(sorted(payload["development_case_ids"])) != _partition_ids(cases, "DEVELOPMENT"):
        raise ContractError("development activation case set drift")
    if tuple(sorted(payload["held_out_case_ids"])) != _partition_ids(cases, "HELD_OUT"):
        raise ContractError("held-out seal case set drift")
    if payload["required_cli_lock"] != "--execute-authorized":
        raise ContractError("development CLI lock drift")
    if payload["required_environment_lock"] != ENVIRONMENT_LOCK:
        raise ContractError("development environment lock name drift")
    if payload["required_environment_value"] != ENVIRONMENT_UNLOCK_VALUE:
        raise ContractError("development environment lock value drift")
    if payload["allowed_run_ids"] != ["run_1", "run_2"]:
        raise ContractError("development run ID contract drift")
    if not isinstance(payload["protected_implementation_files"], dict):
        raise ContractError("protected implementation hash map is missing")
    freeze_hash = payload["formal_review_freeze_sha256"]
    if not isinstance(freeze_hash, str) or len(freeze_hash) != 64:
        raise ContractError("formal review freeze hash is invalid")


def _validate_implementation_hashes(root: Path, payload: Mapping[str, Any]) -> None:
    for relative, expected in payload["protected_implementation_files"].items():
        path = root / relative
        if not path.is_file():
            raise ContractError(f"protected implementation file is missing: {relative}")
        actual = _sha256(path)
        if actual != expected:
            raise ContractError(
                f"protected implementation hash drift for {relative}: {actual} != {expected}"
            )
    freeze_path = root / "P5B_FORMAL_IMPLEMENTATION_FREEZE.json"
    if not freeze_path.is_file():
        raise ContractError("formal review freeze is missing")
    if _sha256(freeze_path) != payload["formal_review_freeze_sha256"]:
        raise ContractError("formal review freeze hash drift")


def authorize_development(
    root: Path,
    *,
    case_id: str,
    run_id: str,
    cli_authorized: bool,
    environment: Mapping[str, str] | None = None,
) -> Path:
    cases = load_case_matrix(root)
    select_development_case(cases, case_id)
    if RUN_ID_PATTERN.fullmatch(run_id) is None:
        raise ContractError(f"invalid development run ID: {run_id}")
    env = os.environ if environment is None else environment
    if not cli_authorized:
        raise ContractError("CLI development authorization is absent")
    if env.get(ENVIRONMENT_LOCK) != ENVIRONMENT_UNLOCK_VALUE:
        raise ContractError("environment development authorization is absent")
    activation_path = root / ACTIVATION_FILENAME
    if not activation_path.is_file():
        raise ContractError("development activation manifest is absent")
    payload = json.loads(activation_path.read_text(encoding="utf-8"))
    validate_activation_payload(payload, cases)
    validate_protected_inputs(root)
    _validate_implementation_hashes(root, payload)
    return root / "results" / "development" / case_id / run_id / "case_result.json"
