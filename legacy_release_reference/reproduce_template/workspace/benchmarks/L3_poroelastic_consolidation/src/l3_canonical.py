"""Load the frozen L2 canonical serializer without importing its package facade."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import sys
from typing import Any


L2_STATE_SHA256 = "05c9684d1bfcf5cb8b0c446795f697ecff6860edef2649af16a4baf7db62e67d"
_MODULE_NAME = "_l3_authoritative_l2_state"
_SOURCE = Path(__file__).resolve().parents[2] / "L2_host_lifecycle" / "src" / "l2_state.py"


def _load_authoritative_module() -> Any:
    payload = _SOURCE.read_bytes()
    observed = hashlib.sha256(payload).hexdigest()
    if observed != L2_STATE_SHA256:
        raise RuntimeError(
            f"authoritative L2 serializer hash mismatch: {observed}"
        )
    existing = sys.modules.get(_MODULE_NAME)
    if existing is not None:
        return existing
    spec = importlib.util.spec_from_file_location(_MODULE_NAME, _SOURCE)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load authoritative L2 serializer")
    module = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE_NAME] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(_MODULE_NAME, None)
        raise
    return module


_authoritative = _load_authoritative_module()
canonical_json = _authoritative.canonical_json
canonical_hash = _authoritative.canonical_hash

__all__ = ["L2_STATE_SHA256", "canonical_json", "canonical_hash"]
