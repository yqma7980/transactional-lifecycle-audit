"""Independent exact serial health-reference oracle for L2-D6.0."""

from fractions import Fraction


def derive_thread_support_oracle():
    return {
        "design_version": "L2-D6.0",
        "case_id": "L2-TH-01",
        "serial_reference": {
            "force": "11/10",
            "displacement": "21/1000",
            "reaction": "11/10",
            "stress": "11/10",
            "epsilon_p": "1/100",
            "kappa": "1/100",
        },
        "parallel_parity_oracle": None,
        "expected_gate_classification": "PASS_SCHEDULING_ENVELOPE_OR_NOT_SUPPORTED",
        "expected_observed_outcome": "NOT_SUPPORTED_NO_PARALLEL_EXECUTION_PATH",
        "claim_boundary": "No parallel path means no thread-safety or performance result.",
    }


__all__ = ["derive_thread_support_oracle"]
