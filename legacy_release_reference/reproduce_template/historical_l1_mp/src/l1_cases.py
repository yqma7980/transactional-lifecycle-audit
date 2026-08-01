"""Execution of the 12 frozen L1-MP cases and 25 variant outcomes."""

from __future__ import annotations

from collections import defaultdict
import csv
from fractions import Fraction
import json
import math
from pathlib import Path
from typing import Any

from .l1_ledger import Ledger, bool_text, decimal_text, float_hex
from .l1_material import incremental_plastic_dissipation
from .l1_state import (
    CommittedState,
    MaterialData,
    MaterialResult,
    canonical_hash,
    canonical_json,
    checkpoint_payload,
    checkpoint_restore,
)
from .l1_variants import VARIANTS, SafeTransactional


DESIGN_VERSION = "L1-D1.0"
RUN_ID = "L1-MP-D1.0-REPLAY"


def _fraction(value: str) -> float:
    return float(Fraction(value))


def _finite(*values: float) -> bool:
    return all(math.isfinite(value) for value in values)


def _bool_or_na(value: bool | None) -> str:
    return "NA" if value is None else bool_text(value)


class MPBenchmark:
    def __init__(self, root: Path, implementation_hash: str) -> None:
        self.root = root
        self.implementation_hash = implementation_hash
        self.material = MaterialData()
        self.material_hash = self.material.fingerprint
        self.freeze = json.loads((root / "L1_MP_execution_freeze.json").read_text(encoding="utf-8"))
        self.configuration_hash = canonical_hash(
            {
                "design_version": DESIGN_VERSION,
                "freeze": self.freeze,
                "case_matrix_sha256": canonical_hash(
                    (root / "L1_case_matrix.csv").read_text(encoding="utf-8")
                ),
            }
        )
        with (root / "schemas" / "l1_call_ledger_columns.csv").open(
            "r", encoding="utf-8", newline=""
        ) as handle:
            columns = [row["name"] for row in csv.DictReader(handle)]
        self.ledger = Ledger(columns)
        self.case_results: list[dict[str, str]] = []
        self.checkpoints: list[dict[str, str]] = []
        self._call_counters: dict[tuple[str, str, str], int] = defaultdict(int)
        expected = json.loads((root / "expected_results_template.json").read_text(encoding="utf-8"))
        self.tolerances = expected["tolerances"]

    def _variant(self, name: str, committed: CommittedState | None = None):
        return VARIANTS[name](self.material, committed)

    def _next_call(self, case_id: str, variant: str, history_id: str) -> int:
        key = (case_id, variant, history_id)
        value = self._call_counters[key]
        self._call_counters[key] += 1
        return value

    def _declared_packet_hash(
        self,
        *,
        case_id: str,
        variant: Any,
        event: str,
        attempt_id: str,
        candidate_id: str,
        committed: CommittedState,
        epsilon: float | None,
    ) -> str:
        return canonical_hash(
            {
                "design_version": DESIGN_VERSION,
                "case_id": case_id,
                "sublevel": "L1-MP",
                "variant": variant.name,
                "event": event,
                "attempt_id": attempt_id,
                "candidate_id": candidate_id,
                "operator_version": variant.operator_version,
                "material_parameters_hash": self.material_hash,
                "configuration_hash": self.configuration_hash,
                "accepted_version": committed.accepted_version,
                "epsilon": epsilon,
                "epsilon_p_committed": committed.epsilon_p,
                "kappa_committed": committed.kappa,
                "requested_outputs": ["sigma", "E_alg", "candidate"],
            }
        )

    def _record(
        self,
        *,
        case_id: str,
        variant: Any,
        history_id: str,
        event: str,
        attempt_id: str,
        candidate_id: str,
        before: CommittedState,
        after: CommittedState,
        persistent_before: str,
        persistent_after: str,
        epsilon: float | None = None,
        result: MaterialResult | None = None,
        output_source_version: str = "NA",
        candidate_reachable_after: bool = False,
        event_valid: bool = True,
        note: str = "ok",
        declared_packet_hash: str | None = None,
        candidate_state_hash: str | None = None,
    ) -> dict[str, Any]:
        call_index = self._next_call(case_id, variant.name, history_id)
        packet_hash = declared_packet_hash or self._declared_packet_hash(
            case_id=case_id,
            variant=variant,
            event=event,
            attempt_id=attempt_id,
            candidate_id=candidate_id,
            committed=before,
            epsilon=epsilon,
        )
        candidate = result.candidate if result is not None else None
        numeric_values = [] if result is None else [result.sigma, result.E_alg, result.delta_gamma]
        finite = _finite(*numeric_values)
        return self.ledger.append(
            design_version=DESIGN_VERSION,
            run_id=RUN_ID,
            implementation_hash=self.implementation_hash,
            case_id=case_id,
            sublevel="L1-MP",
            variant=variant.name,
            history_id=history_id,
            call_index=call_index,
            event=event,
            attempt_id=attempt_id,
            candidate_id=candidate_id,
            operator_version=variant.operator_version,
            declared_packet_hash=packet_hash,
            material_parameters_hash=self.material_hash,
            configuration_hash=self.configuration_hash,
            accepted_version_before=before.accepted_version,
            accepted_version_after=after.accepted_version,
            committed_state_hash_before=before.fingerprint,
            committed_state_hash_after=after.fingerprint,
            candidate_state_hash=(
                candidate_state_hash
                if candidate_state_hash is not None
                else (candidate.fingerprint if candidate is not None else "NA")
            ),
            persistent_state_hash_before=persistent_before,
            persistent_state_hash_after=persistent_after,
            epsilon_hex=float_hex(epsilon),
            u_hex="NA",
            force_hex="NA",
            epsilon_p_committed_hex=before.epsilon_p.hex(),
            kappa_committed_hex=before.kappa.hex(),
            sigma_hex=float_hex(None if result is None else result.sigma),
            E_alg_hex=float_hex(None if result is None else result.E_alg),
            residual_hex="NA",
            tangent_hex="NA",
            epsilon_p_candidate_hex=float_hex(None if candidate is None else candidate.epsilon_p),
            kappa_candidate_hex=float_hex(None if candidate is None else candidate.kappa),
            residual_state_version=("NA" if result is None else result.residual_state_version),
            tangent_state_version=("NA" if result is None else result.tangent_state_version),
            output_source_version=output_source_version,
            candidate_reachable_after=bool_text(candidate_reachable_after),
            finite=bool_text(finite),
            event_valid=bool_text(event_valid),
            note=note,
        )

    def _begin_attempt(self, case_id: str, variant: Any, history_id: str, attempt_id: str) -> None:
        before = variant.committed
        persistent = variant.persistent_hash
        if hasattr(variant, "begin_attempt"):
            variant.begin_attempt(attempt_id)
        self._record(
            case_id=case_id,
            variant=variant,
            history_id=history_id,
            event="BeginAttempt",
            attempt_id=attempt_id,
            candidate_id="NA",
            before=before,
            after=variant.committed,
            persistent_before=persistent,
            persistent_after=variant.persistent_hash,
            note="attempt_declared",
        )

    def _evaluate(
        self,
        case_id: str,
        variant: Any,
        history_id: str,
        epsilon: float,
        attempt_id: str,
        candidate_id: str,
    ) -> tuple[MaterialResult, dict[str, Any]]:
        before = variant.committed
        persistent_before = variant.persistent_hash
        source_call_index = self._call_counters[(case_id, variant.name, history_id)]
        packet_hash = self._declared_packet_hash(
            case_id=case_id,
            variant=variant,
            event="EvaluateMaterial",
            attempt_id=attempt_id,
            candidate_id=candidate_id,
            committed=before,
            epsilon=epsilon,
        )
        result = variant.evaluate(
            epsilon,
            candidate_id=candidate_id,
            attempt_id=attempt_id,
            source_call_index=source_call_index,
        )
        unsafe = variant.name in {"unsafe_trial_cache", "unsafe_output_feedback"}
        row = self._record(
            case_id=case_id,
            variant=variant,
            history_id=history_id,
            event="EvaluateMaterial",
            attempt_id=attempt_id,
            candidate_id=candidate_id,
            before=before,
            after=variant.committed,
            persistent_before=persistent_before,
            persistent_after=variant.persistent_hash,
            epsilon=epsilon,
            result=result,
            candidate_reachable_after=variant.candidate_reachable(candidate_id),
            event_valid=not unsafe,
            note=("seeded_hidden_state_access" if unsafe else "candidate_only"),
            declared_packet_hash=packet_hash,
        )
        return result, row

    def _reject_attempt(
        self,
        case_id: str,
        variant: Any,
        history_id: str,
        attempt_id: str,
    ) -> tuple[str, ...]:
        before = variant.committed
        persistent_before = variant.persistent_hash
        invalidated = variant.reject_attempt(attempt_id)
        unsafe = variant.name == "unsafe_trial_cache"
        self._record(
            case_id=case_id,
            variant=variant,
            history_id=history_id,
            event="RejectAttempt",
            attempt_id=attempt_id,
            candidate_id="NA",
            before=before,
            after=variant.committed,
            persistent_before=persistent_before,
            persistent_after=variant.persistent_hash,
            candidate_reachable_after=False,
            event_valid=not unsafe,
            note=("seeded_cache_not_rolled_back" if unsafe else "candidates_invalidated"),
        )
        return invalidated

    def _accept(
        self,
        case_id: str,
        variant: Any,
        history_id: str,
        result: MaterialResult,
        epsilon: float,
        plastic_dissipation: float,
    ) -> tuple[bool, str]:
        before = variant.committed
        persistent_before = variant.persistent_hash
        accepted, reason = variant.accept(result.candidate)
        after = variant.committed
        self._record(
            case_id=case_id,
            variant=variant,
            history_id=history_id,
            event="AcceptCandidate",
            attempt_id=result.candidate.attempt_id,
            candidate_id=result.candidate.candidate_id,
            before=before,
            after=after,
            persistent_before=persistent_before,
            persistent_after=variant.persistent_hash,
            epsilon=epsilon,
            result=result,
            candidate_reachable_after=variant.candidate_reachable(result.candidate.candidate_id),
            event_valid=True,
            note=reason,
        )
        if accepted:
            self.checkpoints.append(
                {
                    "run_id": RUN_ID,
                    "case_id": case_id,
                    "accepted_version": str(after.accepted_version),
                    "candidate_id": result.candidate.candidate_id,
                    "epsilon_or_u": decimal_text(epsilon),
                    "force": "NA",
                    "sigma": decimal_text(result.sigma),
                    "epsilon_p": decimal_text(after.epsilon_p),
                    "kappa": decimal_text(after.kappa),
                    "plastic_dissipation": decimal_text(plastic_dissipation),
                    "committed_state_hash": after.fingerprint,
                    "source_call_index": str(result.candidate.source_call_index),
                }
            )
        return accepted, reason

    def _terminal_read(
        self,
        case_id: str,
        variant: Any,
        history_id: str,
        trigger_epsilon: float,
    ) -> tuple[Any, bool]:
        before = variant.committed
        persistent_before = variant.persistent_hash
        snapshot = variant.terminal_read(trigger_epsilon)
        source_valid = (
            snapshot.source_version == f"accepted:{before.accepted_version}"
            and snapshot.source_candidate_id == "NA"
        )
        event_valid = (
            source_valid
            and before == variant.committed
            and persistent_before == variant.persistent_hash
        )
        self._record(
            case_id=case_id,
            variant=variant,
            history_id=history_id,
            event="TerminalRead",
            attempt_id="NA",
            candidate_id=snapshot.source_candidate_id,
            before=before,
            after=variant.committed,
            persistent_before=persistent_before,
            persistent_after=variant.persistent_hash,
            epsilon=trigger_epsilon,
            output_source_version=snapshot.source_version,
            candidate_reachable_after=False,
            event_valid=event_valid,
            note=("accepted_read_only" if event_valid else "seeded_output_feedback"),
            candidate_state_hash=snapshot.fingerprint,
        )
        return snapshot, source_valid

    def _checkpoint_write(
        self,
        case_id: str,
        variant: Any,
        history_id: str,
    ) -> dict[str, Any]:
        before = variant.committed
        payload = checkpoint_payload(before, self.configuration_hash)
        self._record(
            case_id=case_id,
            variant=variant,
            history_id=history_id,
            event="CheckpointWrite",
            attempt_id="NA",
            candidate_id="NA",
            before=before,
            after=variant.committed,
            persistent_before=variant.persistent_hash,
            persistent_after=variant.persistent_hash,
            candidate_state_hash=canonical_hash(payload),
            note="complete_committed_payload",
        )
        return payload

    def _checkpoint_read(
        self,
        case_id: str,
        variant: Any,
        history_id: str,
        payload: dict[str, Any],
    ) -> CommittedState:
        before = variant.committed
        restored = checkpoint_restore(payload, self.configuration_hash)
        self._record(
            case_id=case_id,
            variant=variant,
            history_id=history_id,
            event="CheckpointRead",
            attempt_id="NA",
            candidate_id="NA",
            before=before,
            after=before,
            persistent_before=variant.persistent_hash,
            persistent_after=variant.persistent_hash,
            candidate_state_hash=canonical_hash(payload),
            event_valid=(restored.fingerprint == payload["committed_state_hash"]),
            note="checkpoint_verified",
        )
        return restored

    def _result_row(
        self,
        *,
        case: dict[str, str],
        variant: str,
        expected: str,
        observed: str,
        declared_equal: bool,
        delta_stress: float | None,
        delta_residual: float | None,
        delta_tangent: float | None,
        committed_equal: bool,
        operator_equal: bool,
        accepted_source_valid: bool | None,
        checkpoint_equal: bool | None,
        finite: bool,
        passed: bool,
        gate_failed: str = "NA",
    ) -> dict[str, str]:
        return {
            "design_version": DESIGN_VERSION,
            "implementation_hash": self.implementation_hash,
            "case_id": case["case_id"],
            "sublevel": "L1-MP",
            "variant": variant,
            "history_1": case["history_1"],
            "history_2": case["history_2"],
            "declared_packet_equal": bool_text(declared_equal),
            "expected_classification": expected,
            "observed_classification": observed,
            "delta_stress": decimal_text(delta_stress),
            "delta_residual": decimal_text(delta_residual),
            "delta_tangent": decimal_text(delta_tangent),
            "committed_hash_equal": bool_text(committed_equal),
            "operator_hash_equal": bool_text(operator_equal),
            "accepted_source_valid": _bool_or_na(accepted_source_valid),
            "checkpoint_equal": _bool_or_na(checkpoint_equal),
            "finite": bool_text(finite),
            "gate_failed": gate_failed,
            "passed": bool_text(passed),
        }

    def _reference_case(self, case: dict[str, str], variant_name: str) -> dict[str, str]:
        case_id = case["case_id"]
        if case_id == "MP-REF-01":
            epsilon = 0.005
            expected_sigma, expected_tangent = 0.5, 100.0
            expected_ep, expected_kappa = 0.0, 0.0
        else:
            epsilon = 0.03
            expected_sigma, expected_tangent = _fraction("13/11"), _fraction("100/11")
            expected_ep = expected_kappa = _fraction("1/55")
        variant = self._variant(variant_name)
        initial_hash = variant.committed.fingerprint
        self._begin_attempt(case_id, variant, "REFERENCE", "reference")
        result, _ = self._evaluate(
            case_id, variant, "REFERENCE", epsilon, "reference", "reference_candidate"
        )
        self._reject_attempt(case_id, variant, "REFERENCE", "reference")
        errors = [
            abs(result.sigma - expected_sigma),
            abs(result.E_alg - expected_tangent),
            abs(result.candidate.epsilon_p - expected_ep),
            abs(result.candidate.kappa - expected_kappa),
        ]
        tolerance = self.tolerances["analytical_absolute"]
        passed = max(errors) <= tolerance and initial_hash == variant.committed.fingerprint
        return self._result_row(
            case=case,
            variant=variant_name,
            expected="PASS_ANALYTICAL_REFERENCE",
            observed=("PASS_ANALYTICAL_REFERENCE" if passed else "FAIL_ANALYTICAL_REFERENCE"),
            declared_equal=True,
            delta_stress=result.sigma - expected_sigma,
            delta_residual=None,
            delta_tangent=result.E_alg - expected_tangent,
            committed_equal=(initial_hash == variant.committed.fingerprint),
            operator_equal=True,
            accepted_source_valid=None,
            checkpoint_equal=None,
            finite=_finite(result.sigma, result.E_alg),
            passed=passed,
            gate_failed=("NA" if passed else "analytical_reference"),
        )

    def _accepted_path_case(self, case: dict[str, str], variant_name: str) -> dict[str, str]:
        case_id = case["case_id"]
        variant = self._variant(variant_name)
        strains = [_fraction(value) for value in self.freeze["accepted_load_unload_reload_path"]]
        expected = self.freeze["accepted_path_oracle"]
        max_state_error = 0.0
        max_tangent_error = 0.0
        dissipation_ok = True
        accepted_ok = True
        for index, (epsilon, oracle) in enumerate(zip(strains, expected, strict=True), start=1):
            attempt_id = f"path_attempt_{index}"
            candidate_id = f"path_candidate_{index}"
            self._begin_attempt(case_id, variant, "REFERENCE", attempt_id)
            before = variant.committed
            result, _ = self._evaluate(
                case_id,
                variant,
                "REFERENCE",
                epsilon,
                attempt_id,
                candidate_id,
            )
            dissipation = incremental_plastic_dissipation(before, result.candidate, self.material)
            accepted, _ = self._accept(
                case_id,
                variant,
                "REFERENCE",
                result,
                epsilon,
                dissipation,
            )
            accepted_ok = accepted_ok and accepted
            state_errors = [
                abs(result.sigma - _fraction(oracle["sigma"])),
                abs(result.candidate.epsilon_p - _fraction(oracle["epsilon_p"])),
                abs(result.candidate.kappa - _fraction(oracle["kappa"])),
                abs(dissipation - _fraction(oracle["plastic_dissipation"])),
            ]
            max_state_error = max(max_state_error, *state_errors)
            max_tangent_error = max(
                max_tangent_error,
                abs(result.E_alg - _fraction(oracle["E_alg"])),
            )
            dissipation_ok = dissipation_ok and dissipation >= self.tolerances["plastic_dissipation_floor"]
        tolerance = self.tolerances["analytical_absolute"]
        passed = (
            accepted_ok
            and max_state_error <= tolerance
            and max_tangent_error <= tolerance
            and dissipation_ok
            and variant.committed.accepted_version == len(strains)
        )
        return self._result_row(
            case=case,
            variant=variant_name,
            expected="PASS_PATH_REFERENCE_AND_DISSIPATION",
            observed=(
                "PASS_PATH_REFERENCE_AND_DISSIPATION"
                if passed
                else "FAIL_PATH_REFERENCE_OR_DISSIPATION"
            ),
            declared_equal=True,
            delta_stress=max_state_error,
            delta_residual=None,
            delta_tangent=max_tangent_error,
            committed_equal=accepted_ok,
            operator_equal=True,
            accepted_source_valid=True,
            checkpoint_equal=True,
            finite=True,
            passed=passed,
            gate_failed=("NA" if passed else "thermodynamic_sanity"),
        )

    def _rejected_history(
        self,
        case_id: str,
        variant_name: str,
        history_id: str,
        strains: list[float],
        replay_epsilon: float,
    ) -> tuple[Any, MaterialResult, dict[str, Any], bool]:
        variant = self._variant(variant_name)
        initial_hash = variant.committed.fingerprint
        if strains:
            self._begin_attempt(case_id, variant, history_id, "discarded")
            candidate_ids: list[str] = []
            for index, epsilon in enumerate(strains, start=1):
                candidate_id = f"discarded_candidate_{index}"
                candidate_ids.append(candidate_id)
                self._evaluate(
                    case_id,
                    variant,
                    history_id,
                    epsilon,
                    "discarded",
                    candidate_id,
                )
            self._reject_attempt(case_id, variant, history_id, "discarded")
            unreachable = all(not variant.candidate_reachable(value) for value in candidate_ids)
        else:
            unreachable = True
        self._begin_attempt(case_id, variant, history_id, "replay")
        result, row = self._evaluate(
            case_id,
            variant,
            history_id,
            replay_epsilon,
            "replay",
            "replay_candidate",
        )
        self._reject_attempt(case_id, variant, history_id, "replay")
        committed_unchanged = initial_hash == variant.committed.fingerprint
        return variant, result, row, (unreachable and committed_unchanged)

    def _lifecycle_replay_case(
        self,
        case: dict[str, str],
        variant_name: str,
    ) -> dict[str, str]:
        case_id = case["case_id"]
        replay = _fraction(self.freeze["common_replay_epsilon"])
        if case_id == "MP-LC-01":
            history_1 = [0.03]
            history_2: list[float] = []
        elif case_id == "MP-LC-02":
            history_1 = [_fraction(value) for value in self.freeze["call_order_history_1"]]
            history_2 = [_fraction(value) for value in self.freeze["call_order_history_2"]]
        elif case_id == "MP-LC-03":
            history_1 = [0.03]
            history_2 = [0.03, 0.03]
            replay = 0.03
        elif case_id == "MP-LC-05":
            history_1 = [0.02, 0.03]
            history_2 = []
        else:
            raise ValueError(case_id)

        _, result_1, row_1, state_ok_1 = self._rejected_history(
            case_id, variant_name, "H1", history_1, replay
        )
        _, result_2, row_2, state_ok_2 = self._rejected_history(
            case_id, variant_name, "H2", history_2, replay
        )
        delta_stress = result_1.sigma - result_2.sigma
        delta_tangent = result_1.E_alg - result_2.E_alg
        declared_equal = row_1["declared_packet_hash"] == row_2["declared_packet_hash"]
        operator_equal = result_1.operator_fingerprint == result_2.operator_fingerprint
        finite = _finite(result_1.sigma, result_2.sigma, result_1.E_alg, result_2.E_alg)
        if variant_name == "unsafe_trial_cache":
            if case_id == "MP-LC-01":
                expected_delta = _fraction("-205/121")
                seed_ok = abs(delta_stress - expected_delta) <= self.tolerances["analytical_absolute"]
            else:
                seed_ok = (
                    abs(delta_stress) > self.tolerances["unsafe_minimum_drift"]
                    and abs(delta_stress) >= 1000.0e-15
                )
            passed = declared_equal and state_ok_1 and state_ok_2 and finite and seed_ok and not operator_equal
            expected = "DETECT_FINITE_SEEDED_TRIAL_DRIFT"
            observed = "DETECTED_FINITE_SEEDED_TRIAL_DRIFT" if passed else "UNSAFE_SEED_NOT_DETECTED"
        else:
            passed = (
                declared_equal
                and state_ok_1
                and state_ok_2
                and finite
                and delta_stress == 0.0
                and delta_tangent == 0.0
                and operator_equal
            )
            expected = "PASS_EXACT_REPLAY_INVARIANCE"
            observed = "PASS_EXACT_REPLAY_INVARIANCE" if passed else "SAFE_REPLAY_FALSE_POSITIVE"
        return self._result_row(
            case=case,
            variant=variant_name,
            expected=expected,
            observed=observed,
            declared_equal=declared_equal,
            delta_stress=delta_stress,
            delta_residual=delta_stress,
            delta_tangent=delta_tangent,
            committed_equal=(state_ok_1 and state_ok_2),
            operator_equal=operator_equal,
            accepted_source_valid=None,
            checkpoint_equal=None,
            finite=finite,
            passed=passed,
            gate_failed=("NA" if passed else "lifecycle"),
        )

    def _duplicate_accept_case(self, case: dict[str, str]) -> dict[str, str]:
        case_id = case["case_id"]
        variant = self._variant("safe_transactional")
        self._begin_attempt(case_id, variant, "H1", "accept_once")
        result, _ = self._evaluate(
            case_id,
            variant,
            "H1",
            0.03,
            "accept_once",
            "accepted_candidate",
        )
        dissipation = incremental_plastic_dissipation(variant.committed, result.candidate, self.material)
        first, _ = self._accept(case_id, variant, "H1", result, 0.03, dissipation)
        after_first = variant.committed
        second, reason = self._accept(case_id, variant, "H2", result, 0.03, dissipation)
        after_second = variant.committed
        passed = (
            first
            and not second
            and reason == "duplicate_accept_rejected"
            and after_first == after_second
            and after_second.accepted_version == 1
        )
        return self._result_row(
            case=case,
            variant="safe_transactional",
            expected="PASS_ACCEPT_ONCE_DUPLICATE_REJECTED",
            observed=(
                "PASS_ACCEPT_ONCE_DUPLICATE_REJECTED"
                if passed
                else "FAIL_DUPLICATE_ACCEPT_SEMANTICS"
            ),
            declared_equal=True,
            delta_stress=0.0,
            delta_residual=None,
            delta_tangent=0.0,
            committed_equal=(after_first == after_second),
            operator_equal=True,
            accepted_source_valid=True,
            checkpoint_equal=None,
            finite=True,
            passed=passed,
            gate_failed=("NA" if passed else "commit_semantics"),
        )

    def _terminal_case(self, case: dict[str, str], variant_name: str) -> dict[str, str]:
        case_id = case["case_id"]
        trigger = _fraction(self.freeze["terminal_seed_epsilon"])
        replay = _fraction(self.freeze["common_replay_epsilon"])

        variant_1 = self._variant(variant_name)
        initial_hash_1 = variant_1.committed.fingerprint
        _, source_valid_1 = self._terminal_read(case_id, variant_1, "H1", trigger)
        self._begin_attempt(case_id, variant_1, "H1", "replay")
        result_1, row_1 = self._evaluate(
            case_id, variant_1, "H1", replay, "replay", "replay_candidate"
        )
        self._reject_attempt(case_id, variant_1, "H1", "replay")

        variant_2 = self._variant(variant_name)
        initial_hash_2 = variant_2.committed.fingerprint
        self._begin_attempt(case_id, variant_2, "H2", "replay")
        result_2, row_2 = self._evaluate(
            case_id, variant_2, "H2", replay, "replay", "replay_candidate"
        )
        self._reject_attempt(case_id, variant_2, "H2", "replay")

        delta_stress = result_1.sigma - result_2.sigma
        delta_tangent = result_1.E_alg - result_2.E_alg
        declared_equal = row_1["declared_packet_hash"] == row_2["declared_packet_hash"]
        committed_equal = (
            variant_1.committed.fingerprint == initial_hash_1
            and variant_2.committed.fingerprint == initial_hash_2
        )
        operator_equal = result_1.operator_fingerprint == result_2.operator_fingerprint
        finite = _finite(result_1.sigma, result_2.sigma, result_1.E_alg, result_2.E_alg)
        if variant_name == "unsafe_output_feedback":
            passed = (
                declared_equal
                and committed_equal
                and finite
                and abs(delta_stress) > self.tolerances["unsafe_minimum_drift"]
                and not source_valid_1
                and not operator_equal
            )
            expected = "DETECT_FINITE_OUTPUT_FEEDBACK_DRIFT"
            observed = "DETECTED_FINITE_OUTPUT_FEEDBACK_DRIFT" if passed else "OUTPUT_SEED_NOT_DETECTED"
            accepted_source_valid = False
        else:
            passed = (
                declared_equal
                and committed_equal
                and finite
                and source_valid_1
                and delta_stress == 0.0
                and delta_tangent == 0.0
                and operator_equal
            )
            expected = "PASS_TERMINAL_NONINTERFERENCE"
            observed = "PASS_TERMINAL_NONINTERFERENCE" if passed else "SAFE_TERMINAL_FALSE_POSITIVE"
            accepted_source_valid = source_valid_1
        return self._result_row(
            case=case,
            variant=variant_name,
            expected=expected,
            observed=observed,
            declared_equal=declared_equal,
            delta_stress=delta_stress,
            delta_residual=delta_stress,
            delta_tangent=delta_tangent,
            committed_equal=committed_equal,
            operator_equal=operator_equal,
            accepted_source_valid=accepted_source_valid,
            checkpoint_equal=None,
            finite=finite,
            passed=passed,
            gate_failed=("NA" if passed else "terminal_output"),
        )

    def _checkpoint_case(self, case: dict[str, str], variant_name: str) -> dict[str, str]:
        case_id = case["case_id"]
        source = self._variant(variant_name)
        self._begin_attempt(case_id, source, "H1", "load")
        load_result, _ = self._evaluate(case_id, source, "H1", 0.03, "load", "load_candidate")
        dissipation = incremental_plastic_dissipation(source.committed, load_result.candidate, self.material)
        accepted, _ = self._accept(case_id, source, "H1", load_result, 0.03, dissipation)
        payload = self._checkpoint_write(case_id, source, "H1")

        restored_state = self._checkpoint_read(case_id, source, "H1", payload)
        restored = self._variant(variant_name, restored_state)
        direct = self._variant(variant_name, source.committed)

        for history, variant in (("H1", restored), ("H2", direct)):
            self._begin_attempt(case_id, variant, history, "replay")
        result_1, row_1 = self._evaluate(
            case_id, restored, "H1", 0.005, "replay", "replay_candidate"
        )
        result_2, row_2 = self._evaluate(
            case_id, direct, "H2", 0.005, "replay", "replay_candidate"
        )
        self._reject_attempt(case_id, restored, "H1", "replay")
        self._reject_attempt(case_id, direct, "H2", "replay")

        declared_equal = row_1["declared_packet_hash"] == row_2["declared_packet_hash"]
        checkpoint_equal = restored_state.fingerprint == source.committed.fingerprint
        operator_equal = result_1.operator_fingerprint == result_2.operator_fingerprint
        passed = (
            accepted
            and declared_equal
            and checkpoint_equal
            and operator_equal
            and result_1.sigma == result_2.sigma
            and result_1.E_alg == result_2.E_alg
        )
        return self._result_row(
            case=case,
            variant=variant_name,
            expected="PASS_CHECKPOINT_ROUND_TRIP",
            observed=("PASS_CHECKPOINT_ROUND_TRIP" if passed else "FAIL_CHECKPOINT_ROUND_TRIP"),
            declared_equal=declared_equal,
            delta_stress=result_1.sigma - result_2.sigma,
            delta_residual=None,
            delta_tangent=result_1.E_alg - result_2.E_alg,
            committed_equal=checkpoint_equal,
            operator_equal=operator_equal,
            accepted_source_valid=True,
            checkpoint_equal=checkpoint_equal,
            finite=_finite(result_1.sigma, result_2.sigma),
            passed=passed,
            gate_failed=("NA" if passed else "output_checkpoint"),
        )

    def _directional_case(self, case: dict[str, str], variant_name: str) -> dict[str, str]:
        case_id = case["case_id"]
        epsilon = 0.005 if case_id == "MP-OP-01" else 0.03
        h = self.tolerances["directional_step"]
        variant = self._variant(variant_name)
        initial_hash = variant.committed.fingerprint
        self._begin_attempt(case_id, variant, "REFERENCE", "directional")
        minus, _ = self._evaluate(
            case_id,
            variant,
            "REFERENCE",
            epsilon - h,
            "directional",
            "minus_candidate",
        )
        base, _ = self._evaluate(
            case_id,
            variant,
            "REFERENCE",
            epsilon,
            "directional",
            "base_candidate",
        )
        plus, _ = self._evaluate(
            case_id,
            variant,
            "REFERENCE",
            epsilon + h,
            "directional",
            "plus_candidate",
        )
        self._reject_attempt(case_id, variant, "REFERENCE", "directional")
        finite_difference = (plus.sigma - minus.sigma) / (2.0 * h)
        relative_error = abs(finite_difference - base.E_alg) / max(1.0, abs(base.E_alg))
        passed = (
            relative_error <= self.tolerances["directional_relative_error"]
            and initial_hash == variant.committed.fingerprint
            and _finite(finite_difference, base.E_alg)
        )
        return self._result_row(
            case=case,
            variant=variant_name,
            expected="PASS_DIRECTIONAL_TANGENT",
            observed=("PASS_DIRECTIONAL_TANGENT" if passed else "FAIL_DIRECTIONAL_TANGENT"),
            declared_equal=True,
            delta_stress=None,
            delta_residual=None,
            delta_tangent=relative_error,
            committed_equal=(initial_hash == variant.committed.fingerprint),
            operator_equal=(relative_error <= self.tolerances["directional_relative_error"]),
            accepted_source_valid=None,
            checkpoint_equal=None,
            finite=_finite(finite_difference, base.E_alg),
            passed=passed,
            gate_failed=("NA" if passed else "operator_accuracy"),
        )

    def run(self) -> tuple[list[dict[str, str]], list[dict[str, Any]], list[dict[str, str]]]:
        with (self.root / "L1_case_matrix.csv").open("r", encoding="utf-8", newline="") as handle:
            cases = [row for row in csv.DictReader(handle) if row["sublevel"] == "L1-MP"]
        cases.sort(key=lambda row: int(row["execution_order"]))
        for case in cases:
            for variant_name in case["variants_required"].split(";"):
                case_id = case["case_id"]
                if case_id in {"MP-REF-01", "MP-REF-02"}:
                    result = self._reference_case(case, variant_name)
                elif case_id == "MP-REF-03":
                    result = self._accepted_path_case(case, variant_name)
                elif case_id in {"MP-LC-01", "MP-LC-02", "MP-LC-03", "MP-LC-05"}:
                    result = self._lifecycle_replay_case(case, variant_name)
                elif case_id == "MP-LC-04":
                    result = self._duplicate_accept_case(case)
                elif case_id == "MP-LC-06":
                    result = self._terminal_case(case, variant_name)
                elif case_id == "MP-LC-07":
                    result = self._checkpoint_case(case, variant_name)
                elif case_id in {"MP-OP-01", "MP-OP-02"}:
                    result = self._directional_case(case, variant_name)
                else:
                    raise ValueError(f"Unsupported MP case: {case_id}")
                self.case_results.append(result)
        if len(self.case_results) != 25:
            raise RuntimeError(f"Expected 25 MP outcomes, observed {len(self.case_results)}")
        return self.case_results, self.ledger.rows, self.checkpoints


CASE_RESULT_COLUMNS = [
    "design_version",
    "implementation_hash",
    "case_id",
    "sublevel",
    "variant",
    "history_1",
    "history_2",
    "declared_packet_equal",
    "expected_classification",
    "observed_classification",
    "delta_stress",
    "delta_residual",
    "delta_tangent",
    "committed_hash_equal",
    "operator_hash_equal",
    "accepted_source_valid",
    "checkpoint_equal",
    "finite",
    "gate_failed",
    "passed",
]


CHECKPOINT_COLUMNS = [
    "run_id",
    "case_id",
    "accepted_version",
    "candidate_id",
    "epsilon_or_u",
    "force",
    "sigma",
    "epsilon_p",
    "kappa",
    "plastic_dissipation",
    "committed_state_hash",
    "source_call_index",
]


def deterministic_rows_hash(rows: list[dict[str, Any]]) -> str:
    return canonical_hash(rows)


def checkpoint_payload_json(payload: dict[str, Any]) -> str:
    return canonical_json(payload)
