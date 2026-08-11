from __future__ import annotations

from typing import Any

from .model import ContractError, Outcome, Verdict


REQUIRED_KEYS = frozenset(
    {
        "schema_version",
        "implementation_version",
        "case_id",
        "run_id",
        "subject_id",
        "partition",
        "expected_verdict",
        "observed_outcome",
        "four_way_verdict",
        "stage",
        "pass_flag",
        "applicability_evaluated",
        "eligibility_evaluated",
        "lifecycle_evaluated",
        "capability",
        "packet_a_fingerprint",
        "packet_b_fingerprint",
        "mismatch_fields",
        "active_signals",
        "reasons",
    }
)


def _require_list_of_strings(payload: dict[str, Any], key: str) -> None:
    value = payload[key]
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ContractError(f"{key} must be a list of strings")


def validate_case_result_payload(payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise ContractError("case result must be an object")
    keys = frozenset(payload)
    if keys != REQUIRED_KEYS:
        missing = sorted(REQUIRED_KEYS.difference(keys))
        extra = sorted(keys.difference(REQUIRED_KEYS))
        raise ContractError(f"case-result keys differ; missing={missing}, extra={extra}")
    if payload["schema_version"] != "JSS-P5B-CASE-RESULT-1.1":
        raise ContractError("case-result schema version drift")
    if payload["implementation_version"] != "JSS-P5B-IMPL-1.0a":
        raise ContractError("implementation version drift")
    expected = Verdict(payload["expected_verdict"])
    outcome = Outcome(payload["observed_outcome"])
    verdict_value = payload["four_way_verdict"]
    verdict = Verdict(verdict_value) if verdict_value is not None else None
    for key in (
        "pass_flag",
        "applicability_evaluated",
        "eligibility_evaluated",
        "lifecycle_evaluated",
    ):
        if type(payload[key]) is not bool:
            raise ContractError(f"{key} must be boolean")
    for key in ("mismatch_fields", "active_signals", "reasons"):
        _require_list_of_strings(payload, key)
    for key in ("packet_a_fingerprint", "packet_b_fingerprint"):
        value = payload[key]
        if not isinstance(value, str) or len(value) != 64:
            raise ContractError(f"{key} must be a SHA-256 hex string")
        try:
            int(value, 16)
        except ValueError as exc:
            raise ContractError(f"{key} is not hexadecimal") from exc
    capability = payload["capability"]
    capability_keys = {
        "observable",
        "required_tokens",
        "available_tokens",
        "missing_fields",
        "missing_events",
    }
    if not isinstance(capability, dict) or set(capability) != capability_keys:
        raise ContractError("capability object does not match the frozen schema")
    if type(capability["observable"]) is not bool:
        raise ContractError("capability.observable must be boolean")
    for key in capability_keys.difference({"observable"}):
        _require_list_of_strings(capability, key)
    if outcome is Outcome.EXECUTION_ERROR:
        if verdict is not None or payload["pass_flag"]:
            raise ContractError("execution error cannot carry a four-way pass verdict")
        if payload["stage"] != "EXECUTION":
            raise ContractError("execution error must stop at the execution stage")
        if any(
            payload[key]
            for key in (
                "applicability_evaluated",
                "eligibility_evaluated",
                "lifecycle_evaluated",
            )
        ):
            raise ContractError("execution error cannot report later-stage evaluation")
        if payload["active_signals"]:
            raise ContractError("execution error cannot carry lifecycle signals")
    else:
        if verdict is None or verdict.value != outcome.value:
            raise ContractError("four-way verdict and observed outcome differ")
        if payload["pass_flag"] != (verdict is expected):
            raise ContractError("pass_flag is inconsistent with expected verdict")
    if verdict in {Verdict.INVALID, Verdict.NOT_SUPPORTED}:
        if payload["lifecycle_evaluated"] or payload["active_signals"]:
            raise ContractError("ineligible or unsupported result evaluated lifecycle signals")
    if verdict is Verdict.NOT_SUPPORTED:
        if payload["stage"] != "APPLICABILITY":
            raise ContractError("NOT_SUPPORTED must stop at applicability")
        if not payload["applicability_evaluated"] or payload["eligibility_evaluated"]:
            raise ContractError("NOT_SUPPORTED stage flags are inconsistent")
        if capability["observable"]:
            raise ContractError("NOT_SUPPORTED requires an unobservable capability")
        if not (capability["missing_fields"] or capability["missing_events"]):
            raise ContractError("NOT_SUPPORTED must name missing evidence")
    if verdict is Verdict.INVALID:
        if payload["stage"] != "ELIGIBILITY":
            raise ContractError("INVALID must stop at eligibility")
        if not payload["applicability_evaluated"] or not payload["eligibility_evaluated"]:
            raise ContractError("INVALID stage flags are inconsistent")
    if verdict in {Verdict.PASS_INVARIANT, Verdict.DETECT_LIFECYCLE_DRIFT}:
        if payload["stage"] != "LIFECYCLE":
            raise ContractError("eligible verdict must use the lifecycle stage")
        if not payload["applicability_evaluated"] or not payload["eligibility_evaluated"]:
            raise ContractError("eligible verdict skipped a prerequisite stage")
        if not payload["lifecycle_evaluated"]:
            raise ContractError("eligible verdict requires lifecycle evaluation")
    if verdict is Verdict.PASS_INVARIANT and payload["active_signals"]:
        raise ContractError("PASS_INVARIANT cannot carry active lifecycle signals")
    if verdict is Verdict.DETECT_LIFECYCLE_DRIFT and not payload["active_signals"]:
        raise ContractError("DETECT_LIFECYCLE_DRIFT must name an active signal")
