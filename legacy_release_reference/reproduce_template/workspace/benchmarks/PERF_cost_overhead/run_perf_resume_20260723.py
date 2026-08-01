from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any

_ROOT = Path(__file__).resolve().parent
_WORKSPACE = _ROOT.parents[1]
if str(_WORKSPACE) not in sys.path:
    sys.path.insert(0, str(_WORKSPACE))

from benchmarks.PERF_cost_overhead.run_perf_d1 import (
    groups, read_matrix, run_child, verify_group_fingerprints, write_json,
)


EXPECTED_PARTIAL_AGGREGATE = "f81efde31290b04953c2025d70339bdff719fdd16ef5c29a8f1c0cd7b79bde7d"
EXPECTED_WARMUP_SHA256 = "102070fba01c200485725b7c9fdbea80f9b4d025626ab394b53212463896a0d6"
EXPECTED_FILES = {"accepted_output.json", "performance_result.json", "case_manifest.json"}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _receipt(result_root: Path, case_id: str, run_id: str) -> dict[str, Any]:
    result = json.loads((result_root / case_id / run_id / "performance_result.json").read_text(encoding="utf-8"))
    return {
        "case_id": result["case_id"],
        "run_id": result["run_id"],
        "phase": result["phase"],
        "accepted_output_fingerprint": result["accepted_output_fingerprint"],
        "pass_flag": result["pass_flag"],
    }


def _verify_run_dir(run_dir: Path, case_id: str, run_id: str) -> dict[str, Any]:
    if {path.name for path in run_dir.iterdir() if path.is_file()} != EXPECTED_FILES:
        raise RuntimeError(f"invalid run directory: {run_dir}")
    manifest = json.loads((run_dir / "case_manifest.json").read_text(encoding="utf-8"))
    for name, digest in manifest["outputs"].items():
        if _sha(run_dir / name) != digest:
            raise RuntimeError(f"manifest mismatch: {run_dir / name}")
    receipt = _receipt(run_dir.parents[1], case_id, run_id)
    if not (receipt["pass_flag"] and receipt["phase"] == "formal" and receipt["case_id"] == case_id and receipt["run_id"] == run_id):
        raise RuntimeError(f"invalid result identity: {run_dir}")
    return receipt


def validate_partial(root: Path) -> tuple[list[dict[str, str]], Path]:
    rows = read_matrix(root)
    result_root = root / "results" / "PERF_D1_cost_overhead"
    warmup = result_root / "warmup_receipts.json"
    if _sha(warmup) != EXPECTED_WARMUP_SHA256:
        raise RuntimeError("warm-up receipt hash changed")
    if (result_root / "formal_execution_receipts.json").exists():
        raise RuntimeError("formal receipt file already exists")
    hashes: list[tuple[str, str]] = []
    for row in rows:
        for repetition in range(1, 10):
            run_id = f"run_{repetition:02d}"
            run_dir = result_root / row["case_id"] / run_id
            _verify_run_dir(run_dir, row["case_id"], run_id)
            for path in sorted(run_dir.iterdir()):
                if path.is_file():
                    hashes.append((path.relative_to(root).as_posix(), _sha(path)))
        if (result_root / row["case_id"] / "run_10").exists():
            raise RuntimeError(f"run_10 already exists: {row['case_id']}")
    aggregate = hashlib.sha256("\n".join(f"{path}|{digest}" for path, digest in sorted(hashes)).encode("utf-8")).hexdigest()
    if len(hashes) != 1215 or aggregate != EXPECTED_PARTIAL_AGGREGATE:
        raise RuntimeError("405-run frozen aggregate changed")
    return rows, result_root


def reconstruct_receipts(root: Path, rows: list[dict[str, str]], result_root: Path) -> list[dict[str, Any]]:
    receipts: list[dict[str, Any]] = []
    run_groups = groups(rows)
    for repetition in range(1, 11):
        for group in run_groups:
            offset = (repetition - 1) % len(group)
            rotated = group[offset:] + group[:offset]
            block = [_verify_run_dir(result_root / row["case_id"] / f"run_{repetition:02d}", row["case_id"], f"run_{repetition:02d}") for row in rotated]
            verify_group_fingerprints(block)
            receipts.extend(block)
    if len(receipts) != 450 or not all(item["pass_flag"] for item in receipts):
        raise RuntimeError("reconstructed receipt ledger failed")
    return receipts


def resume(root: Path) -> None:
    rows, result_root = validate_partial(root)
    repetition = 10
    for group_index, group in enumerate(groups(rows), start=1):
        offset = (repetition - 1) % len(group)
        rotated = group[offset:] + group[:offset]
        block = []
        for row in rotated:
            block.append(run_child(root, row=row, run_id="run_10", phase="formal", output_dir=result_root / row["case_id"] / "run_10"))
        verify_group_fingerprints(block)
        print(f"completed resume group {group_index}/9", flush=True)
    receipts = reconstruct_receipts(root, rows, result_root)
    write_json(result_root / "formal_execution_receipts.json", {
        "schema_version": "PERF-D1-FORMAL-RECEIPTS-1.0",
        "count": len(receipts),
        "all_passed": all(item["pass_flag"] for item in receipts),
        "receipts": receipts,
        "resume_revision": "PERF-D1-R1.0",
        "original_runner_completed_repetitions": 9,
        "resumed_repetition": 10,
    })


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute-authorized", action="store_true")
    args = parser.parse_args()
    if not args.execute_authorized or os.environ.get("PERF_D1_RESUME_AUTHORIZED") != "YES":
        parser.error("PERF-D1 resume is not authorized")
    resume(Path(__file__).resolve().parent)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
