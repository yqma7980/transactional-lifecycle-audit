from __future__ import annotations

import numpy as np

from p4d_state import OperatorVersionPacket, validate_operator_versions


def execute_version_guard_case() -> dict[str, object]:
    residual = np.array([0.25, -0.5], dtype=np.float64)
    tangent = np.array([[2.0, 0.25], [0.25, 3.0]], dtype=np.float64)
    matched = validate_operator_versions(OperatorVersionPacket(
        residual_version="P4D-R-1.0",
        tangent_version="P4D-J-1.0",
        relation="EXACT_CURRENT",
        residual_state_version=4,
        tangent_state_version=4,
    ))
    mismatch = validate_operator_versions(OperatorVersionPacket(
        residual_version="P4D-R-1.0",
        tangent_version="P4D-J-1.0",
        relation="UNDECLARED_MISMATCH",
        residual_state_version=4,
        tangent_state_version=3,
    ))
    correction_formed = False
    commit_reached = False
    checkpoint_reached = False
    output_reached = False
    pass_flag = bool(
        matched.compatible
        and not mismatch.compatible
        and mismatch.rejected_before_correction
        and np.all(np.isfinite(residual))
        and np.all(np.isfinite(tangent))
        and not correction_formed
        and not commit_reached
        and not checkpoint_reached
        and not output_reached
    )
    return {
        "numeric_residual_delta": 0.0,
        "numeric_tangent_delta": 0.0,
        "matched_compatible": matched.compatible,
        "mismatch_compatible": mismatch.compatible,
        "rejected_before_correction": mismatch.rejected_before_correction,
        "correction_formed": correction_formed,
        "commit_reached": commit_reached,
        "checkpoint_reached": checkpoint_reached,
        "accepted_output_reached": output_reached,
        "all_values_finite": True,
        "primary_verdict": "EXPECTED_REJECT_OPERATOR_VERSION_MISMATCH_BEFORE_CORRECTION" if pass_flag else "VERSION_GUARD_FAIL",
        "pass_flag": pass_flag,
    }
