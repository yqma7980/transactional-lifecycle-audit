from __future__ import annotations

import numpy as np

from p4d_material import evaluate_material


def execute_constitutive_oracle(fraction_packets: dict[str, object]) -> dict[str, object]:
    elastic = evaluate_material(np.array([1.0 / 20.0, 0.0]), np.zeros(2), 0.0)
    plastic = evaluate_material(np.array([1.0 / 5.0, 0.0]), np.zeros(2), 0.0)
    expected_elastic_tau = np.array([float(value) for value in fraction_packets["elastic"]["tau"]])
    expected_plastic_tau = np.array([float(value) for value in fraction_packets["plastic"]["tau"]])
    expected_plastic_tangent = np.array(
        [[float(value) for value in row] for row in fraction_packets["plastic"]["tangent"]],
        dtype=np.float64,
    )
    checks = {
        "elastic_tau": bool(np.allclose(elastic.tau, expected_elastic_tau, rtol=1.0e-14, atol=1.0e-14)),
        "elastic_tangent": bool(np.allclose(elastic.tangent, 10.0 * np.eye(2), rtol=1.0e-14, atol=1.0e-14)),
        "plastic_tau": bool(np.allclose(plastic.tau, expected_plastic_tau, rtol=1.0e-14, atol=1.0e-14)),
        "plastic_tangent": bool(np.allclose(plastic.tangent, expected_plastic_tangent, rtol=1.0e-14, atol=1.0e-14)),
        "plastic_delta_lambda": bool(np.isclose(plastic.delta_lambda, 1.0 / 12.0, rtol=1.0e-14, atol=1.0e-14)),
        "plastic_candidate": bool(
            np.allclose(plastic.candidate.gamma_p, [1.0 / 12.0, 0.0], rtol=1.0e-14, atol=1.0e-14)
            and np.isclose(plastic.candidate.alpha, 1.0 / 12.0, rtol=1.0e-14, atol=1.0e-14)
        ),
    }
    pass_flag = all(checks.values())
    return {
        "checks": checks,
        "elastic": {
            "tau": elastic.tau.tolist(),
            "tangent": elastic.tangent.tolist(),
            "branch": elastic.branch,
        },
        "plastic": {
            "tau": plastic.tau.tolist(),
            "tangent": plastic.tangent.tolist(),
            "gamma_p": plastic.candidate.gamma_p.tolist(),
            "alpha": plastic.candidate.alpha,
            "delta_lambda": plastic.delta_lambda,
            "branch": plastic.branch,
        },
        "primary_verdict": "CONSTITUTIVE_ORACLE_PASS" if pass_flag else "CONSTITUTIVE_ORACLE_FAIL",
        "pass_flag": pass_flag,
    }
