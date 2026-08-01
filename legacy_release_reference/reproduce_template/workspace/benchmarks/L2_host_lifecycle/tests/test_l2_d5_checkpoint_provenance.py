"""Directed tests for the L2-D5.0a checkpoint-provenance benchmark."""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
from pathlib import Path
import json
import math
import unittest

from oracle.l2_d5_fraction_oracle import derive_checkpoint_provenance_oracle
from src.l2_d5_checkpoint_provenance import (
    AUTHORIZED_CASES,
    CHECKPOINT_SCHEMA,
    EXPECTED_CLASSIFICATION,
    build_checkpoint_payload,
    deserialize_checkpoint,
    execute_checkpoint_provenance_case,
    load_frozen_design,
    serialize_checkpoint,
)
from src.l2_host import NewtonHost
from src.l2_state import ElementData, MaterialData
from src.l2_variants import SafeTransactional


BENCHMARK_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_CONFIGURATION_HASH = (
    "c4e3373b1ec484567f7c0cdd75727e636282847c6ebc8577f278720069efb0ca"
)
EXPECTED_CHECKPOINT_COMMITTED_HASH = (
    "9208bebb27104d3b2f2ea9c53cb519159c7ec0fee98c7978091fba4c6fe3a6b9"
)
EXPECTED_CHECKPOINT_PHYSICAL_HASH = (
    "0b3351602c8ca334f0155fdedc7800032e41f4781a1ea969a8b0159c9675eef4"
)
EXPECTED_FINAL_COMMITTED_HASH = (
    "58223c0076a614bb7e37b82d4e4dec99376185839ed649534e33258d6bc3fb59"
)
EXPECTED_FINAL_PHYSICAL_HASH = (
    "466a2ab596c3b04c37583fe1a571afb22a7b4335b1d188b18c410238f17d7835"
)


class L2D5CheckpointProvenanceTests(unittest.TestCase):
    def test_freeze_and_case_matrix_identity(self) -> None:
        freeze, matrix = load_frozen_design(BENCHMARK_ROOT)
        self.assertEqual(freeze["design_version"], "L2-D5.0a")
        self.assertEqual(tuple(row["case_id"] for row in matrix), AUTHORIZED_CASES)
        self.assertEqual(len(set(row["case_id"] for row in matrix)), 1)
        self.assertEqual(freeze["runtime_configuration_hash"], EXPECTED_CONFIGURATION_HASH)

    def test_fraction_oracle_is_exact_and_independent(self) -> None:
        oracle = derive_checkpoint_provenance_oracle()
        self.assertEqual(oracle["checkpoint"]["displacement"], "21/1000")
        self.assertEqual(oracle["checkpoint"]["epsilon_p"], "1/100")
        self.assertEqual(oracle["continuation"]["displacement"], "4/125")
        self.assertEqual(oracle["continuation"]["epsilon_p"], "1/50")
        self.assertTrue(all(value == "0/1" for value in oracle["expected_deltas"].values()))

    def _source_payload(self):
        freeze, _ = load_frozen_design(BENCHMARK_ROOT)
        material = MaterialData()
        element = ElementData()
        variant = SafeTransactional(material)
        host = NewtonHost(
            run_id="unit",
            case_id="L2-CP-01",
            history_id="unit_source",
            variant=variant,
            configuration_hash=freeze["runtime_configuration_hash"],
        )
        checkpoint = host.solve_increment(target_force=1.1, attempt_id="SOURCE")
        payload = build_checkpoint_payload(
            checkpoint,
            configuration_hash=freeze["runtime_configuration_hash"],
            material=material,
            element=element,
        )
        return freeze, material, element, payload

    def test_checkpoint_bytes_are_deterministic_and_round_trip_exact(self) -> None:
        freeze, material, element, payload = self._source_payload()
        first = serialize_checkpoint(payload)
        second = serialize_checkpoint(payload)
        self.assertEqual(first, second)
        restored_payload, committed, checkpoint = deserialize_checkpoint(
            first,
            expected_configuration_hash=freeze["runtime_configuration_hash"],
            material=material,
            element=element,
        )
        self.assertEqual(restored_payload, payload)
        self.assertEqual(restored_payload.schema_version, CHECKPOINT_SCHEMA)
        self.assertEqual(committed.fingerprint, EXPECTED_CHECKPOINT_COMMITTED_HASH)
        self.assertEqual(checkpoint.physical_hash, EXPECTED_CHECKPOINT_PHYSICAL_HASH)

    def test_checkpoint_corruption_is_rejected(self) -> None:
        freeze, material, element, payload = self._source_payload()
        envelope = json.loads(serialize_checkpoint(payload).decode("ascii"))
        envelope["payload"]["accepted_version"] = 99
        corrupted = json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode("ascii")
        with self.assertRaises(ValueError):
            deserialize_checkpoint(
                corrupted,
                expected_configuration_hash=freeze["runtime_configuration_hash"],
                material=material,
                element=element,
            )

    def test_configuration_mismatch_is_rejected(self) -> None:
        freeze, material, element, payload = self._source_payload()
        with self.assertRaises(ValueError):
            deserialize_checkpoint(
                serialize_checkpoint(payload),
                expected_configuration_hash="0" * 64,
                material=material,
                element=element,
            )

    def test_cp01_passes_all_round_trip_gates(self) -> None:
        result = execute_checkpoint_provenance_case(
            BENCHMARK_ROOT, "L2-CP-01", "unit"
        )
        self.assertTrue(result.pass_flag)
        self.assertEqual(result.observed_classification, EXPECTED_CLASSIFICATION)
        self.assertEqual(len(result.events), 7)
        self.assertTrue(all(not event.candidate_reachable for event in result.events))
        self.assertTrue(all(event.all_values_finite for event in result.events))
        self.assertEqual(result.reference_source.committed_state_fingerprint, EXPECTED_CHECKPOINT_COMMITTED_HASH)
        self.assertEqual(result.reference_source.physical_checkpoint_fingerprint, EXPECTED_CHECKPOINT_PHYSICAL_HASH)
        self.assertEqual(result.reference_final.committed_state_fingerprint, EXPECTED_FINAL_COMMITTED_HASH)
        self.assertEqual(result.reference_final.physical_checkpoint_fingerprint, EXPECTED_FINAL_PHYSICAL_HASH)
        self.assertEqual(result.reference_final, result.restored_final)

    def test_runtime_fields_match_fraction_oracle_within_frozen_tolerance(self) -> None:
        result = execute_checkpoint_provenance_case(
            BENCHMARK_ROOT, "L2-CP-01", "unit"
        )
        expected = {
            "force": Fraction(6, 5),
            "displacement": Fraction(4, 125),
            "reaction": Fraction(6, 5),
            "stress": Fraction(6, 5),
            "epsilon_p": Fraction(1, 50),
            "kappa": Fraction(1, 50),
        }
        for key, value in expected.items():
            self.assertTrue(
                math.isclose(
                    getattr(result.restored_final, key),
                    float(value),
                    abs_tol=1.0e-12,
                    rel_tol=1.0e-12,
                )
            )

    def test_hash_gate_cannot_be_replaced_by_field_tolerance(self) -> None:
        result = execute_checkpoint_provenance_case(
            BENCHMARK_ROOT, "L2-CP-01", "unit"
        )
        broken = replace(
            result.comparison,
            final_committed_fingerprint_exact=False,
        )
        from src.l2_d5_checkpoint_provenance import classify_checkpoint_case

        classification, passed = classify_checkpoint_case(broken)
        self.assertFalse(passed)
        self.assertEqual(classification, "FAIL_CHECKPOINT_ROUND_TRIP")

    def test_unauthorized_case_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            execute_checkpoint_provenance_case(
                BENCHMARK_ROOT, "L2-TH-01", "unit"
            )

    def test_import_contract_does_not_require_result_root(self) -> None:
        self.assertFalse(
            (BENCHMARK_ROOT / "results" / "L2_D5_checkpoint_provenance").exists()
        )


if __name__ == "__main__":
    unittest.main()
