"""Run two fresh, isolated Python 3.12.10 processes; keep all run artifacts."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from datetime import datetime, timezone
from uuid import uuid4


BASELINE = Path(__file__).resolve().parent
TASK = BASELINE.parents[2]
RELATIVE_BASELINE = BASELINE.relative_to(TASK).as_posix()
PYTHON = Path(r"LOCAL_USER/AppData\Local\Programs\Python\Python312\python.exe")
TIMEOUT_SECONDS = 180
STREAM_LIMIT_BYTES = 16 * 1024 * 1024
SPEC_HASHES = {
    "governance/AUTHORIZED_SCOPE.md": "e3c837de9592e2687c01df79dea2ecdf4fd4e14c0851e6fbb7e15f43f0138e59",
    "contracts/COMPARISON_SEMANTICS.md": "05f799b810e2867b19c7d1ea0a42a2bb4687c1cf864dba2eb08ae9ecaec9c90e",
}
AUTHORED_FILES = ("rich_compare.py", "test_rich_compare.py", "run_synthetic_tests.py", "README.md", "SOURCE_LINEAGE.md")


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json_exclusive(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def lock_inputs():
    locked = {RELATIVE_BASELINE + "/" + name: sha256(BASELINE / name) for name in AUTHORED_FILES}
    locked.update({name: sha256(TASK / name) for name in SPEC_HASHES})
    return locked


def semantic_record(report):
    return {key: report[key] for key in ("schema", "tests_run", "subtests_executed", "test_ids", "failures", "errors", "skipped", "ok", "coverage", "behavior_checks", "behavior")}


def run_trial(run_dir, mode, optimized):
    trial = run_dir / mode
    trial.mkdir(exist_ok=False)
    command = [str(PYTHON), "-I", "-B"]
    if optimized:
        command.append("-O")
    command.append(str(BASELINE / "test_rich_compare.py"))
    record = {
        "mode": mode, "command": command, "cwd": str(BASELINE),
        "timeout_seconds": TIMEOUT_SECONDS, "started_utc": utc_now(),
        "native_target_run": False, "timed_out": False,
    }
    write_json_exclusive(trial / "INVOCATION.json", record)
    start = time.perf_counter()
    report = None
    try:
        with (trial / "stdout.log").open("xb") as stdout, (trial / "stderr.log").open("xb") as stderr:
            flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            process = subprocess.Popen(command, cwd=BASELINE, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr, creationflags=flags)
            record["pid"] = process.pid
            try:
                record["returncode"] = process.wait(timeout=TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired:
                record["timed_out"] = True
                process.kill()
                record["returncode"] = process.wait(timeout=10)
    except Exception as exc:
        record["infrastructure_error"] = {"type": type(exc).__name__, "message": str(exc)}
    record["wall_seconds"] = time.perf_counter() - start
    record["finished_utc"] = utc_now()
    record["logs"] = {}
    for name in ("stdout.log", "stderr.log"):
        path = trial / name
        if path.exists():
            record["logs"][name] = {"sha256": sha256(path), "bytes": path.stat().st_size}
    record["streams_within_16_mib"] = all(item["bytes"] <= STREAM_LIMIT_BYTES for item in record["logs"].values())
    stdout_path = trial / "stdout.log"
    if stdout_path.exists() and record["streams_within_16_mib"]:
        try:
            marker = "SYNTHETIC_REPORT_JSON="
            lines = [line[len(marker):] for line in stdout_path.read_text(encoding="utf-8").splitlines() if line.startswith(marker)]
            if len(lines) != 1:
                raise ValueError("Expected exactly one synthetic report")
            report = json.loads(lines[0])
            write_json_exclusive(trial / "SYNTHETIC_REPORT.json", report)
            record["tests"] = {key: value for key, value in report.items() if key != "behavior"}
            semantics = semantic_record(report)
            encoded = json.dumps(semantics, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
            record["semantic_report_sha256"] = hashlib.sha256(encoded).hexdigest()
        except Exception as exc:
            record["report_error"] = {"type": type(exc).__name__, "message": str(exc)}
    record["passed"] = bool(
        record.get("returncode") == 0 and not record["timed_out"]
        and record["streams_within_16_mib"] and len(record["logs"]) == 2
        and report and report.get("ok") and report.get("failures") == 0
        and report.get("errors") == 0 and report.get("skipped") == 0
        and report.get("python_version") == [3, 12, 10]
        and report.get("optimization") == (1 if optimized else 0)
        and report.get("isolated") == 1 and report.get("dont_write_bytecode") is True
        and report.get("pid") == record.get("pid")
        and report.get("coverage") == {"r79_truth_patterns": 64, "r94_truth_patterns": 32, "r79_eligibility_patterns": 8, "r94_eligibility_patterns": 8}
    )
    write_json_exclusive(trial / "RESULT.json", record)
    return record, report


def main():
    if tuple(sys.version_info[:3]) != (3, 12, 10) or Path(sys.executable).resolve() != PYTHON.resolve():
        raise RuntimeError("Runner requires the specified Python 3.12.10 executable")
    if not sys.dont_write_bytecode:
        raise RuntimeError("Invoke the runner with -B to keep bytecode writes disabled")
    (BASELINE / "runs").mkdir(exist_ok=True)
    run_id = "SYNTHETIC_RICH_R02_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_") + uuid4().hex
    run_dir = BASELINE / "runs" / run_id
    run_dir.mkdir(exist_ok=False)
    before = lock_inputs()
    manifest = {
        "schema": "independent-rich-run-v1", "run_id": run_id,
        "run_directory": str(run_dir), "started_utc": utc_now(),
        "runner_pid": os.getpid(), "python": str(PYTHON),
        "input_hashes_before": before, "timeout_seconds_per_process": TIMEOUT_SECONDS,
        "scope": "Synthetic baseline unit tests only; no target/native processes or results.",
        "preservation": "Exclusive directory and create-only files; failures retained; fixes require successor paths.",
    }
    write_json_exclusive(run_dir / "RUN_STARTED.json", manifest)
    expected_inputs = all(before.get(name) == digest for name, digest in SPEC_HASHES.items())
    trials = []
    reports = []
    if expected_inputs:
        for mode, optimized in (("normal", False), ("optimized", True)):
            trial, report = run_trial(run_dir, mode, optimized)
            trials.append(trial)
            reports.append(report)
    else:
        manifest["scope_input_changed"] = True
    after = lock_inputs()
    invariant = len(reports) == 2 and all(reports) and semantic_record(reports[0]) == semantic_record(reports[1])
    fresh = len(trials) == 2 and len({trial.get("pid") for trial in trials}) == 2 and all(trial.get("pid") not in (None, os.getpid()) for trial in trials)
    passed = bool(expected_inputs and before == after and invariant and fresh and all(trial["passed"] for trial in trials))
    manifest.update({
        "finished_utc": utc_now(), "trials": trials, "input_hashes_after": after,
        "inputs_unchanged": before == after, "expected_common_input_hashes": expected_inputs,
        "fresh_distinct_processes": fresh, "optimization_semantics_identical": bool(invariant),
        "passed": passed, "status": "SYNTHETIC_TESTS_PASSED" if passed else "PRESERVED_FAILURE",
        "claim_boundary": "Author self-tests, not independent review, target qualification, G4, heldout, human, or publication evidence.",
    })
    write_json_exclusive(run_dir / "RUN_REPORT.json", manifest)
    print(json.dumps({"run_id": run_id, "report": str(run_dir / "RUN_REPORT.json"), "passed": passed, "optimization_semantics_identical": bool(invariant), "trials": [{"mode": trial["mode"], "pid": trial.get("pid"), "returncode": trial.get("returncode"), "tests_run": trial.get("tests", {}).get("tests_run"), "behavior_checks": trial.get("tests", {}).get("behavior_checks"), "passed": trial["passed"]} for trial in trials]}, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
