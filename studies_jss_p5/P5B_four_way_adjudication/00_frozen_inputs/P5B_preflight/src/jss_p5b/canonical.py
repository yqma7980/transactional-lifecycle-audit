from __future__ import annotations

import dataclasses
import hashlib
import json
from enum import Enum
from pathlib import Path
from typing import Any, Mapping


def canonicalize(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return canonicalize(dataclasses.asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, Mapping):
        return {str(key): canonicalize(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, (list, tuple)):
        return [canonicalize(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return [canonicalize(item) for item in sorted(value, key=str)]
    if isinstance(value, float):
        return {"__float_hex__": value.hex()}
    if value is None or isinstance(value, (bool, int, str)):
        return value
    raise TypeError(f"unsupported canonical type: {type(value).__name__}")


def canonical_json(value: Any) -> str:
    return json.dumps(
        canonicalize(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("ascii")).hexdigest()

