from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parent
CURRENT_WORKSPACE = ROOT / "workspace"
HISTORICAL_L1_MP = ROOT / "historical_l1_mp"
THREAD_ENV = {
    "OMP_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "PYTHONHASHSEED": "0",
    "PYTHONDONTWRITEBYTECODE": "1",
}
ABAQUS_NAMES = {"standard", "pre", "smasimutility", "abqcaek"}
COMSOL_NAMES = {"comsol", "comsolbatch"}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_matrix() -> list[dict[str, str]]:
    with (ROOT / "CR_D3_case_matrix.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != 59 or len({row["job_id"] for row in rows}) != 59:
        raise RuntimeError("clean matrix must contain 59 unique jobs")
    historical = [row for row in rows if row["source_profile"] == "historical_l1_mp"]
    if len(historical) != 1 or historical[0]["job_id"] != "CR-L1-MP":
        raise RuntimeError("only CR-L1-MP may use the historical source profile")
    if any(row["source_profile"] not in {"current", "historical_l1_mp"} for row in rows):
        raise RuntimeError("unknown source profile")
    return rows


def _verify_manifest_files(manifest: dict[str, Any]) -> list[tuple[str, str]]:
    records = []
    for item in manifest["files"]:
        path = ROOT / item["path"]
        actual = sha256_file(path)
        if actual != item["sha256"] or path.stat().st_size != item["bytes"]:
            raise RuntimeError(f"source snapshot mismatch: {item['path']}")
        records.append((item["path"], actual))
    return records


def _historical_implementation_hash() -> str:
    digest = hashlib.sha256()
    paths = sorted((HISTORICAL_L1_MP / "src").glob("*.py")) + [HISTORICAL_L1_MP / "run_l1_mp.py"]
    for path in paths:
        digest.update(path.relative_to(HISTORICAL_L1_MP).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def verify_source_snapshots() -> dict[str, Any]:
    current = read_json(ROOT / "CR_D3_current_source_snapshot_manifest.json")
    current_records = _verify_manifest_files(current)
    current_aggregate = hashlib.sha256("\n".join(f"{path}|{digest}" for path, digest in current_records).encode("utf-8")).hexdigest()
    if current_aggregate != current["source_aggregate_sha256"]:
        raise RuntimeError("current source aggregate mismatch")

    historical = read_json(ROOT / "CR_D3_historical_l1_mp_source_manifest.json")
    historical_records = _verify_manifest_files(historical)
    historical_aggregate = hashlib.sha256("\n".join(
        f"{item['source_relative_path']}|{digest}"
        for item, (_, digest) in zip(historical["files"], historical_records)
    ).encode("utf-8")).hexdigest()
    if historical_aggregate != historical["source_aggregate_sha256"]:
        raise RuntimeError("historical source aggregate mismatch")
    implementation_hash = _historical_implementation_hash()
    if implementation_hash != historical["implementation_hash"]:
        raise RuntimeError("historical implementation hash mismatch")
    return {
        "current": {"file_count": len(current_records), "aggregate_sha256": current_aggregate},
        "historical_l1_mp": {"file_count": len(historical_records), "aggregate_sha256": historical_aggregate, "implementation_hash": implementation_hash},
    }


def active_forbidden_processes() -> list[str]:
    if os.name != "nt":
        return []
    completed = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    found = []
    for row in csv.reader(completed.stdout.splitlines()):
        if not row:
            continue
        name = Path(row[0]).stem.lower()
        if name in ABAQUS_NAMES or name in COMSOL_NAMES:
            found.append(row[0])
    return sorted(found)


def _specific_environment(layer: str) -> dict[str, str]:
    mapping = {
        "L2-D1": {"L2_D1_EXECUTION_APPROVED": "YES"},
        "L2-D2": {"L2_D2_EXECUTION_AUTHORIZED": "YES"},
        "L2-D3": {"L2_D3_EXECUTION_AUTHORIZED": "YES"},
        "L2-D3b": {"L2_D3B_EXECUTION_AUTHORIZED": "YES"},
        "L2-D4": {"L2_D4_EXECUTION_AUTHORIZED": "YES"},
        "L2-D5": {"L2_D5_EXECUTION_AUTHORIZED": "YES"},
        "L2-D6": {"L2_D6_EXECUTION_AUTHORIZED": "YES"},
        "L3": {"L3_D1_EXECUTION_AUTHORIZED": "YES", "L3_D1_THREADS": "1"},
        "L4": {"L4_D1_EXECUTION_AUTHORIZED": "YES", "L4_D1_THREADS": "1"},
        "L5": {"L5_D2_EXECUTION_AUTHORIZED": "YES", "L5_D2_THREADS": "1"},
        "L6": {"L6_D1_EXECUTION_AUTHORIZED": "YES", "L6_D1_THREADS": "1"},
        "PERF": {"PERF_D1_WORKER_AUTHORIZED": "YES"},
    }
    return mapping.get(layer, {})


def build_command(row: dict[str, str]) -> tuple[list[str], Path, dict[str, str]]:
    if row["source_profile"] == "historical_l1_mp":
        script = HISTORICAL_L1_MP / Path(row["runner"]).name
        python_root = HISTORICAL_L1_MP
    else:
        script = CURRENT_WORKSPACE / row["runner"]
        python_root = CURRENT_WORKSPACE
    env = os.environ.copy()
    env.update(THREAD_ENV)
    env.update(_specific_environment(row["layer"]))
    env["PYTHONPATH"] = str(python_root)
    output_root = ROOT / row["output_root_relative"] if row["output_root_relative"] else None
    output_dir = ROOT / row["output_dir_relative"]
    command = [sys.executable, str(script)]
    layer = row["layer"]
    if layer == "L0":
        command.extend(["--output-dir", str(output_dir)])
    elif layer in {"L1-MP", "L1-E1"}:
        command.extend(["--output-dir", str(output_dir)])
    elif layer == "L2-D1":
        command.extend(["--authorized-run", "--authorization-token", "L2-D1-MINIMAL-5-CASES", "--output-dir", str(output_dir), "--run-id", row["run_id"]])
    elif layer in {"L2-D2", "L2-D3", "L2-D3b", "L2-D4", "L2-D5", "L2-D6", "L3", "L4", "L5"}:
        command.extend(["--case-id", row["case_id"], "--run-id", row["run_id"], "--execute-authorized", "--output-root", str(output_root)])
    elif layer == "L6":
        command.extend(["--case-id", row["case_id"], "--run-id", row["run_id"], "--execute-authorized"])
    elif layer == "PERF":
        raise RuntimeError("PERF uses the dedicated multi-process path")
    else:
        raise RuntimeError(f"unknown layer: {layer}")
    return command, script.parent, env


def run_process(command: list[str], cwd: Path, env: dict[str, str], log_prefix: Path, timeout: int = 1200) -> None:
    completed = subprocess.run(command, cwd=str(cwd), env=env, capture_output=True, text=True, timeout=timeout, check=False)
    log_prefix.parent.mkdir(parents=True, exist_ok=True)
    (log_prefix.with_suffix(".stdout.txt")).write_text(completed.stdout, encoding="utf-8")
    (log_prefix.with_suffix(".stderr.txt")).write_text(completed.stderr, encoding="utf-8")
    if completed.returncode != 0:
        raise RuntimeError(f"command failed with {completed.returncode}: {' '.join(command)}")


def compare_exact(job_id: str, output_dir: Path, expected: dict[str, Any]) -> dict[str, Any]:
    actual = {}
    for name, digest in expected["files"].items():
        path = output_dir / name
        actual[name] = sha256_file(path)
        if actual[name] != digest:
            raise RuntimeError(f"exact output mismatch: {job_id}/{name}")
    return {"comparison": "exact_files", "file_count": len(actual), "all_match": True, "actual_sha256": actual}


def _all_finite(value: Any) -> bool:
    if value is None or isinstance(value, bool):
        return True
    if isinstance(value, (int, float)):
        return math.isfinite(float(value)) and abs(float(value)) <= 1.0e100
    if isinstance(value, dict):
        return all(_all_finite(item) for item in value.values())
    if isinstance(value, list):
        return all(_all_finite(item) for item in value)
    return True


def run_performance(row: dict[str, str], expected: dict[str, Any], log_root: Path) -> dict[str, Any]:
    script = CURRENT_WORKSPACE / row["runner"]
    cwd = script.parent
    env = os.environ.copy(); env.update(THREAD_ENV); env.update(_specific_environment("PERF")); env["PYTHONPATH"] = str(CURRENT_WORKSPACE)
    case_root = ROOT / row["output_root_relative"]
    if case_root.exists():
        raise FileExistsError(case_root)
    for warmup in range(1, 3):
        command = [sys.executable, str(script), "--case-id", row["case_id"], "--run-id", f"warmup_{warmup}", "--phase", "warmup", "--worker-authorized"]
        run_process(command, cwd, env, log_root / f"{row['job_id']}_warmup_{warmup}")
    results = []
    for repetition in range(1, 11):
        run_id = f"run_{repetition:02d}"
        output = case_root / run_id
        command = [sys.executable, str(script), "--case-id", row["case_id"], "--run-id", run_id, "--phase", "formal", "--worker-authorized", "--output-dir", str(output)]
        run_process(command, cwd, env, log_root / f"{row['job_id']}_{run_id}")
        result = read_json(output / "performance_result.json")
        manifest = read_json(output / "case_manifest.json")
        for name, digest in manifest["outputs"].items():
            if sha256_file(output / name) != digest:
                raise RuntimeError(f"performance manifest mismatch: {row['job_id']}/{run_id}/{name}")
        if not (result["pass_flag"] and result["all_values_finite"] and _all_finite(result)):
            raise RuntimeError(f"invalid performance result: {row['job_id']}/{run_id}")
        if result["accepted_output_fingerprint"] != expected["accepted_output_fingerprint"]:
            raise RuntimeError(f"performance output mismatch: {row['job_id']}/{run_id}")
        results.append(result)
    return {
        "comparison": "accepted_output_fingerprint",
        "warmups": 2,
        "formal_repetitions": len(results),
        "all_match": True,
        "accepted_output_fingerprint": expected["accepted_output_fingerprint"],
        "wall_time_ns": [item["wall_time_ns"] for item in results],
        "cpu_time_ns": [item["cpu_time_ns"] for item in results],
    }


def run_clean() -> dict[str, Any]:
    if (ROOT / "outputs").exists() or (ROOT / "logs").exists() or (ROOT / "final").exists():
        raise RuntimeError("clean output, log or final directory already exists")
    generated_roots = [
        CURRENT_WORKSPACE / "benchmarks" / "L4_two_phase_displacement" / "results" / "L4_D1_two_phase_displacement",
        CURRENT_WORKSPACE / "benchmarks" / "L6_external_host" / "results",
    ]
    if any(path.exists() for path in generated_roots):
        raise RuntimeError("clean canonical dependency/result root already exists")
    forbidden = active_forbidden_processes()
    if forbidden:
        raise RuntimeError(f"forbidden solver processes: {forbidden}")
    sources = verify_source_snapshots()
    expected_all = read_json(ROOT / "CR_D3_expected_reference_manifest.json")["jobs"]
    rows = load_matrix()
    logs = ROOT / "logs"
    ledger = []
    for index, row in enumerate(rows, start=1):
        expected = expected_all[row["job_id"]]
        if row["layer"] == "PERF":
            comparison = run_performance(row, expected, logs)
        else:
            command, cwd, env = build_command(row)
            run_process(command, cwd, env, logs / row["job_id"])
            comparison = compare_exact(row["job_id"], ROOT / row["output_dir_relative"], expected)
        ledger.append({"ordinal": index, "job_id": row["job_id"], "layer": row["layer"], "case_id": row["case_id"], "status": "PASS", **comparison})
        (ROOT / "clean_progress.json").write_text(json.dumps({"completed": index, "total": len(rows), "last_job": row["job_id"], "status": "RUNNING"}, indent=2) + "\n", encoding="utf-8")
        print(f"completed clean job {index}/{len(rows)}: {row['job_id']}", flush=True)
    forbidden_after = active_forbidden_processes()
    if forbidden_after:
        raise RuntimeError(f"forbidden solver processes after run: {forbidden_after}")
    final = ROOT / "final"; final.mkdir()
    summary = {"schema_version": "CR-D1-FINAL-1.0", "design_version": "CR-D3.0", "status": "PASS_CLEAN_RERUN", "job_count": len(ledger), "all_jobs_passed": True, "exact_jobs": sum(item["comparison"] == "exact_files" for item in ledger), "performance_jobs": sum(item["comparison"] == "accepted_output_fingerprint" for item in ledger), "source_snapshots": sources, "abaqus_used": False, "comsol_used": False, "production_model_used": False}
    write_json(final / "clean_rerun_summary.json", summary)
    write_json(final / "clean_rerun_ledger.json", ledger)
    files = []
    for path in sorted((ROOT / "outputs").rglob("*")):
        if path.is_file(): files.append({"path": path.relative_to(ROOT).as_posix(), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    for generated_root in [
        CURRENT_WORKSPACE / "benchmarks" / "L4_two_phase_displacement" / "results" / "L4_D1_two_phase_displacement",
        CURRENT_WORKSPACE / "benchmarks" / "L6_external_host" / "results",
    ]:
        for path in sorted(generated_root.rglob("*")):
            if path.is_file(): files.append({"path": path.relative_to(ROOT).as_posix(), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    write_json(final / "clean_rerun_execution_manifest.json", {"schema_version": "CR-D1-MANIFEST-1.0", "output_file_count": len(files), "output_files": files, "summary_sha256": sha256_file(final / "clean_rerun_summary.json"), "ledger_sha256": sha256_file(final / "clean_rerun_ledger.json"), "manifest_self_hash_embedded": False})
    write_json(ROOT / "clean_progress.json", {"completed": len(rows), "total": len(rows), "last_job": rows[-1]["job_id"], "status": "PASS"})
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute-authorized", action="store_true")
    args = parser.parse_args()
    if not args.execute_authorized or os.environ.get("CR_D3_EXECUTION_AUTHORIZED") != "YES":
        parser.error("CR-D3 execution is not authorized")
    try:
        summary = run_clean()
    except Exception as error:
        failure = ROOT / "clean_failure.json"
        if not failure.exists():
            write_json(failure, {"status": "FAIL", "error_type": type(error).__name__, "error": str(error)})
        raise
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
