from __future__ import annotations

import copy
import math
from dataclasses import dataclass


@dataclass
class MutationState:
    gamma_p: list[list[list[float]]]
    alpha: list[list[float]]
    feedback_mirror_E: float = 0.0
    feedback_mirror_J: float = 0.0
    callback_bias_F: float = 0.0
    rejected_source_reachable: bool = False


@dataclass(frozen=True)
class MutationObservation:
    family_id: str
    eta: float
    physical_delta: float
    structural_verdict: str
    field_binding: str
    state: MutationState


def zero_state() -> MutationState:
    return MutationState(
        gamma_p=[[[0.0, 0.0] for _ in range(3)] for _ in range(32)],
        alpha=[[0.0 for _ in range(3)] for _ in range(32)],
    )


def apply_development_mutation(source: MutationState, family_id: str, eta: float) -> MutationObservation:
    if eta <= 0.0 or not math.isfinite(eta):
        raise ValueError("eta must be positive and finite")
    target = copy.deepcopy(source)
    if family_id == "F01":
        delta = eta * 0.1
        target.gamma_p[0][0][0] += delta
        verdict = "FAIL_PERSISTENT_STATE_RESTORATION"
        binding = "trial_cache.gamma_p[cell=0,qp=0,component=0]"
    elif family_id == "F02":
        delta = eta * 0.1
        target.alpha[0][1] += delta
        verdict = "FAIL_DECLARED_PERSISTENT_FIELD_RESTORATION"
        binding = "declared_snapshot.alpha[cell=0,qp=1]"
    elif family_id == "F05":
        delta = eta
        target.feedback_mirror_E += delta
        target.rejected_source_reachable = True
        verdict = "FAIL_REJECTED_SOURCE_REACHABILITY"
        binding = "feedback_mirror_E@first_lambda_0.10_replay"
    elif family_id == "F07":
        delta = eta
        target.callback_bias_F += delta
        verdict = "FAIL_PROCESS_GLOBAL_STATE_RESTORATION"
        binding = "callback_bias_F@extra_nonaccepting_residual"
    else:
        raise ValueError(f"unsupported P5 family {family_id}")
    return MutationObservation(family_id, eta, delta, verdict, binding, target)


def apply_confirmation_binding(source: MutationState, family_id: str, eta: float) -> MutationObservation:
    if eta <= 0.0 or not math.isfinite(eta):
        raise ValueError("eta must be positive and finite")
    target = copy.deepcopy(source)
    if family_id == "F01":
        delta = eta * 0.1
        target.gamma_p[31][2][1] += delta
        return MutationObservation(family_id, eta, delta, "FAIL_PERSISTENT_STATE_RESTORATION", "trial_cache.gamma_p[cell=31,qp=2,component=1]", target)
    if family_id == "F05":
        delta = eta
        target.feedback_mirror_J += delta
        target.rejected_source_reachable = True
        return MutationObservation(family_id, eta, delta, "FAIL_REJECTED_SOURCE_REACHABILITY", "feedback_mirror_J@secondary_callback", target)
    raise ValueError("only F01 and F05 have frozen P6 confirmation bindings")
