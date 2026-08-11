from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Mapping

from .model import ContractError


ENVIRONMENT_LOCK = "JSS_P5B_PREFLIGHT_AUTHORIZED"
ENVIRONMENT_UNLOCK_VALUE = "YES"
ALLOWED_PREFLIGHT_IDS = frozenset(
    {
        "P5B-PREFLIGHT-SAFE-NULL-S01",
        "P5B-PREFLIGHT-SAFE-NULL-S02",
        "P5B-PREFLIGHT-SAFE-NULL-S03",
    }
)
RUN_ID_PATTERN = re.compile(r"preflight_run_[12]\Z")

PROTECTED_HASHES = {
    "00_frozen_inputs/P5A/01_semantics/P5A_adjudication_contract.json": (
        "f58f5967e95f81e2a98adc04bf4a4f1deff1b8a4f89da52f5dcb855c2cab4849"
    ),
    "00_frozen_inputs/P5A/01_semantics/P5A_verdict_state_machine.md": (
        "f6323f1933ede306468fd6ed74897f7c71d9aca533c6e33491df12336e0e3859"
    ),
    "00_frozen_inputs/P5A/01_semantics/P5A_verdict_transition_table.csv": (
        "1ae49b51bc37a3dc6d5defa669da2e07bd7a01a1499a7285a99eb244226aa06c"
    ),
    "00_frozen_inputs/P5A/02_four_way/P5B_acceptance_gates.md": (
        "521254d7c1abff40495b9bf5bad670387fd369a6119dac7b75606280b6ed47fd"
    ),
    "00_frozen_inputs/P5A/02_four_way/P5B_benign_control_catalog.md": (
        "41349237d91339b5927cc653b9484b86811d156e93533c9179ef980a2c722544"
    ),
    "00_frozen_inputs/P5A/02_four_way/P5B_four_way_case_matrix.csv": (
        "a4583c96c8bcd847816ec1a72493c6a326a2a7eb5fe787efa68edd1c92ded0e3"
    ),
    "00_frozen_inputs/P5A/02_four_way/P5B_partition_and_heldout_rule.md": (
        "5c8086bc48bb414d8b0b0eb5798635d6526282c509498fefb65d37635a9f238a"
    ),
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_protected_inputs(root: Path) -> dict[str, str]:
    observed: dict[str, str] = {}
    for relative, expected in PROTECTED_HASHES.items():
        path = root / relative
        if not path.is_file():
            raise ContractError(f"protected freeze input is missing: {relative}")
        actual = _sha256(path)
        observed[relative] = actual
        if actual != expected:
            raise ContractError(
                f"protected freeze hash drift for {relative}: {actual} != {expected}"
            )
    return observed


def authorize_preflight(
    root: Path,
    *,
    preflight_id: str,
    run_id: str,
    cli_authorized: bool,
    environment: Mapping[str, str] | None = None,
) -> Path:
    if preflight_id not in ALLOWED_PREFLIGHT_IDS:
        raise ContractError(f"preflight ID is not authorized: {preflight_id}")
    if RUN_ID_PATTERN.fullmatch(run_id) is None:
        raise ContractError(f"invalid preflight run ID: {run_id}")
    env = os.environ if environment is None else environment
    if not cli_authorized:
        raise ContractError("CLI preflight authorization is absent")
    if env.get(ENVIRONMENT_LOCK) != ENVIRONMENT_UNLOCK_VALUE:
        raise ContractError("environment preflight authorization is absent")
    validate_protected_inputs(root)
    return root / "qa" / "safe_null_runtime" / preflight_id / run_id / "case_result.json"

