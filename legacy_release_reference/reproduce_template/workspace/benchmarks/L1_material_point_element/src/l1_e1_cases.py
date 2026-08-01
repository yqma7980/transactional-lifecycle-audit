"""Execution of the eight frozen L1-E1 cases and 20 variant outcomes."""

from __future__ import annotations

from collections import defaultdict
import csv
from fractions import Fraction
import json
from pathlib import Path
from typing import Any

from .l1_cases import CASE_RESULT_COLUMNS, CHECKPOINT_COLUMNS
from .l1_element import ElementData, ElementOutputSnapshot, ElementResult, evaluate_element, read_element_output
from .l1_ledger import Ledger, bool_text, decimal_text, float_hex
from .l1_material import incremental_plastic_dissipation
from .l1_state import CommittedState, MaterialData, canonical_hash, checkpoint_payload, checkpoint_restore
from .l1_variants import VARIANTS

DESIGN_VERSION = "L1-D1.0"
RUN_ID = "L1-E1-D1.0-REPLAY"


def _fraction(value: str) -> float:
    return float(Fraction(value))


def _bool_or_na(value: bool | None) -> str:
    return "NA" if value is None else bool_text(value)


class E1Benchmark:
    def __init__(self, root: Path, implementation_hash: str) -> None:
        self.root = root
        self.implementation_hash = implementation_hash
        self.material = MaterialData()
        self.material_hash = self.material.fingerprint
        self.element = ElementData()
        self.freeze = json.loads((root / "L1_E1_execution_freeze.json").read_text(encoding="utf-8"))
        self.configuration_hash = canonical_hash({
            "design_version": DESIGN_VERSION,
            "freeze": self.freeze,
            "case_matrix": (root / "L1_case_matrix.csv").read_text(encoding="utf-8"),
            "element": self.element,
        })
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

    def _variant(self, name: str, committed: CommittedState | None = None) -> Any:
        return VARIANTS[name](self.material, committed)

    def _next_call(self, case_id: str, variant_name: str, history_id: str) -> int:
        key = (case_id, variant_name, history_id)
        value = self._call_counters[key]
        self._call_counters[key] += 1
        return value

    def _event_packet_hash(
        self, case_id: str, variant_name: str, history_id: str,
        event: str, committed: CommittedState,
    ) -> str:
        return canonical_hash({
            "design_version": DESIGN_VERSION,
            "case_id": case_id,
            "sublevel": "L1-E1",
            "variant": variant_name,
            "history_id": history_id,
            "event": event,
            "committed_state_hash": committed.fingerprint,
            "accepted_version": committed.accepted_version,
            "material_parameters_hash": self.material_hash,
            "element_configuration_hash": self.element.fingerprint,
            "configuration_hash": self.configuration_hash,
        })

    def _record(
        self, *, case_id: str, variant: Any, history_id: str, event: str,
        attempt_id: str, candidate_id: str, before: CommittedState,
        after: CommittedState, persistent_before: str, persistent_after: str,
        u: float | None = None, force: float | None = None,
        result: ElementResult | None = None, output_source_version: str = "NA",
        candidate_reachable_after: bool = False, event_valid: bool = True,
        note: str = "ok", declared_packet_hash: str | None = None,
        candidate_state_hash: str | None = None,
    ) -> dict[str, Any]:
        call_index = self._next_call(case_id, variant.name, history_id)
        packet_hash = declared_packet_hash or self._event_packet_hash(
            case_id, variant.name, history_id, event, before
        )
        candidate = result.candidate if result is not None else None
        epsilon = None if u is None else (u - self.element.u1) / self.element.length
        return self.ledger.append(
            design_version=DESIGN_VERSION, run_id=RUN_ID,
            implementation_hash=self.implementation_hash, case_id=case_id,
            sublevel="L1-E1", variant=variant.name, history_id=history_id,
            call_index=call_index, event=event, attempt_id=attempt_id,
            candidate_id=candidate_id, operator_version=self.element.operator_version,
            declared_packet_hash=packet_hash, material_parameters_hash=self.material_hash,
            configuration_hash=self.configuration_hash,
            accepted_version_before=before.accepted_version,
            accepted_version_after=after.accepted_version,
            committed_state_hash_before=before.fingerprint,
            committed_state_hash_after=after.fingerprint,
            candidate_state_hash=(candidate_state_hash if candidate_state_hash is not None
                                  else (candidate.fingerprint if candidate is not None else "NA")),
            persistent_state_hash_before=persistent_before,
            persistent_state_hash_after=persistent_after,
            epsilon_hex=float_hex(epsilon), u_hex=float_hex(u), force_hex=float_hex(force),
            epsilon_p_committed_hex=before.epsilon_p.hex(),
            kappa_committed_hex=before.kappa.hex(),
            sigma_hex=float_hex(None if result is None else result.sigma),
            E_alg_hex=float_hex(None if result is None else result.E_alg),
            residual_hex=float_hex(None if result is None else result.residual),
            tangent_hex=float_hex(None if result is None else result.tangent),
            epsilon_p_candidate_hex=float_hex(None if candidate is None else candidate.epsilon_p),
            kappa_candidate_hex=float_hex(None if candidate is None else candidate.kappa),
            residual_state_version="NA" if result is None else result.residual_state_version,
            tangent_state_version="NA" if result is None else result.tangent_state_version,
            output_source_version=output_source_version,
            candidate_reachable_after=bool_text(candidate_reachable_after),
            finite=bool_text(True if result is None else result.finite),
            event_valid=bool_text(event_valid), note=note,
        )

    def _begin_attempt(
        self, case_id: str, variant: Any, history_id: str, attempt_id: str
    ) -> None:
        before = variant.committed
        persistent = variant.persistent_hash
        if hasattr(variant, "begin_attempt"):
            variant.begin_attempt(attempt_id)
        self._record(
            case_id=case_id, variant=variant, history_id=history_id,
            event="BeginAttempt", attempt_id=attempt_id, candidate_id="NA",
            before=before, after=variant.committed, persistent_before=persistent,
            persistent_after=variant.persistent_hash, note="element_attempt_declared",
        )

    def _evaluate(
        self, case_id: str, variant: Any, history_id: str, *,
        u: float, force: float, attempt_id: str, candidate_id: str,
    ) -> tuple[ElementResult, dict[str, Any]]:
        before = variant.committed
        persistent_before = variant.persistent_hash
        source_call_index = self._call_counters[(case_id, variant.name, history_id)]
        seeded_mismatch = variant.name == "seeded_version_mismatch"
        result = evaluate_element(
            variant, self.element, case_id=case_id,
            configuration_hash=self.configuration_hash, u=u, force=force,
            candidate_id=candidate_id, attempt_id=attempt_id,
            source_call_index=source_call_index,
            seeded_version_mismatch=seeded_mismatch,
        )
        hidden_seed = variant.name in {"unsafe_trial_cache", "unsafe_output_feedback"}
        row = self._record(
            case_id=case_id, variant=variant, history_id=history_id,
            event="EvaluateElement", attempt_id=attempt_id,
            candidate_id=candidate_id, before=before, after=variant.committed,
            persistent_before=persistent_before,
            persistent_after=variant.persistent_hash, u=u, force=force,
            result=result,
            candidate_reachable_after=variant.candidate_reachable(candidate_id),
            event_valid=result.version_compatible and not hidden_seed,
            note=("seeded_version_mismatch" if seeded_mismatch else
                  ("seeded_hidden_state_access" if hidden_seed else "thin_element_assembly")),
            declared_packet_hash=result.declared_packet_hash,
        )
        return result, row

    def _reject_attempt(
        self, case_id: str, variant: Any, history_id: str, attempt_id: str
    ) -> tuple[str, ...]:
        before = variant.committed
        persistent_before = variant.persistent_hash
        invalidated = variant.reject_attempt(attempt_id)
        unsafe = variant.name == "unsafe_trial_cache"
        self._record(
            case_id=case_id, variant=variant, history_id=history_id,
            event="RejectAttempt", attempt_id=attempt_id, candidate_id="NA",
            before=before, after=variant.committed,
            persistent_before=persistent_before,
            persistent_after=variant.persistent_hash,
            candidate_reachable_after=False, event_valid=not unsafe,
            note="seeded_cache_not_rolled_back" if unsafe else "candidates_invalidated",
        )
        return invalidated

    def _accept(
        self, case_id: str, variant: Any, history_id: str, result: ElementResult
    ) -> tuple[bool, str]:
        before = variant.committed
        persistent_before = variant.persistent_hash
        dissipation = incremental_plastic_dissipation(before, result.candidate, self.material)
        accepted, reason = variant.accept(result.candidate)
        after = variant.committed
        self._record(
            case_id=case_id, variant=variant, history_id=history_id,
            event="AcceptCandidate", attempt_id=result.candidate.attempt_id,
            candidate_id=result.candidate.candidate_id, before=before, after=after,
            persistent_before=persistent_before,
            persistent_after=variant.persistent_hash, u=result.u, force=result.force,
            result=result,
            candidate_reachable_after=variant.candidate_reachable(
                result.candidate.candidate_id
            ),
            event_valid=True, note=reason,
            declared_packet_hash=result.declared_packet_hash,
        )
        if accepted:
            self.checkpoints.append({
                "run_id": RUN_ID, "case_id": case_id,
                "accepted_version": str(after.accepted_version),
                "candidate_id": result.candidate.candidate_id,
                "epsilon_or_u": decimal_text(result.u),
                "force": decimal_text(result.force),
                "sigma": decimal_text(result.sigma),
                "epsilon_p": decimal_text(after.epsilon_p),
                "kappa": decimal_text(after.kappa),
                "plastic_dissipation": decimal_text(dissipation),
                "committed_state_hash": after.fingerprint,
                "source_call_index": str(result.candidate.source_call_index),
            })
        return accepted, reason

    def _output_read(
        self, case_id: str, variant: Any, history_id: str, trigger_u: float
    ) -> tuple[ElementOutputSnapshot, bool]:
        before = variant.committed
        persistent_before = variant.persistent_hash
        snapshot = read_element_output(
            variant, self.element, trigger_u=trigger_u,
            configuration_hash=self.configuration_hash,
        )
        valid = (
            snapshot.accepted_source_valid
            and before == variant.committed
            and persistent_before == variant.persistent_hash
        )
        self._record(
            case_id=case_id, variant=variant, history_id=history_id,
            event="OutputAcceptedState", attempt_id="NA",
            candidate_id=snapshot.source_candidate_id, before=before,
            after=variant.committed, persistent_before=persistent_before,
            persistent_after=variant.persistent_hash, u=trigger_u,
            output_source_version=snapshot.source_version,
            candidate_reachable_after=False, event_valid=valid,
            note="accepted_read_only" if valid else "seeded_output_feedback",
            candidate_state_hash=snapshot.fingerprint,
        )
        return snapshot, valid


    def _checkpoint_write(
        self, case_id: str, variant: Any, history_id: str
    ) -> dict[str, Any]:
        before = variant.committed
        payload = checkpoint_payload(before, self.configuration_hash)
        self._record(
            case_id=case_id, variant=variant, history_id=history_id,
            event="CheckpointWrite", attempt_id="NA", candidate_id="NA",
            before=before, after=variant.committed,
            persistent_before=variant.persistent_hash,
            persistent_after=variant.persistent_hash,
            candidate_state_hash=canonical_hash(payload),
            note="complete_element_committed_payload",
        )
        return payload

    def _checkpoint_read(
        self, case_id: str, variant: Any, history_id: str, payload: dict[str, Any]
    ) -> CommittedState:
        before = variant.committed
        restored = checkpoint_restore(payload, self.configuration_hash)
        self._record(
            case_id=case_id, variant=variant, history_id=history_id,
            event="CheckpointRead", attempt_id="NA", candidate_id="NA",
            before=before, after=before,
            persistent_before=variant.persistent_hash,
            persistent_after=variant.persistent_hash,
            candidate_state_hash=canonical_hash(payload),
            event_valid=restored.fingerprint == payload["committed_state_hash"],
            note="element_checkpoint_verified",
        )
        return restored

    def _result_row(
        self, *, case: dict[str, str], variant: str, expected: str,
        observed: str, declared_equal: bool, delta_stress: float | None,
        delta_residual: float | None, delta_tangent: float | None,
        committed_equal: bool, operator_equal: bool,
        accepted_source_valid: bool | None, checkpoint_equal: bool | None,
        finite: bool, passed: bool, gate_failed: str = "NA",
    ) -> dict[str, str]:
        return {
            "design_version": DESIGN_VERSION,
            "implementation_hash": self.implementation_hash,
            "case_id": case["case_id"], "sublevel": "L1-E1",
            "variant": variant, "history_1": case["history_1"],
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
            "finite": bool_text(finite), "gate_failed": gate_failed,
            "passed": bool_text(passed),
        }

    def _reference_case(
        self, case: dict[str, str], variant_name: str
    ) -> dict[str, str]:
        key = "elastic" if case["case_id"] == "E1-REF-01" else "plastic_equilibrium"
        packet = self.freeze["reference_packets"][key]
        u, force = _fraction(packet["u"]), _fraction(packet["force"])
        expected_R = _fraction(packet["residual"])
        expected_K = _fraction(packet["tangent"])
        variant = self._variant(variant_name)
        self._begin_attempt(case["case_id"], variant, "REFERENCE", "reference")
        result, _ = self._evaluate(
            case["case_id"], variant, "REFERENCE", u=u, force=force,
            attempt_id="reference", candidate_id="reference_candidate",
        )
        self._reject_attempt(case["case_id"], variant, "REFERENCE", "reference")
        R_error = abs(result.residual - expected_R)
        K_error = abs(result.tangent - expected_K)
        R_ok = (
            R_error <= self.tolerances["analytical_absolute"]
            and R_error / max(1.0, abs(expected_R))
            <= self.tolerances["analytical_relative"]
        )
        K_ok = (
            K_error <= self.tolerances["analytical_absolute"]
            and K_error / max(1.0, abs(expected_K))
            <= self.tolerances["analytical_relative"]
        )
        passed = result.finite and result.version_compatible and R_ok and K_ok
        return self._result_row(
            case=case, variant=variant_name,
            expected="PASS_ANALYTICAL_ELEMENT_REFERENCE",
            observed=("PASS_ANALYTICAL_ELEMENT_REFERENCE" if passed
                      else "FAIL_ANALYTICAL_ELEMENT_REFERENCE"),
            declared_equal=True, delta_stress=result.sigma - force,
            delta_residual=result.residual - expected_R,
            delta_tangent=result.tangent - expected_K,
            committed_equal=variant.committed == CommittedState(),
            operator_equal=R_ok and K_ok and result.version_compatible,
            accepted_source_valid=None, checkpoint_equal=None,
            finite=result.finite, passed=passed,
            gate_failed="NA" if passed else "analytical_reference",
        )

    def _rejected_history(
        self, case_id: str, variant_name: str, history_id: str,
        discarded_u: list[float],
    ) -> tuple[Any, ElementResult, dict[str, Any], bool]:
        variant = self._variant(variant_name)
        initial_hash = variant.committed.fingerprint
        if discarded_u:
            self._begin_attempt(case_id, variant, history_id, "discarded")
            ids: list[str] = []
            for index, u in enumerate(discarded_u, start=1):
                candidate_id = f"discarded_candidate_{index}"
                ids.append(candidate_id)
                self._evaluate(
                    case_id, variant, history_id, u=u,
                    force=_fraction(self.freeze["discarded_force"]),
                    attempt_id="discarded", candidate_id=candidate_id,
                )
            self._reject_attempt(case_id, variant, history_id, "discarded")
            unreachable = all(not variant.candidate_reachable(value) for value in ids)
        else:
            unreachable = True
        replay = self.freeze["common_replay"]
        self._begin_attempt(case_id, variant, history_id, "replay")
        result, row = self._evaluate(
            case_id, variant, history_id, u=_fraction(replay["u"]),
            force=_fraction(replay["force"]), attempt_id="replay",
            candidate_id="replay_candidate",
        )
        self._reject_attempt(case_id, variant, history_id, "replay")
        state_ok = initial_hash == variant.committed.fingerprint and unreachable
        return variant, result, row, state_ok


    def _lifecycle_replay_case(
        self, case: dict[str, str], variant_name: str
    ) -> dict[str, str]:
        case_id = case["case_id"]
        if case_id == "E1-LC-01":
            history_1, history_2 = [0.03], []
        else:
            history_1 = [_fraction(v) for v in self.freeze["call_order_history_1"]]
            history_2 = [_fraction(v) for v in self.freeze["call_order_history_2"]]
        _, result_1, row_1, state_ok_1 = self._rejected_history(
            case_id, variant_name, "H1", history_1
        )
        _, result_2, row_2, state_ok_2 = self._rejected_history(
            case_id, variant_name, "H2", history_2
        )
        delta_R = result_1.residual - result_2.residual
        delta_K = result_1.tangent - result_2.tangent
        delta_sigma = result_1.sigma - result_2.sigma
        declared_equal = row_1["declared_packet_hash"] == row_2["declared_packet_hash"]
        operator_equal = result_1.operator_fingerprint == result_2.operator_fingerprint
        finite = result_1.finite and result_2.finite
        if variant_name == "unsafe_trial_cache":
            if case_id == "E1-LC-01":
                seed_ok = abs(delta_R - _fraction("-205/121")) <= self.tolerances[
                    "analytical_absolute"
                ]
            else:
                seed_ok = (
                    abs(delta_R) > self.tolerances["unsafe_minimum_drift"]
                    and abs(delta_R) >= 1000.0e-15
                )
            passed = (
                declared_equal and state_ok_1 and state_ok_2 and finite
                and seed_ok and not operator_equal
            )
            expected = "DETECT_FINITE_SEEDED_ELEMENT_TRIAL_DRIFT"
            observed = ("DETECTED_FINITE_SEEDED_ELEMENT_TRIAL_DRIFT" if passed
                        else "UNSAFE_ELEMENT_SEED_NOT_DETECTED")
        else:
            passed = (
                declared_equal and state_ok_1 and state_ok_2 and finite
                and delta_R == 0.0 and delta_K == 0.0 and delta_sigma == 0.0
                and operator_equal
            )
            expected = "PASS_EXACT_ELEMENT_REPLAY_INVARIANCE"
            observed = ("PASS_EXACT_ELEMENT_REPLAY_INVARIANCE" if passed
                        else "SAFE_ELEMENT_REPLAY_FALSE_POSITIVE")
        return self._result_row(
            case=case, variant=variant_name, expected=expected, observed=observed,
            declared_equal=declared_equal, delta_stress=delta_sigma,
            delta_residual=delta_R, delta_tangent=delta_K,
            committed_equal=state_ok_1 and state_ok_2,
            operator_equal=operator_equal, accepted_source_valid=None,
            checkpoint_equal=None, finite=finite, passed=passed,
            gate_failed="NA" if passed else "lifecycle",
        )

    def _terminal_feedback_case(
        self, case: dict[str, str], variant_name: str
    ) -> dict[str, str]:
        case_id = case["case_id"]
        trigger = _fraction(self.freeze["terminal_seed_u"])
        replay = self.freeze["common_replay"]
        variant_1 = self._variant(variant_name)
        initial_1 = variant_1.committed.fingerprint
        _, source_valid_1 = self._output_read(case_id, variant_1, "H1", trigger)
        self._begin_attempt(case_id, variant_1, "H1", "replay")
        result_1, row_1 = self._evaluate(
            case_id, variant_1, "H1", u=_fraction(replay["u"]),
            force=_fraction(replay["force"]), attempt_id="replay",
            candidate_id="replay_candidate",
        )
        self._reject_attempt(case_id, variant_1, "H1", "replay")

        variant_2 = self._variant(variant_name)
        initial_2 = variant_2.committed.fingerprint
        self._begin_attempt(case_id, variant_2, "H2", "replay")
        result_2, row_2 = self._evaluate(
            case_id, variant_2, "H2", u=_fraction(replay["u"]),
            force=_fraction(replay["force"]), attempt_id="replay",
            candidate_id="replay_candidate",
        )
        self._reject_attempt(case_id, variant_2, "H2", "replay")

        delta_R = result_1.residual - result_2.residual
        delta_K = result_1.tangent - result_2.tangent
        declared_equal = row_1["declared_packet_hash"] == row_2["declared_packet_hash"]
        committed_equal = (
            variant_1.committed.fingerprint == initial_1
            and variant_2.committed.fingerprint == initial_2
        )
        operator_equal = result_1.operator_fingerprint == result_2.operator_fingerprint
        finite = result_1.finite and result_2.finite
        if variant_name == "unsafe_output_feedback":
            passed = (
                declared_equal and committed_equal and finite
                and abs(delta_R) > self.tolerances["unsafe_minimum_drift"]
                and not source_valid_1 and not operator_equal
            )
            expected = "DETECT_FINITE_ELEMENT_OUTPUT_FEEDBACK_DRIFT"
            observed = ("DETECTED_FINITE_ELEMENT_OUTPUT_FEEDBACK_DRIFT" if passed
                        else "ELEMENT_OUTPUT_SEED_NOT_DETECTED")
            accepted_source_valid = False
        else:
            passed = (
                declared_equal and committed_equal and finite and source_valid_1
                and delta_R == 0.0 and delta_K == 0.0 and operator_equal
            )
            expected = "PASS_ELEMENT_OUTPUT_NONINTERFERENCE"
            observed = ("PASS_ELEMENT_OUTPUT_NONINTERFERENCE" if passed
                        else "SAFE_ELEMENT_OUTPUT_FALSE_POSITIVE")
            accepted_source_valid = source_valid_1
        return self._result_row(
            case=case, variant=variant_name, expected=expected, observed=observed,
            declared_equal=declared_equal,
            delta_stress=result_1.sigma - result_2.sigma,
            delta_residual=delta_R, delta_tangent=delta_K,
            committed_equal=committed_equal, operator_equal=operator_equal,
            accepted_source_valid=accepted_source_valid, checkpoint_equal=None,
            finite=finite, passed=passed,
            gate_failed="NA" if passed else "terminal_output",
        )


    def _output_provenance_case(
        self, case: dict[str, str], variant_name: str
    ) -> dict[str, str]:
        case_id = case["case_id"]
        trigger = _fraction(self.freeze["terminal_seed_u"])
        force = _fraction(
            self.freeze["reference_packets"]["virgin_plastic_operator"]["force"]
        )
        variant_1 = self._variant(variant_name)
        initial_1 = variant_1.committed.fingerprint
        self._begin_attempt(case_id, variant_1, "H1", "trial")
        self._evaluate(
            case_id, variant_1, "H1", u=trigger, force=force,
            attempt_id="trial", candidate_id="trial_candidate",
        )
        output_1, valid_1 = self._output_read(case_id, variant_1, "H1", trigger)
        self._reject_attempt(case_id, variant_1, "H1", "trial")

        variant_2 = self._variant(variant_name)
        initial_2 = variant_2.committed.fingerprint
        output_2, valid_2 = self._output_read(case_id, variant_2, "H2", trigger)
        committed_equal = (
            variant_1.committed.fingerprint == initial_1
            and variant_2.committed.fingerprint == initial_2
            and initial_1 == initial_2
        )
        output_equal = output_1.fingerprint == output_2.fingerprint
        passed = (
            valid_1 and valid_2 and committed_equal and output_equal
            and output_1.source_candidate_id == "NA"
            and output_2.source_candidate_id == "NA"
        )
        return self._result_row(
            case=case, variant=variant_name,
            expected="PASS_ACCEPTED_OUTPUT_PROVENANCE",
            observed=("PASS_ACCEPTED_OUTPUT_PROVENANCE" if passed
                      else "FAIL_ACCEPTED_OUTPUT_PROVENANCE"),
            declared_equal=True, delta_stress=None, delta_residual=None,
            delta_tangent=None, committed_equal=committed_equal,
            operator_equal=output_equal, accepted_source_valid=valid_1 and valid_2,
            checkpoint_equal=None, finite=True, passed=passed,
            gate_failed="NA" if passed else "output_provenance",
        )

    def _checkpoint_case(
        self, case: dict[str, str], variant_name: str
    ) -> dict[str, str]:
        case_id = case["case_id"]
        accept_packet = self.freeze["checkpoint_accept_packet"]
        replay_packet = self.freeze["checkpoint_replay_packet"]
        source = self._variant(variant_name)
        self._begin_attempt(case_id, source, "H1", "load")
        load, _ = self._evaluate(
            case_id, source, "H1", u=_fraction(accept_packet["u"]),
            force=_fraction(accept_packet["force"]), attempt_id="load",
            candidate_id="accepted_candidate",
        )
        accepted, _ = self._accept(case_id, source, "H1", load)
        payload = self._checkpoint_write(case_id, source, "H1")
        restored_state = self._checkpoint_read(case_id, source, "H1", payload)
        restored = self._variant(variant_name, restored_state)
        direct = self._variant(variant_name, source.committed)

        self._begin_attempt(case_id, restored, "H1", "replay")
        result_1, row_1 = self._evaluate(
            case_id, restored, "H1", u=_fraction(replay_packet["u"]),
            force=_fraction(replay_packet["force"]), attempt_id="replay",
            candidate_id="replay_candidate",
        )
        self._reject_attempt(case_id, restored, "H1", "replay")
        self._begin_attempt(case_id, direct, "H2", "replay")
        result_2, row_2 = self._evaluate(
            case_id, direct, "H2", u=_fraction(replay_packet["u"]),
            force=_fraction(replay_packet["force"]), attempt_id="replay",
            candidate_id="replay_candidate",
        )
        self._reject_attempt(case_id, direct, "H2", "replay")

        declared_equal = row_1["declared_packet_hash"] == row_2["declared_packet_hash"]
        checkpoint_equal = restored_state.fingerprint == source.committed.fingerprint
        operator_equal = (
            result_1.residual_fingerprint == result_2.residual_fingerprint
            and result_1.tangent_fingerprint == result_2.tangent_fingerprint
            and result_1.operator_fingerprint == result_2.operator_fingerprint
        )
        passed = (
            accepted and declared_equal and checkpoint_equal and operator_equal
            and result_1.residual == result_2.residual
            and result_1.tangent == result_2.tangent
        )
        return self._result_row(
            case=case, variant=variant_name,
            expected="PASS_ELEMENT_CHECKPOINT_ROUND_TRIP",
            observed=("PASS_ELEMENT_CHECKPOINT_ROUND_TRIP" if passed
                      else "FAIL_ELEMENT_CHECKPOINT_ROUND_TRIP"),
            declared_equal=declared_equal,
            delta_stress=result_1.sigma - result_2.sigma,
            delta_residual=result_1.residual - result_2.residual,
            delta_tangent=result_1.tangent - result_2.tangent,
            committed_equal=checkpoint_equal, operator_equal=operator_equal,
            accepted_source_valid=True, checkpoint_equal=checkpoint_equal,
            finite=result_1.finite and result_2.finite, passed=passed,
            gate_failed="NA" if passed else "output_checkpoint",
        )


    def _version_case(
        self, case: dict[str, str], variant_name: str
    ) -> dict[str, str]:
        case_id = case["case_id"]
        packet = self.freeze["reference_packets"]["virgin_plastic_operator"]
        variant = self._variant(variant_name)
        self._begin_attempt(case_id, variant, "REFERENCE", "version_check")
        result, _ = self._evaluate(
            case_id, variant, "REFERENCE", u=_fraction(packet["u"]),
            force=_fraction(packet["force"]), attempt_id="version_check",
            candidate_id="version_candidate",
        )
        self._reject_attempt(case_id, variant, "REFERENCE", "version_check")
        R_ok = abs(result.residual - _fraction(packet["residual"])) <= self.tolerances[
            "analytical_absolute"
        ]
        K_ok = abs(result.tangent - _fraction(packet["tangent"])) <= self.tolerances[
            "analytical_absolute"
        ]
        if variant_name == "seeded_version_mismatch":
            passed = (
                result.finite and R_ok and K_ok and result.seeded_version_mismatch
                and not result.version_compatible
            )
            expected = "REJECT_SEEDED_VERSION_MISMATCH_BEFORE_LIFECYCLE_VERDICT"
            observed = (
                "REJECTED_SEEDED_VERSION_MISMATCH_BEFORE_LIFECYCLE_VERDICT"
                if passed else "FAILED_TO_DETECT_SEEDED_VERSION_MISMATCH"
            )
        else:
            passed = result.finite and R_ok and K_ok and result.version_compatible
            expected = "PASS_MATCHED_RESIDUAL_TANGENT_VERSIONS"
            observed = ("PASS_MATCHED_RESIDUAL_TANGENT_VERSIONS" if passed
                        else "FAIL_RESIDUAL_TANGENT_VERSION_COMPATIBILITY")
        return self._result_row(
            case=case, variant=variant_name, expected=expected, observed=observed,
            declared_equal=True,
            delta_stress=result.sigma - _fraction(packet["force"]),
            delta_residual=result.residual - _fraction(packet["residual"]),
            delta_tangent=result.tangent - _fraction(packet["tangent"]),
            committed_equal=variant.committed == CommittedState(),
            operator_equal=result.version_compatible, accepted_source_valid=None,
            checkpoint_equal=None, finite=result.finite, passed=passed,
            gate_failed="NA" if passed else "version_compatibility",
        )

    def run(
        self,
    ) -> tuple[list[dict[str, str]], list[dict[str, Any]], list[dict[str, str]]]:
        with (self.root / "L1_case_matrix.csv").open(
            "r", encoding="utf-8", newline=""
        ) as handle:
            cases = [
                row for row in csv.DictReader(handle) if row["sublevel"] == "L1-E1"
            ]
        cases.sort(key=lambda row: int(row["execution_order"]))
        for case in cases:
            for variant_name in case["variants_required"].split(";"):
                case_id = case["case_id"]
                if case_id in {"E1-REF-01", "E1-REF-02"}:
                    result = self._reference_case(case, variant_name)
                elif case_id in {"E1-LC-01", "E1-LC-02"}:
                    result = self._lifecycle_replay_case(case, variant_name)
                elif case_id == "E1-LC-03":
                    result = self._terminal_feedback_case(case, variant_name)
                elif case_id == "E1-LC-04":
                    result = self._output_provenance_case(case, variant_name)
                elif case_id == "E1-LC-05":
                    result = self._checkpoint_case(case, variant_name)
                elif case_id == "E1-OP-01":
                    result = self._version_case(case, variant_name)
                else:
                    raise ValueError(f"Unsupported E1 case: {case_id}")
                self.case_results.append(result)
        if len(self.case_results) != 20:
            raise RuntimeError(
                f"Expected 20 L1-E1 outcomes, observed {len(self.case_results)}"
            )
        return self.case_results, self.ledger.rows, self.checkpoints


__all__ = ["E1Benchmark", "CASE_RESULT_COLUMNS", "CHECKPOINT_COLUMNS"]

