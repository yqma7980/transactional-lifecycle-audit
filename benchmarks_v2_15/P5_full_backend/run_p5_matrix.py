from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
WORKING = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))

from p5_backend_contracts import IMAGE, SCALED_CASES, matrix_authorized, require_single_thread_environment, verify_protected_evidence


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="P5 guarded 90-process formal matrix runner")
    parser.add_argument("--execution-tag", required=True)
    parser.add_argument("--execute-matrix-authorized", action="store_true")
    return parser.parse_args(argv)


def _container_path(path: Path) -> str:
    return "/working/" + path.resolve().relative_to(WORKING.resolve()).as_posix()


def _run_case(results_root: Path, case_id: str, run_id: str, thresholds: Path | None = None, selection: Path | None = None) -> None:
    command = [
        "docker", "run", "--rm", "--network", "none", "--platform", "linux/amd64",
        "-e", "OMP_NUM_THREADS=1", "-e", "OPENBLAS_NUM_THREADS=1", "-e", "MKL_NUM_THREADS=1",
        "-e", "PYTHONDONTWRITEBYTECODE=1", "-e", "P5_EXECUTION_AUTHORIZED=YES",
        "-v", f"{WORKING.resolve()}:/working:rw", "-w", _container_path(ROOT), IMAGE,
        "python3", "run_p5.py", "--case-id", case_id, "--run-id", run_id,
        "--results-root", _container_path(results_root), "--execute-authorized",
    ]
    if thresholds is not None:
        command.extend(["--thresholds-file", _container_path(thresholds)])
    if selection is not None:
        command.extend(["--selection-file", _container_path(selection)])
    completed = subprocess.run(command, check=False, text=True, capture_output=True)
    log_path = results_root / "process_logs" / case_id / f"{run_id}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(completed.stdout + completed.stderr, encoding="utf-8")
    if completed.returncode != 0:
        raise RuntimeError(f"P5 process failed: {case_id}/{run_id}; see {log_path}")


def main(argv=None) -> int:
    args = parse_args(argv)
    if not matrix_authorized(args.execute_matrix_authorized):
        raise SystemExit("P5 matrix execution requires both matrix authorization locks")
    require_single_thread_environment()
    verify_protected_evidence()
    if not re.fullmatch(r"P5_formal_[0-9]{8}_[A-Za-z0-9._-]+", args.execution_tag):
        raise SystemExit("execution tag must match P5_formal_YYYYMMDD_label")
    inspected = subprocess.run(["docker", "image", "inspect", IMAGE], check=False, capture_output=True, text=True)
    if inspected.returncode != 0:
        raise SystemExit("frozen DOLFINx image is unavailable")

    results_root = ROOT / "results" / args.execution_tag
    if results_root.exists():
        raise SystemExit(f"refusing to overwrite execution tag: {results_root}")
    results_root.mkdir(parents=True, exist_ok=False)
    final_root = results_root / "final"
    final_root.mkdir()

    from p5_scheduler import (
        build_execution_manifest,
        calibrate_null_envelope,
        confirm_null_envelope,
        select_scaled_strengths,
        verify_scaled_repetitions,
    )

    for case_id in ("P5-NULL-EXACT-CAL-01", "P5-NULL-ARITH-CAL-01"):
        for number in range(1, 7):
            _run_case(results_root, case_id, f"run_{number}")
    null_payload = calibrate_null_envelope(results_root, final_root)
    threshold_path = final_root / "null_envelope.json"

    for number in (1, 2):
        _run_case(results_root, "P5-NULL-ARITH-CONF-01", f"run_{number}", thresholds=threshold_path)
    confirmation = confirm_null_envelope(results_root, null_payload)
    (final_root / "null_confirmation.json").write_text(json.dumps(confirmation, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    for case_id in SCALED_CASES:
        for number in range(1, 16):
            _run_case(results_root, case_id, f"run_{number}", thresholds=threshold_path)
    selections = select_scaled_strengths(results_root, final_root)
    selection_path = final_root / "selected_strengths.json"

    for case_id in SCALED_CASES:
        family = SCALED_CASES[case_id]
        if selections["families"][family]["status"] != "SELECTED_PENDING_FRESH_VERIFICATION":
            continue
        for number in range(16, 20):
            _run_case(results_root, case_id, f"run_{number}", thresholds=threshold_path, selection=selection_path)
    duplicate = verify_scaled_repetitions(results_root, selections, final_root)
    manifest = build_execution_manifest(results_root, final_root)
    summary = {
        "null_calibration": null_payload["status"],
        "null_confirmation": confirmation["status"],
        "scaled_verification": duplicate["status"],
        "formal_process_count": 90,
        "manifest_file_count": len(manifest["files"]),
    }
    (final_root / "matrix_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, sort_keys=True))
    return 0 if duplicate["status"] == "PASS_FRESH_PROCESS_VERIFICATION" else 3


if __name__ == "__main__":
    raise SystemExit(main())
