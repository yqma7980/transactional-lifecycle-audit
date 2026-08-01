from __future__ import annotations

import dataclasses
import hashlib
import json
from typing import Any

import numpy as np


def _canonical(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return _canonical(dataclasses.asdict(value))
    if isinstance(value, np.ndarray):
        if np.issubdtype(value.dtype, np.floating):
            return {"shape": list(value.shape), "float_hex": [float(x).hex() for x in value.ravel(order="C")]}
        return {"shape": list(value.shape), "values": value.ravel(order="C").tolist()}
    if isinstance(value, (np.floating, float)):
        return {"float_hex": float(value).hex()}
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, dict):
        return {str(key): _canonical(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    if value is None or isinstance(value, (str, bool)):
        return value
    raise TypeError(f"Unsupported canonical value: {type(value)!r}")


def canonical_json(value: Any) -> str:
    return json.dumps(_canonical(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("ascii")).hexdigest()


def file_sha256(path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
