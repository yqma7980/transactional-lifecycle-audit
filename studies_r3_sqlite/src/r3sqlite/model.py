from __future__ import annotations

from enum import Enum


class Verdict(str, Enum):
    INVARIANT = "INVARIANT"
    DETECTED = "DETECTED"
    INVALID = "INVALID"
    UNSUPPORTED = "UNSUPPORTED"


OBLIGATION_ORDER = ("O1", "O2", "O3", "O4", "O5")

