"""Explicitly gated runner for the five-case L2-D1 subset."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.l2_cases import authorized_case_ids, execute_case
from src.l2_schema import CASE_RESULT_COLUMNS, CHECKPOINT_COLUMNS, EVENT_COLUMNS
from src.l2_state import DESIGN_VERSION, HOST_VERSION


AUTHORIZATION_TOKEN = "L2-D1-MINIMAL-5-CASES"


def _text(value: Any) -> str:
    if value == "NA":
        return "NA"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return format(value, ".17e")
    return str(value)


def _write_csv(path: Path, columns: tuple[str, ...], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: _text(row.get(column, "NA")) for column in columns})


def _implementation_hash(root: Path) -> str:
    members = [
        root / "L2_D1_execution_freeze.json",
        root / "L2_D1_minimal_case_matrix.csv",
        root / "run_l2_d1.py",
        *sorted((root / "src").glob("*.py")),
        *sorted((root / "oracle").glob("*.py")),
        *sorted((root / "schemas").glob("l2_*.csv")),
    ]
    digest = hashlib.sha256()
    for path in members:
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authorized-run", action="store_true")
    parser.add_argument("--authorization-token", default="")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--run-id", default="L2-D1-FORMAL")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.authorized_run or args.authorization_token != AUTHORIZATION_TOKEN:
        raise SystemExit(
            "Execution refused. A later explicit authorization must provide both "
            "--authorized-run and the frozen minimal-slice token."
        )
    if os.environ.get("L2_D1_EXECUTION_APPROVED") != "YES":
        raise SystemExit(
            "Execution refused. Set L2_D1_EXECUTION_APPROVED=YES only in the "
            "separately authorized execution command."
        )

    output_dir = args.output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise SystemExit(f"Output directory must be new or empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    case_rows: list[dict[str, Any]] = []
    event_rows: list[dict[str, Any]] = []
    checkpoint_rows: list[dict[str, Any]] = []
    for case_id in authorized_case_ids():
        execution = execute_case(ROOT, case_id, args.run_id)
        case_rows.append(execution.result)
        event_rows.extend(execution.events)
        checkpoint_rows.extend(execution.checkpoints)

    _write_csv(output_dir / "l2_case_results.csv", CASE_RESULT_COLUMNS, case_rows)
    _write_csv(output_dir / "l2_event_ledger.csv", EVENT_COLUMNS, event_rows)
    _write_csv(
        output_dir / "l2_accepted_checkpoints.csv",
        CHECKPOINT_COLUMNS,
        checkpoint_rows,
    )
    summary = {
        "design_version": DESIGN_VERSION,
        "host_version": HOST_VERSION,
        "run_id": args.run_id,
        "execution_scope": list(authorized_case_ids()),
        "case_count": len(case_rows),
        "case_pass_count": sum(bool(row["passed"]) for row in case_rows),
        "overall_pass": all(bool(row["passed"]) for row in case_rows),
        "event_rows": len(event_rows),
        "checkpoint_rows": len(checkpoint_rows),
        "implementation_hash": _implementation_hash(ROOT),
        "thread_count": 1,
        "abaqus_used": False,
        "claim_boundary": (
            "Standalone L2-D1 only; formal duplicate-run comparison remains a "
            "separate gate."
        ),
    }
    (output_dir / "l2_run_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0 if summary["overall_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
