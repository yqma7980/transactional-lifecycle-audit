from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

DESIGN_VERSION = "P6R-F05-F07.0"
IMPLEMENTATION_VERSION = "P6R-IMPLEMENTATION-0.1"
EXPECTED_FREEZE_MANIFEST_SHA256 = (
    "88e32f884eb2f99236dae4d2dacc5d9bd74cf5a02417c0fae52eb4d644e53aee"
)
METHOD_IDS = (
    "M1_FINAL",
    "M2_CKPT",
    "M3_STATE",
    "M4_OPERATOR",
    "M5_META",
    "M6_TLA",
)
NOT_APPLICABLE = {
    "M2_CKPT": "NOT_APPLICABLE_CHECKPOINT_RESTART_ABSENT",
    "M3_STATE": "NOT_APPLICABLE_SCHEMA_INSUFFICIENT",
}
NULL_THRESHOLDS = {
    key: 2.2737367544323206e-13
    for key in (
        "M_ALPHA",
        "M_GP",
        "M_J",
        "M_OUTPUT_R",
        "M_OUTPUT_W",
        "M_R",
        "M_REACTION",
        "M_X",
    )
}
FORBIDDEN_DETECTOR_KEYS = frozenset(
    {
        "case_id",
        "case_role",
        "family_id",
        "expected_lifecycle_verdict",
        "expected_classification",
        "observed_lifecycle_verdict",
        "observed_classification",
        "selection_basis",
        "strength_index",
        "z_family",
        "z_residual",
        "z_tangent",
    }
)


class ContractError(RuntimeError):
    """Raised before any result directory is created."""


class AuthorizationError(ContractError):
    """Raised when either formal-execution authorization lock is absent."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json_ready(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_ready(item) for item in value]
    if hasattr(value, "tolist"):
        return _json_ready(value.tolist())
    if isinstance(value, Path):
        return value.as_posix()
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(
        _json_ready(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("ascii")).hexdigest()


def require_execution_authorized(
    cli_authorized: bool, environ: Mapping[str, str] | None = None
) -> None:
    env = os.environ if environ is None else environ
    if not cli_authorized or env.get("P6R_EXECUTION_AUTHORIZED") != "YES":
        raise AuthorizationError(
            "P6R formal projection requires --execute-authorized and "
            "P6R_EXECUTION_AUTHORIZED=YES"
        )


def require_single_thread_environment(environ: Mapping[str, str] | None = None) -> None:
    env = os.environ if environ is None else environ
    for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        if env.get(name) != "1":
            raise ContractError(f"{name}=1 is required for formal projection")


def require_descendant(path: Path, parent: Path) -> Path:
    resolved_path = path.resolve()
    resolved_parent = parent.resolve()
    try:
        resolved_path.relative_to(resolved_parent)
    except ValueError as exc:
        raise ContractError(f"result path escapes authorized root: {path}") from exc
    return resolved_path


def assert_no_forbidden_keys(value: Any, location: str = "payload") -> None:
    if isinstance(value, Mapping):
        bad = FORBIDDEN_DETECTOR_KEYS.intersection(str(key) for key in value)
        if bad:
            raise ContractError(f"forbidden detector keys at {location}: {sorted(bad)}")
        for key, item in value.items():
            assert_no_forbidden_keys(item, f"{location}.{key}")
    elif isinstance(value, (tuple, list)):
        for index, item in enumerate(value):
            assert_no_forbidden_keys(item, f"{location}[{index}]")

