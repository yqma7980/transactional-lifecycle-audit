"""One-process worker for a single PERF-D1 cell and repetition."""

from __future__ import annotations

import csv
import ctypes
from ctypes import wintypes
import gc
import hashlib
import json
import math
import os
from pathlib import Path
import time
import tracemalloc
from typing import Any

from benchmarks.L6_external_host.src.l6_state import canonical_json

from .perf_instrumentation import AuditCollector
from .perf_workloads import execute_family


THREAD_ENV = {
    "OMP_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "PYTHONHASHSEED": "0",
    "PYTHONDONTWRITEBYTECODE": "1",
}


class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


def _kernel32() -> Any:
    library = ctypes.WinDLL("kernel32", use_last_error=True)
    library.GetCurrentProcess.restype = wintypes.HANDLE
    library.GetProcessAffinityMask.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(ctypes.c_size_t),
        ctypes.POINTER(ctypes.c_size_t),
    ]
    library.GetProcessAffinityMask.restype = wintypes.BOOL
    library.SetProcessAffinityMask.argtypes = [wintypes.HANDLE, ctypes.c_size_t]
    library.SetProcessAffinityMask.restype = wintypes.BOOL
    return library


def set_and_verify_affinity(mask: int = 1) -> dict[str, int]:
    kernel = _kernel32()
    process = kernel.GetCurrentProcess()
    if not kernel.SetProcessAffinityMask(process, mask):
        raise OSError(ctypes.get_last_error(), "SetProcessAffinityMask failed")
    process_mask = ctypes.c_size_t()
    system_mask = ctypes.c_size_t()
    if not kernel.GetProcessAffinityMask(
        process, ctypes.byref(process_mask), ctypes.byref(system_mask)
    ):
        raise OSError(ctypes.get_last_error(), "GetProcessAffinityMask failed")
    if process_mask.value != mask:
        raise RuntimeError(
            f"affinity mismatch: expected {mask}, found {process_mask.value}"
        )
    return {
        "process_mask": int(process_mask.value),
        "system_mask": int(system_mask.value),
    }


def peak_working_set() -> int:
    kernel = _kernel32()
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    psapi.GetProcessMemoryInfo.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(PROCESS_MEMORY_COUNTERS),
        wintypes.DWORD,
    ]
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    counters = PROCESS_MEMORY_COUNTERS()
    counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
    if not psapi.GetProcessMemoryInfo(
        kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb
    ):
        raise OSError(ctypes.get_last_error(), "GetProcessMemoryInfo failed")
    return int(counters.PeakWorkingSetSize)


def load_matrix(root: Path) -> dict[str, dict[str, str]]:
    path = root / "PERF_D0_case_matrix.csv"
    with path.open("r", encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    return {row["case_id"]: row for row in rows}


def _all_finite(value: Any, limit: float = 1.0e100) -> bool:
    if isinstance(value, bool) or value is None:
        return True
    if isinstance(value, (int, float)):
        return math.isfinite(float(value)) and abs(float(value)) <= limit
    if isinstance(value, dict):
        return all(_all_finite(item, limit) for item in value.values())
    if isinstance(value, (list, tuple)):
        return all(_all_finite(item, limit) for item in value)
    return True


def _hash_payload(value: Any) -> tuple[str, int]:
    payload = canonical_json(value).encode("utf-8")
    return hashlib.sha256(payload).hexdigest(), len(payload)


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def execute_performance_case(
    root: Path,
    *,
    case_id: str,
    run_id: str,
    phase: str,
    output_dir: Path | None,
) -> dict[str, Any]:
    matrix = load_matrix(root)
    if case_id not in matrix:
        raise ValueError(f"unauthorized case: {case_id}")
    if phase not in {"warmup", "preflight", "formal"}:
        raise ValueError(f"unsupported phase: {phase}")
    row = matrix[case_id]
    for key, expected in THREAD_ENV.items():
        if os.environ.get(key) != expected:
            raise RuntimeError(f"{key} must equal {expected}")
    affinity = set_and_verify_affinity(1)

    audit = AuditCollector(row["config_id"])
    gc.collect()
    tracemalloc.start()
    wall_start = time.perf_counter_ns()
    cpu_start = time.process_time_ns()
    accepted_output, counts = execute_family(row, audit)
    audit_metrics = audit.finalize(accepted_output)
    cpu_time_ns = time.process_time_ns() - cpu_start
    wall_time_ns = time.perf_counter_ns() - wall_start
    _, python_peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    peak_working_set_bytes = peak_working_set()

    output_fingerprint, accepted_output_bytes = _hash_payload(accepted_output)
    all_values_finite = _all_finite(accepted_output)
    if not all_values_finite:
        raise FloatingPointError("non-finite accepted output")

    result = {
        "schema_version": "PERF-D1-RUN-1.0",
        "design_version": "PERF-D1.0",
        "case_id": case_id,
        "run_id": run_id,
        "phase": phase,
        "family": row["family"],
        "size": row["size"],
        "config_id": row["config_id"],
        "config_name": row["config_name"],
        "classification": "PASS_OUTPUT_EQUIVALENT_TIMING_RECORDED",
        "pass_flag": True,
        "all_values_finite": all_values_finite,
        "accepted_output_fingerprint": output_fingerprint,
        "accepted_output_bytes": accepted_output_bytes,
        "wall_time_ns": wall_time_ns,
        "cpu_time_ns": cpu_time_ns,
        "peak_working_set_bytes": peak_working_set_bytes,
        "python_peak_bytes": python_peak_bytes,
        "affinity": affinity,
        "thread_environment": dict(THREAD_ENV),
        "counts": counts,
        "audit": {
            "candidate_count": audit_metrics.candidate_count,
            "commit_count": audit_metrics.commit_count,
            "accepted_callback_count": audit_metrics.accepted_callback_count,
            "event_count": audit_metrics.event_count,
            "fingerprint_count": audit_metrics.fingerprint_count,
            "serialized_audit_bytes": audit_metrics.serialized_audit_bytes,
            "serialization_time_ns": audit_metrics.serialization_time_ns,
            "hashing_time_ns": audit_metrics.hashing_time_ns,
            "audit_payload_sha256": audit_metrics.audit_payload_sha256,
            "accepted_output_provenance_sha256": (
                audit_metrics.accepted_output_provenance_sha256
            ),
        },
        "result_file_io_inside_timed_region": False,
        "abaqus_used": False,
        "comsol_used": False,
        "production_model_used": False,
    }

    if output_dir is not None:
        if output_dir.exists():
            raise FileExistsError(output_dir)
        output_dir.mkdir(parents=True)
        accepted_path = output_dir / "accepted_output.json"
        result_path = output_dir / "performance_result.json"
        _write_json(
            accepted_path,
            {
                "case_id": case_id,
                "run_id": run_id,
                "phase": phase,
                "accepted_output_fingerprint": output_fingerprint,
                "accepted_output": accepted_output,
            },
        )
        _write_json(result_path, result)
        outputs = {
            accepted_path.name: hashlib.sha256(accepted_path.read_bytes()).hexdigest(),
            result_path.name: hashlib.sha256(result_path.read_bytes()).hexdigest(),
        }
        manifest = {
            "schema_version": "PERF-D1-RUN-MANIFEST-1.0",
            "design_version": "PERF-D1.0",
            "case_id": case_id,
            "run_id": run_id,
            "phase": phase,
            "outputs": outputs,
            "manifest_self_hash_embedded": False,
        }
        _write_json(output_dir / "case_manifest.json", manifest)
    return result


__all__ = [
    "THREAD_ENV",
    "execute_performance_case",
    "load_matrix",
    "peak_working_set",
    "set_and_verify_affinity",
]