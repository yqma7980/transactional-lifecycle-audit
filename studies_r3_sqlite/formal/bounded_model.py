from __future__ import annotations

import argparse
import itertools
import json
from collections import Counter, deque
from dataclasses import asdict, dataclass, replace
from pathlib import Path


@dataclass(frozen=True)
class State:
    phase: str = "idle"
    committed: int = 0
    trial: int = 0
    candidate: int = 0
    committed_candidate: int = 0
    accepted: bool = False
    last_commit_accepted: bool = False
    emitted: bool = False


ACTIONS = ("begin", "evaluate", "reject", "restore", "accept", "commit", "emit")


def step(state: State, action: str, *, guarded: bool) -> State | None:
    if action == "begin" and state.phase == "idle":
        return replace(
            state,
            phase="trial",
            trial=state.committed,
            candidate=state.candidate + 1,
            accepted=False,
        )
    if action == "evaluate" and state.phase == "trial":
        return replace(state, trial=1)
    if action == "reject" and state.phase == "trial":
        return replace(state, phase="rejected", accepted=False)
    if action == "restore" and state.phase == "rejected":
        return replace(state, phase="idle", trial=state.committed, accepted=False)
    if action == "accept" and state.phase == "trial":
        return replace(state, phase="accepted", accepted=True)
    if action == "commit" and state.phase in {"trial", "rejected", "accepted"}:
        if guarded and state.phase != "accepted":
            return None
        return replace(
            state,
            phase="idle",
            committed=state.trial,
            committed_candidate=state.candidate,
            last_commit_accepted=state.phase == "accepted",
            accepted=False,
        )
    if action == "emit":
        provenance_valid = (
            state.phase == "idle"
            and state.last_commit_accepted
            and state.candidate == state.committed_candidate
        )
        if guarded and not provenance_valid:
            return None
        return replace(state, emitted=True)
    return None


def explore(*, guarded: bool, depth: int) -> dict[str, object]:
    initial = State()
    queue = deque([(initial, tuple())])
    seen = {(initial, 0)}
    states = {initial}
    traces = 0
    commit_counterexamples: list[list[str]] = []
    output_counterexamples: list[list[str]] = []
    rollback_counterexamples: list[list[str]] = []
    while queue:
        state, trace = queue.popleft()
        if len(trace) >= depth:
            continue
        for action in ACTIONS:
            successor = step(state, action, guarded=guarded)
            if successor is None:
                continue
            new_trace = trace + (action,)
            traces += 1
            states.add(successor)
            if action == "commit" and not state.accepted:
                commit_counterexamples.append(list(new_trace))
            provenance_valid = (
                state.phase == "idle"
                and state.last_commit_accepted
                and state.candidate == state.committed_candidate
            )
            if action == "emit" and not provenance_valid:
                output_counterexamples.append(list(new_trace))
            if action == "restore" and successor.committed != state.committed:
                rollback_counterexamples.append(list(new_trace))
            key = (successor, len(new_trace))
            if key not in seen:
                seen.add(key)
                queue.append((successor, new_trace))
    return {
        "guarded": guarded,
        "depth": depth,
        "reachable_states": len(states),
        "explored_transitions": traces,
        "premature_commit_counterexamples": commit_counterexamples[:5],
        "output_escape_counterexamples": output_counterexamples[:5],
        "rollback_noninterference_counterexamples": rollback_counterexamples[:5],
    }


def verdict_exhaustion() -> dict[str, object]:
    counts: Counter[str] = Counter()
    combinations = 0
    for coverage, eligible, *signal_values in itertools.product((False, True), repeat=7):
        combinations += 1
        if not coverage:
            verdict = "UNSUPPORTED"
        elif not eligible:
            verdict = "INVALID"
        elif any(signal_values):
            verdict = "DETECTED"
        else:
            verdict = "INVARIANT"
        counts[verdict] += 1
    return {
        "boolean_combinations": combinations,
        "verdict_counts": dict(sorted(counts.items())),
        "exclusive_and_total": sum(counts.values()) == combinations,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--depth", type=int, default=8)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite existing output: {args.output}")
    payload = {
        "schema_version": "M2026-003-R3-BOUNDED-MODEL-1.0",
        "scope": "finite-state exploration only; not an unbounded proof",
        "verdict_model": verdict_exhaustion(),
        "guarded_transaction_model": explore(guarded=True, depth=args.depth),
        "unguarded_transaction_model": explore(guarded=False, depth=args.depth),
    }
    guarded = payload["guarded_transaction_model"]
    unguarded = payload["unguarded_transaction_model"]
    payload["checks_pass"] = (
        payload["verdict_model"]["exclusive_and_total"]
        and not guarded["premature_commit_counterexamples"]
        and not guarded["output_escape_counterexamples"]
        and not guarded["rollback_noninterference_counterexamples"]
        and bool(unguarded["premature_commit_counterexamples"])
        and bool(unguarded["output_escape_counterexamples"])
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["checks_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
