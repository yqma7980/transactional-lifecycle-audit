from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import sys
from pathlib import Path
from typing import Any, Callable

from l0_model import VARIANTS, ScalarEvaluator, fingerprint


ROOT = Path(__file__).resolve().parent
SCHEMA_VERSION = "1.0"
BENCHMARK_VERSION = "L0-1.0"


def run_history(
    variant: str,
    history_id: str,
    scenario: str,
    operations: list[tuple[str, float | None, str]],
    committed_c: float,
    alpha: float,
) -> dict[str, Any]:
    evaluator = VARIANTS[variant](committed_c=committed_c, alpha=alpha)
    replay_residual: float | None = None
    for event, x_trial, candidate_id in operations:
        if event == "reject":
            evaluator.reject(candidate_id)
            continue
        if x_trial is None:
            raise ValueError(f"{event} requires x_trial")
        residual = evaluator.evaluate(x_trial, event=event, candidate_id=candidate_id)
        if event == "replay":
            replay_residual = residual
    if replay_residual is None:
        raise RuntimeError(f"history {history_id} has no replay event")
    declared = {
        "x_trial": committed_c,
        "committed_c": committed_c,
        "alpha": alpha,
        "scenario": scenario,
    }
    return {
        "variant": variant,
        "history_id": history_id,
        "scenario": scenario,
        "replay_residual": replay_residual,
        "declared_state_fingerprint": fingerprint(declared),
        "committed_state_fingerprint": fingerprint(evaluator.committed_state()),
        "persistent_state_fingerprint": fingerprint(evaluator.persistent_state()),
        "records": [record.to_dict() for record in evaluator.records],
    }


def scenario_discarded_trial(variant: str, c: float, alpha: float) -> tuple[dict[str, Any], dict[str, Any]]:
    h1 = run_history(
        variant,
        "H1_rejected_trial",
        "discarded_trial_replay",
        [("trial", 2.0, "a1"), ("reject", None, "a1"), ("replay", c, "q")],
        c,
        alpha,
    )
    h2 = run_history(
        variant,
        "H2_control",
        "discarded_trial_replay",
        [("replay", c, "q")],
        c,
        alpha,
    )
    return h1, h2


def scenario_call_order(variant: str, c: float, alpha: float) -> tuple[dict[str, Any], dict[str, Any]]:
    h1 = run_history(
        variant,
        "H1_order_2_then_3",
        "call_order_permutation",
        [
            ("trial", 2.0, "a1"),
            ("reject", None, "a1"),
            ("trial", 3.0, "a2"),
            ("reject", None, "a2"),
            ("replay", c, "q"),
        ],
        c,
        alpha,
    )
    h2 = run_history(
        variant,
        "H2_order_3_then_2",
        "call_order_permutation",
        [
            ("trial", 3.0, "a1"),
            ("reject", None, "a1"),
            ("trial", 2.0, "a2"),
            ("reject", None, "a2"),
            ("replay", c, "q"),
        ],
        c,
        alpha,
    )
    return h1, h2


def scenario_terminal_call(variant: str, c: float, alpha: float) -> tuple[dict[str, Any], dict[str, Any]]:
    h1 = run_history(
        variant,
        "H1_terminal_inserted",
        "terminal_call_noninterference",
        [("terminal", 4.0, "terminal"), ("replay", c, "q")],
        c,
        alpha,
    )
    h2 = run_history(
        variant,
        "H2_no_terminal",
        "terminal_call_noninterference",
        [("replay", c, "q")],
        c,
        alpha,
    )
    return h1, h2


SCENARIOS: dict[str, Callable[[str, float, float], tuple[dict[str, Any], dict[str, Any]]]] = {
    "discarded_trial_replay": scenario_discarded_trial,
    "call_order_permutation": scenario_call_order,
    "terminal_call_noninterference": scenario_terminal_call,
}


def load_expected(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def execute_benchmark(expected_path: Path | None = None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    expected_path = expected_path or ROOT / "expected_results.json"
    expected = load_expected(expected_path)
    c = float(expected["parameters"]["committed_c"])
    alpha = float(expected["parameters"]["alpha"])
    tolerance = float(expected["tolerance"])
    outcomes: list[dict[str, Any]] = []
    ledger: list[dict[str, Any]] = []

    for scenario_name, scenario_fn in SCENARIOS.items():
        for variant in VARIANTS:
            h1, h2 = scenario_fn(variant, c, alpha)
            if h1["declared_state_fingerprint"] != h2["declared_state_fingerprint"]:
                raise AssertionError("compared replay states are not declared-equal")
            delta = h1["replay_residual"] - h2["replay_residual"]
            expected_delta = float(expected["expected_delta"][scenario_name][variant])
            passed = math.isfinite(delta) and abs(delta - expected_delta) <= tolerance
            outcomes.append(
                {
                    "scenario": scenario_name,
                    "variant": variant,
                    "history_1": h1["history_id"],
                    "history_2": h2["history_id"],
                    "replay_residual_h1": h1["replay_residual"],
                    "replay_residual_h2": h2["replay_residual"],
                    "delta_residual": delta,
                    "expected_delta": expected_delta,
                    "declared_state_equal": True,
                    "finite": math.isfinite(delta),
                    "passed": passed,
                }
            )
            for history in (h1, h2):
                for record in history["records"]:
                    ledger.append(
                        {
                            "scenario": scenario_name,
                            "history_id": history["history_id"],
                            "declared_state_fingerprint": history["declared_state_fingerprint"],
                            **record,
                        }
                    )

    summary = {
        "schema_version": SCHEMA_VERSION,
        "benchmark_version": BENCHMARK_VERSION,
        "parameters": {"committed_c": c, "alpha": alpha},
        "tolerance": tolerance,
        "overall_pass": all(item["passed"] for item in outcomes),
        "outcomes": outcomes,
        "interpretation": {
            "unsafe_seed_detected": all(
                item["passed"] and item["delta_residual"] != 0.0
                for item in outcomes
                if item["variant"] == "unsafe_persistent"
            ),
            "safe_local_replay_invariant": all(
                item["passed"] and item["delta_residual"] == 0.0
                for item in outcomes
                if item["variant"] == "safe_local"
            ),
            "safe_transactional_replay_invariant": all(
                item["passed"] and item["delta_residual"] == 0.0
                for item in outcomes
                if item["variant"] == "safe_transactional"
            ),
        },
    }
    return summary, ledger


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def write_outputs(output_dir: Path, summary: dict[str, Any], ledger: list[dict[str, Any]]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "l0_summary.json"
    ledger_path = output_dir / "l0_call_ledger.csv"
    manifest_path = output_dir / "l0_manifest.json"

    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    fieldnames = list(ledger[0].keys())
    with ledger_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(ledger)

    source_files = [
        ROOT / "l0_model.py",
        ROOT / "run_benchmark.py",
        ROOT / "expected_results.json",
        ROOT / "README.md",
        ROOT / "benchmark_spec.md",
        ROOT / "tests" / "test_l0.py",
    ]
    manifest = {
        "benchmark_version": BENCHMARK_VERSION,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "source_sha256": {str(path.relative_to(ROOT)): sha256(path) for path in source_files},
        "result_sha256": {
            summary_path.name: sha256(summary_path),
            ledger_path.name: sha256(ledger_path),
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the L0 scalar lifecycle replay benchmark")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results")
    parser.add_argument("--expected", type=Path, default=ROOT / "expected_results.json")
    args = parser.parse_args()
    summary, ledger = execute_benchmark(args.expected)
    write_outputs(args.output_dir, summary, ledger)
    print(
        json.dumps(
            {
                "benchmark_version": summary["benchmark_version"],
                "overall_pass": summary["overall_pass"],
                "outcome_count": len(summary["outcomes"]),
                "ledger_rows": len(ledger),
                "output_dir": str(args.output_dir.resolve()),
            },
            sort_keys=True,
        )
    )
    return 0 if summary["overall_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
