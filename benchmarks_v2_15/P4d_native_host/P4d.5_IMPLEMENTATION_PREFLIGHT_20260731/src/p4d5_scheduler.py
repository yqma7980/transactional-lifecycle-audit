from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from p4d5_protocol import CASE_ORDER, EXPECTED_VERDICTS, RUN_IDS

PASS = "PASS"
FAIL = "FAIL"
NOT_SUPPORTED = "NOT_SUPPORTED"
INCOMPLETE = "INCOMPLETE"
READY = "READY"
WAITING = "WAITING"
SKIPPED_DEPENDENCY = "SKIPPED_DEPENDENCY"

WAVE_ONE = ("P4D-SAFE-RT-01", "P4D-SAFE-RS-01", "P4D-VER-01")
RETRY_DEPENDENTS = ("P4D-NC-CACHE-01", "P4D-NC-OUTPUT-01")


@dataclass(frozen=True)
class PairStatus:
    case_id: str
    classification: str
    observed_run_ids: tuple[str, ...]
    reason: str
    normalized_results_equal: bool | None


def _contains_not_supported(value: Any) -> bool:
    if isinstance(value, str):
        return "NOT_SUPPORTED" in value
    if isinstance(value, Mapping):
        return any(_contains_not_supported(item) for item in value.values())
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return any(_contains_not_supported(item) for item in value)
    return False


def _normalize_run_semantics(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            key: _normalize_run_semantics(item)
            for key, item in value.items()
            if key != "run_id"
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_normalize_run_semantics(item) for item in value]
    if isinstance(value, str):
        return value.replace("run_1", "<run>").replace("run_2", "<run>")
    return value


def _pass_flag_is_true(value: Any) -> bool:
    return value is True or (type(value) is int and value == 1)


def classify_case_pair(
    case_id: str,
    run_results: Sequence[Mapping[str, Any]],
) -> PairStatus:
    if case_id not in EXPECTED_VERDICTS:
        raise ValueError(f"unknown P4d.5 case: {case_id}")
    by_run = {str(item.get("run_id")): item for item in run_results}
    observed = tuple(run_id for run_id in RUN_IDS if run_id in by_run)
    if (
        observed != RUN_IDS
        or len(run_results) != len(RUN_IDS)
        or set(by_run) != set(RUN_IDS)
    ):
        return PairStatus(
            case_id,
            INCOMPLETE,
            observed,
            "exactly the two frozen run IDs are required",
            None,
        )
    ordered = [by_run[run_id] for run_id in RUN_IDS]
    normalized_equal = (
        _normalize_run_semantics(ordered[0])
        == _normalize_run_semantics(ordered[1])
    )
    if not normalized_equal:
        return PairStatus(
            case_id,
            FAIL,
            observed,
            "fresh-process case results differ after run-ID normalization",
            False,
        )
    if any(_contains_not_supported(item) for item in ordered):
        return PairStatus(
            case_id,
            NOT_SUPPORTED,
            observed,
            "a frozen trigger or capability was not supported",
            True,
        )
    expected = EXPECTED_VERDICTS[case_id]
    if all(
        _pass_flag_is_true(item.get("pass_flag"))
        and item.get("primary_verdict") == expected
        for item in ordered
    ):
        return PairStatus(
            case_id,
            PASS,
            observed,
            "both fresh-process repetitions passed the frozen contract",
            True,
        )
    return PairStatus(
        case_id,
        FAIL,
        observed,
        "at least one repetition failed or returned a verdict mismatch",
        True,
    )


def schedule_state(pair_statuses: Mapping[str, str]) -> dict[str, str]:
    unknown = set(pair_statuses) - set(CASE_ORDER)
    if unknown:
        raise ValueError(f"unknown case status keys: {sorted(unknown)}")
    state: dict[str, str] = {}
    for case_id in WAVE_ONE:
        state[case_id] = pair_statuses.get(case_id, READY)
    retry_status = pair_statuses.get("P4D-SAFE-RT-01")
    for case_id in RETRY_DEPENDENTS:
        if case_id in pair_statuses:
            state[case_id] = pair_statuses[case_id]
        elif retry_status == PASS:
            state[case_id] = READY
        elif retry_status in {FAIL, NOT_SUPPORTED}:
            state[case_id] = SKIPPED_DEPENDENCY
        else:
            state[case_id] = WAITING
    return {case_id: state[case_id] for case_id in CASE_ORDER}


def eligible_cases(pair_statuses: Mapping[str, str]) -> tuple[str, ...]:
    state = schedule_state(pair_statuses)
    return tuple(case_id for case_id in CASE_ORDER if state[case_id] == READY)


def aggregate_boundary(pair_statuses: Mapping[str, str]) -> str:
    state = schedule_state(pair_statuses)
    terminal = {PASS, FAIL, NOT_SUPPORTED, SKIPPED_DEPENDENCY}
    if not all(value in terminal for value in state.values()):
        return "P4D5_BRANCH_EXECUTION_INCOMPLETE"
    if all(value == PASS for value in state.values()):
        return "P4D5_PAIR_CONTRACTS_PASS_PENDING_FULL_FILE_DUPLICATE_QA"
    return "P4D5_BRANCH_EXECUTION_COMPLETE_WITH_NONPASS_OR_SKIPPED_BRANCHES"
