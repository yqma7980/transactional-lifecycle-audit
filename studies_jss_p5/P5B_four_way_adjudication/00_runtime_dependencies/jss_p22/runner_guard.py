from __future__ import annotations

import json
import os
from pathlib import Path

from .common import CaseSpec, file_sha256


ENV_LOCK = "JSS_FORMAL_MATRIX_AUTHORIZED"


def require_formal_authorization(
    root: Path,
    spec: CaseSpec,
    run_id: str,
    *,
    cli_lock: bool,
) -> Path:
    if not cli_lock or os.environ.get(ENV_LOCK) != "YES":
        raise PermissionError("formal execution requires CLI and environment locks")
    if run_id not in {"run_1", "run_2"}:
        raise ValueError("run_id must be run_1 or run_2")
    if spec.effective_partition == "DEVELOPMENT":
        activation = root / "JSS_P2_2_DEVELOPMENT_ACTIVATION.json"
        required_status = "DEVELOPMENT_ACTIVE"
        output = root / "results" / "development" / spec.case_id / run_id
    elif spec.effective_partition == "CONFIRMATION_HELD_OUT":
        activation = root / "JSS_P2_2_HELDOUT_ACTIVATION.json"
        required_status = "HELDOUT_ACTIVE"
        output = root / "results" / "heldout" / spec.case_id / run_id
    else:
        raise PermissionError("case partition is not authorized for prospective execution")
    if not activation.is_file():
        raise PermissionError(f"missing activation manifest: {activation.name}")
    payload = json.loads(activation.read_text(encoding="utf-8"))
    if payload.get("status") != required_status or payload.get("execution_authorized") is not True:
        raise PermissionError("activation manifest is not active")
    if spec.case_id not in payload.get("authorized_case_ids", []):
        raise PermissionError("case is absent from the activation allowlist")
    if spec.effective_partition == "CONFIRMATION_HELD_OUT":
        freeze = root / "results" / "development" / "final" / "development_execution_freeze.json"
        if not freeze.is_file():
            raise PermissionError("held-out execution requires frozen development evidence")
        if payload.get("development_freeze_sha256") != file_sha256(freeze):
            raise PermissionError("held-out activation does not bind the development freeze")
    if output.exists():
        raise FileExistsError(output)
    return output
