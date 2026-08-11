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


AUTHORIZATION_FILENAME = "P5B3_HELDOUT_EXECUTION_AUTHORIZATION.json"
STATIC_ACTIVATION = Path("00_frozen_inputs/P5B2/P5B2_HELDOUT_ACTIVATION_MANIFEST.json")
STATIC_MATRIX = Path("00_frozen_inputs/P5B2/P5B2_heldout_case_matrix.csv")
P5B2_SOURCE_MANIFEST = Path("00_frozen_inputs/P5B2/P5B2_SOURCE_MANIFEST.json")
ENVIRONMENT_LOCK = "JSS_P5B_HELDOUT_AUTHORIZED"
ENVIRONMENT_UNLOCK_VALUE = "YES"
RUN_ID_PATTERN = re.compile(r"run_[12]\Z")
EXPECTED_DESIGN_VERSION = "JSS-P5B.0"
EXPECTED_IMPLEMENTATION_VERSION = "JSS-P5B-IMPL-1.0a"
EXPECTED_STATIC_HASH = "c47ff42e8abfdf74874d6c4a2a4f5554a77a407a79ed012fe3bd3660e0609e5b"
EXPECTED_MATRIX_HASH = "453240fca5509bdb031b0a3b796c12bf5b4e35c102e1d457fc58869a65c8d055"
EXPECTED_P5B2_SOURCE_HASH = "b05e33850c7073c1d443804ad908eb194d2c1372b0f133b9136cd983a6a78f37"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _heldout_ids(cases: tuple[CaseSpec, ...]) -> tuple[str, ...]:
    return tuple(sorted(case.case_id for case in cases if case.partition == "HELD_OUT"))


def select_heldout_case(cases: tuple[CaseSpec, ...], case_id: str) -> CaseSpec:
    matches = [case for case in cases if case.case_id == case_id]
    if len(matches) != 1:
        raise ContractError(f"unknown formal case ID: {case_id}")
    case = matches[0]
    if case.partition != "HELD_OUT":
        raise ContractError(f"case is not held out: {case_id}")
    return case


def _validate_static_activation(root: Path, cases: tuple[CaseSpec, ...]) -> None:
    for relative, expected in (
        (STATIC_ACTIVATION, EXPECTED_STATIC_HASH),
        (STATIC_MATRIX, EXPECTED_MATRIX_HASH),
        (P5B2_SOURCE_MANIFEST, EXPECTED_P5B2_SOURCE_HASH),
    ):
        path = root / relative
        if not path.is_file() or _sha256(path) != expected:
            raise ContractError(f"P5B.2 frozen input drift: {relative.as_posix()}")
    payload = json.loads((root / STATIC_ACTIVATION).read_text(encoding="utf-8"))
    if payload["status"] != "HELD_OUT_STATIC_ACCESS_PREREQUISITES_SATISFIED_EXECUTION_NOT_AUTHORIZED":
        raise ContractError("P5B.2 static activation status drift")
    if payload["held_out_static_access_authorized"] is not True:
        raise ContractError("held-out static access is not qualified")
    if payload["held_out_execution_authorized"] is not False:
        raise ContractError("P5B.2 static freeze must remain non-executing")
    if payload["held_out_results_exist"] is not False:
        raise ContractError("P5B.2 freeze claims pre-existing held-out results")
    if tuple(sorted(payload["held_out_case_ids"])) != _heldout_ids(cases):
        raise ContractError("P5B.2 held-out case set drift")
    if payload["held_out_case_matrix_sha256"] != EXPECTED_MATRIX_HASH:
        raise ContractError("P5B.2 held-out matrix binding drift")
    bound = payload["bound_hashes"]
    required = {
        "adjudication_contract_sha256": "f58f5967e95f81e2a98adc04bf4a4f1deff1b8a4f89da52f5dcb855c2cab4849",
        "case_matrix_sha256": "a4583c96c8bcd847816ec1a72493c6a326a2a7eb5fe787efa68edd1c92ded0e3",
        "development_activation_sha256": "a56eb7ae978cc257e65ce952fc3df69d64f0ba4c23017a138aa5434655ebf196",
        "development_source_manifest_sha256": "e77c395f7eba21d5e21d00a89ea66900d31e811f8f542c28e9540786d652f1e6",
        "implementation_freeze_sha256": "b37ef34486e87d31525ec567bfcc52360fac0938ee9c9139521225eac32d7320",
    }
    if any(bound.get(key) != value for key, value in required.items()):
        raise ContractError("P5B.2 bound hashes drift")


def _validate_authorization(root: Path, cases: tuple[CaseSpec, ...]) -> None:
    path = root / AUTHORIZATION_FILENAME
    if not path.is_file():
        raise ContractError("held-out execution authorization is absent")
    payload: Mapping[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    if payload["authorization_status"] != "HELD_OUT_EXECUTION_AUTHORIZED_BY_USER":
        raise ContractError("held-out authorization status drift")
    if payload["held_out_execution_authorized"] is not True:
        raise ContractError("held-out execution is not authorized")
    if payload["design_version"] != EXPECTED_DESIGN_VERSION:
        raise ContractError("held-out authorization design drift")
    if payload["implementation_version"] != EXPECTED_IMPLEMENTATION_VERSION:
        raise ContractError("held-out authorization implementation drift")
    if tuple(sorted(payload["authorized_case_ids"])) != _heldout_ids(cases):
        raise ContractError("held-out authorization case set drift")
    if payload["allowed_run_ids"] != ["run_1", "run_2"]:
        raise ContractError("held-out authorization run IDs drift")
    if payload["required_cli_lock"] != "--execute-authorized":
        raise ContractError("held-out CLI lock drift")
    if payload["required_environment_lock"] != ENVIRONMENT_LOCK:
        raise ContractError("held-out environment lock drift")
    if payload["required_environment_value"] != ENVIRONMENT_UNLOCK_VALUE:
        raise ContractError("held-out environment unlock value drift")
    if not all(payload[key] is True for key in ("no_replacement", "no_reseeding", "no_threshold_change", "no_tuning")):
        raise ContractError("held-out no-post-hoc constraints drift")
    if payload["source_static_activation_sha256"] != EXPECTED_STATIC_HASH:
        raise ContractError("authorization static activation binding drift")
    if payload["source_heldout_case_matrix_sha256"] != EXPECTED_MATRIX_HASH:
        raise ContractError("authorization held-out matrix binding drift")
    if payload["source_p5b2_manifest_sha256"] != EXPECTED_P5B2_SOURCE_HASH:
        raise ContractError("authorization P5B.2 manifest binding drift")


def authorize_heldout(
    root: Path,
    *,
    case_id: str,
    run_id: str,
    cli_authorized: bool,
    environment: Mapping[str, str] | None = None,
) -> Path:
    cases = load_case_matrix(root)
    select_heldout_case(cases, case_id)
    if RUN_ID_PATTERN.fullmatch(run_id) is None:
        raise ContractError(f"invalid held-out run ID: {run_id}")
    env = os.environ if environment is None else environment
    if not cli_authorized:
        raise ContractError("CLI held-out authorization is absent")
    if env.get(ENVIRONMENT_LOCK) != ENVIRONMENT_UNLOCK_VALUE:
        raise ContractError("environment held-out authorization is absent")
    validate_protected_inputs(root)
    _validate_static_activation(root, cases)
    _validate_authorization(root, cases)
    result = root / "results" / "heldout" / case_id / run_id / "case_result.json"
    if result.parent.exists():
        raise FileExistsError(f"held-out run directory already exists: {result.parent}")
    return result
