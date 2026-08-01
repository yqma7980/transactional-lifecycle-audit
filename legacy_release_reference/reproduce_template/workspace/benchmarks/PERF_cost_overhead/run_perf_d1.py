from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


THREAD_ENV = {
    "OMP_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "PYTHONHASHSEED": "0",
    "PYTHONDONTWRITEBYTECODE": "1",
}


def read_matrix(root: Path) -> list[dict[str, str]]:
    with (root / "PERF_D0_case_matrix.csv").open(
        "r", encoding="utf-8", newline=""
    ) as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != 45 or len({row["case_id"] for row in rows}) != 45:
        raise RuntimeError("frozen case matrix is not 45 unique cells")
    return rows


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def run_child(
    root: Path,
    *,
    row: dict[str, str],
    run_id: str,
    phase: str,
    output_dir: Path | None,
) -> dict[str, Any]:
    env = os.environ.copy()
    env.update(THREAD_ENV)
    env["PERF_D1_WORKER_AUTHORIZED"] = "YES"
    command = [
        sys.executable,
        str(root / "run_perf_worker.py"),
        "--case-id",
        row["case_id"],
        "--run-id",
        run_id,
        "--phase",
        phase,
        "--worker-authorized",
    ]
    if output_dir is not None:
        command.extend(["--output-dir", str(output_dir)])
    completed = subprocess.run(
        command,
        cwd=str(root),
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"worker failed for {row['case_id']} {run_id}: "
            f"{completed.stdout}\n{completed.stderr}"
        )
    return json.loads(completed.stdout.strip().splitlines()[-1])


def groups(rows: list[dict[str, str]]) -> list[list[dict[str, str]]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in rows:
        grouped.setdefault((row["family"], row["size"]), []).append(row)
    ordered: list[list[dict[str, str]]] = []
    for key in sorted(grouped):
        ordered.append(sorted(grouped[key], key=lambda item: item["config_id"]))
    return ordered


def verify_group_fingerprints(receipts: list[dict[str, Any]]) -> str:
    fingerprints = {item["accepted_output_fingerprint"] for item in receipts}
    if len(fingerprints) != 1:
        raise RuntimeError(f"output-equivalence hard gate failed: {receipts}")
    return next(iter(fingerprints))


def run_preflight(root: Path, rows: list[dict[str, str]]) -> None:
    preflight_root = root / "preflight" / "PERF_D1_all_cells"
    if preflight_root.exists():
        raise FileExistsError(preflight_root)
    receipts: list[dict[str, Any]] = []
    for row in rows:
        output_dir = preflight_root / row["case_id"] / "preflight_1"
        receipts.append(
            run_child(
                root,
                row=row,
                run_id="preflight_1",
                phase="preflight",
                output_dir=output_dir,
            )
        )
    equivalence: list[dict[str, Any]] = []
    for group in groups(rows):
        selected = [
            receipt
            for receipt in receipts
            if receipt["case_id"] in {row["case_id"] for row in group}
        ]
        fingerprint = verify_group_fingerprints(selected)
        equivalence.append(
            {
                "family": group[0]["family"],
                "size": group[0]["size"],
                "accepted_output_fingerprint": fingerprint,
                "config_count": len(selected),
            }
        )
    summary = {
        "schema_version": "PERF-D1-PREFLIGHT-1.0",
        "design_version": "PERF-D1.0",
        "status": "PASS",
        "cell_count": len(receipts),
        "all_cells_passed": all(item["pass_flag"] for item in receipts),
        "all_output_equivalence_gates_passed": True,
        "equivalence": equivalence,
        "no_formal_execution": True,
    }
    write_json(preflight_root / "preflight_summary.json", summary)
    manifest = {
        "schema_version": "PERF-D1-PREFLIGHT-MANIFEST-1.0",
        "summary_sha256": hashlib.sha256(
            (preflight_root / "preflight_summary.json").read_bytes()
        ).hexdigest(),
        "manifest_self_hash_embedded": False,
    }
    write_json(preflight_root / "preflight_manifest.json", manifest)


def run_formal(root: Path, rows: list[dict[str, str]]) -> None:
    preflight_summary = (
        root / "preflight" / "PERF_D1_all_cells" / "preflight_summary.json"
    )
    if not preflight_summary.exists():
        raise RuntimeError("formal execution requires completed preflight")
    preflight = json.loads(preflight_summary.read_text(encoding="utf-8"))
    if not (
        preflight["status"] == "PASS"
        and preflight["all_output_equivalence_gates_passed"]
    ):
        raise RuntimeError("preflight gate is not PASS")

    result_root = root / "results" / "PERF_D1_cost_overhead"
    if result_root.exists():
        raise FileExistsError(result_root)
    result_root.mkdir(parents=True)

    warmups: list[dict[str, Any]] = []
    for warmup_id in (1, 2):
        for row in rows:
            warmups.append(
                run_child(
                    root,
                    row=row,
                    run_id=f"warmup_{warmup_id}",
                    phase="warmup",
                    output_dir=None,
                )
            )
    write_json(
        result_root / "warmup_receipts.json",
        {
            "schema_version": "PERF-D1-WARMUP-1.0",
            "count": len(warmups),
            "excluded_from_statistics": True,
            "all_passed": all(item["pass_flag"] for item in warmups),
            "receipts": warmups,
        },
    )

    formal_receipts: list[dict[str, Any]] = []
    run_groups = groups(rows)
    for repetition in range(1, 11):
        for group in run_groups:
            offset = (repetition - 1) % len(group)
            rotated = group[offset:] + group[:offset]
            block: list[dict[str, Any]] = []
            for row in rotated:
                run_id = f"run_{repetition:02d}"
                receipt = run_child(
                    root,
                    row=row,
                    run_id=run_id,
                    phase="formal",
                    output_dir=result_root / row["case_id"] / run_id,
                )
                block.append(receipt)
                formal_receipts.append(receipt)
            verify_group_fingerprints(block)
        print(f"completed formal repetition {repetition}/10", flush=True)

    write_json(
        result_root / "formal_execution_receipts.json",
        {
            "schema_version": "PERF-D1-FORMAL-RECEIPTS-1.0",
            "count": len(formal_receipts),
            "all_passed": all(item["pass_flag"] for item in formal_receipts),
            "receipts": formal_receipts,
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("preflight", "formal"), required=True)
    parser.add_argument("--execute-authorized", action="store_true")
    args = parser.parse_args()
    if (
        not args.execute_authorized
        or os.environ.get("PERF_D1_EXECUTION_AUTHORIZED") != "YES"
    ):
        parser.error("PERF-D1 execution is not authorized")

    root = Path(__file__).resolve().parent
    rows = read_matrix(root)
    if args.phase == "preflight":
        run_preflight(root, rows)
    else:
        run_formal(root, rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())