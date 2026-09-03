from __future__ import annotations

from collections.abc import Mapping

from .model import OBLIGATION_ORDER, Verdict


def adjudicate(
    *,
    capability_complete: bool,
    eligible: bool,
    signals: Mapping[str, bool],
) -> tuple[Verdict, tuple[str, ...]]:
    """Apply the frozen four-way priority without inventing missing evidence."""
    if not capability_complete:
        return Verdict.UNSUPPORTED, ("required_observation_missing",)
    if not eligible:
        return Verdict.INVALID, ("authoritative_entry_mismatch",)
    active = tuple(name for name in OBLIGATION_ORDER if bool(signals.get(name, False)))
    if active:
        return Verdict.DETECTED, active
    return Verdict.INVARIANT, ("eligible_observed_history_invariant",)

