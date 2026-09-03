from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent


def _run_one(
    config_path: Path,
    spec: dict[str, Any],
    run_index: int,
    mode: str,
    output_root: Path,
) -> dict[str, Any]:
    run_id = f"{mode}-{run_index:02d}"
    destination = output_root / "runs" / mode / spec["case_id"] / run_id
    environment = os.environ.copy()
    environment.update({"PYTHONHASHSEED": "0", "PYTHONDONTWRITEBYTECODE": "1"})
    process = subprocess.run(
        [
            sys.executable,
            str(ROOT / "run_case.py"),
            "--config",
            str(config_path),
            "--case-id",
            spec["case_id"],
            "--run-id",
            run_id,
            "--mode",
            mode,
            "--output",
            str(destination),
        ],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if process.returncode:
        raise RuntimeError(
            f"case failed: {spec['case_id']} {run_id}\nstdout={process.stdout}\nstderr={process.stderr}"
        )
    return json.loads((destination / "case_result.json").read_text(encoding="utf-8"))


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = (
        "case_id",
        "label",
        "fault",
        "mode",
        "run_id",
        "expected_verdict",
        "observed_verdict",
        "verdict_match",
        "eligible",
        "database_equal",
        "persistent_equal",
        "output_equal",
        "endpoint_equal",
        "blocked_count",
        "false_block",
        "containment_pass",
        "semantic_sha256",
    )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite existing output: {args.output}")
    args.output.mkdir(parents=True)

    config_path = args.config.resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    cases = {item["case_id"]: item for item in config["cases"]}
    repeats = int(config["fresh_processes_per_case"])
    rows: list[dict[str, Any]] = []
    for case_id in config["case_order"]:
        for run_index in range(1, repeats + 1):
            rows.append(_run_one(config_path, cases[case_id], run_index, "diagnostic", args.output))
    for case_id in config["case_order"]:
        spec = cases[case_id]
        if not spec["containment_eligible"]:
            continue
        for run_index in range(1, repeats + 1):
            rows.append(_run_one(config_path, spec, run_index, "enforce", args.output))

    _write_csv(args.output / "run_results.csv", rows)
    by_mode = Counter(row["mode"] for row in rows)
    by_verdict = Counter(
        row["observed_verdict"] for row in rows if row["mode"] == "diagnostic"
    )
    semantic_groups: dict[str, set[str]] = {}
    for row in rows:
        key = f"{row['mode']}:{row['case_id']}"
        semantic_groups.setdefault(key, set()).add(row["semantic_sha256"])
    reproducible = all(len(values) == 1 for values in semantic_groups.values())
    fault_enforcement = [
        row for row in rows if row["mode"] == "enforce" and row["fault"].startswith("O")
    ]
    benign_enforcement = [
        row for row in rows if row["mode"] == "enforce" and row["fault"] == "NONE"
    ]
    summary = {
        "schema_version": "M2026-003-R3-SQLITE-SUMMARY-1.0",
        "total_fresh_processes": len(rows),
        "processes_by_mode": dict(sorted(by_mode.items())),
        "diagnostic_verdict_processes": dict(sorted(by_verdict.items())),
        "diagnostic_cases": len(config["case_order"]),
        "diagnostic_verdict_matches": sum(
            1 for row in rows if row["mode"] == "diagnostic" and row["verdict_match"]
        ),
        "diagnostic_processes": by_mode["diagnostic"],
        "semantic_groups": len(semantic_groups),
        "semantic_reproducibility_pass": reproducible,
        "enforced_fault_processes": len(fault_enforcement),
        "enforced_faults_blocked_and_contained": sum(
            1
            for row in fault_enforcement
            if row["blocked_count"] > 0 and row["containment_pass"]
        ),
        "benign_enforcement_processes": len(benign_enforcement),
        "benign_false_blocks": sum(1 for row in benign_enforcement if row["false_block"]),
        "all_pass": all(row["verdict_match"] and row["containment_pass"] for row in rows)
        and reproducible,
    }
    (args.output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["all_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

