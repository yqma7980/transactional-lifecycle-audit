from __future__ import annotations

import pathlib
import sys
from typing import Any

import numpy as np

from p4d_material import evaluate_material, stress_only
from p4d_reference_smoke import run_manufactured_reference_smoke


def _fraction_vector(value) -> np.ndarray:
    return np.asarray([float(item) for item in value], dtype=np.float64)


def _fraction_matrix(value) -> np.ndarray:
    return np.asarray([[float(item) for item in row] for row in value], dtype=np.float64)


def _packet_errors(host, expected) -> dict[str, float]:
    return {
        "tau": float(np.max(np.abs(host.tau - _fraction_vector(expected["tau"])))),
        "gamma_p": float(np.max(np.abs(host.candidate.gamma_p - _fraction_vector(expected["gamma_p"])))),
        "alpha": abs(host.candidate.alpha - float(expected["alpha"])),
        "tangent": float(np.max(np.abs(host.tangent - _fraction_matrix(expected["tangent"])))),
    }


def _directional_check(gamma: np.ndarray) -> list[dict[str, Any]]:
    packet = evaluate_material(gamma, np.zeros(2), 0.0)
    checks = []
    epsilon = 1.0e-7
    directions = (
        np.array([1.0, 0.0]),
        np.array([0.0, 1.0]),
        np.array([3.0, 4.0]) / 5.0,
    )
    for ordinal, direction in enumerate(directions, 1):
        plus = stress_only(gamma + epsilon * direction, np.zeros(2), 0.0)
        minus = stress_only(gamma - epsilon * direction, np.zeros(2), 0.0)
        finite_difference = (plus - minus) / (2.0 * epsilon)
        predicted = packet.tangent @ direction
        relative = float(np.linalg.norm(finite_difference - predicted) / max(np.linalg.norm(predicted), np.finfo(float).tiny))
        checks.append(
            {
                "ordinal": ordinal,
                "direction_hex": [float(x).hex() for x in direction],
                "finite_difference_hex": [float(x).hex() for x in finite_difference],
                "predicted_hex": [float(x).hex() for x in predicted],
                "relative_error_hex": relative.hex(),
            }
        )
    return checks


def run_oracle_stage(root: pathlib.Path) -> dict[str, Any]:
    oracle_path = root / "oracle"
    if str(oracle_path) not in sys.path:
        sys.path.insert(0, str(oracle_path))
    from p4d_fraction_oracle import derive_fraction_packets, fraction_text

    fractions = derive_fraction_packets()
    elastic = evaluate_material(np.array([0.05, 0.0]), np.zeros(2), 0.0)
    plastic = evaluate_material(np.array([0.2, 0.0]), np.zeros(2), 0.0)
    elastic_errors = _packet_errors(elastic, fractions["elastic"])
    plastic_errors = _packet_errors(plastic, fractions["plastic"])
    directional = {
        "elastic": _directional_check(np.array([0.05, 0.0])),
        "plastic": _directional_check(np.array([0.2, 0.0])),
    }
    maximum_packet_error = max(list(elastic_errors.values()) + list(plastic_errors.values()))
    maximum_directional_error = max(
        float.fromhex(item["relative_error_hex"])
        for branch in directional.values()
        for item in branch
    )
    manufactured = run_manufactured_reference_smoke()
    gate_pass = bool(
        maximum_packet_error <= 1.0e-14
        and maximum_directional_error <= 1.0e-7
        and manufactured["mesh_level"] == 4
        and manufactured["all_values_finite"]
        and not manufactured["formal_convergence_sequence_run"]
    )
    return {
        "schema_version": "CMAME-P4D1-ORACLE-RESULT-1.0",
        "preflight_id": "P4D1-ORACLE-01",
        "fraction_packets": fraction_text(fractions),
        "elastic_packet_errors_hex": {key: value.hex() for key, value in elastic_errors.items()},
        "plastic_packet_errors_hex": {key: value.hex() for key, value in plastic_errors.items()},
        "maximum_packet_error_hex": maximum_packet_error.hex(),
        "directional_checks": directional,
        "maximum_directional_relative_error_hex": maximum_directional_error.hex(),
        "manufactured_reference": manufactured,
        "host_update_imported_by_fraction_oracle": False,
        "oracle_gate_pass": gate_pass,
    }
