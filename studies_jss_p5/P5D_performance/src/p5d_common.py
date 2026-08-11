from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import os
import platform
import sys
from pathlib import Path
from typing import Any

import numpy as np

try:
    import resource
except ImportError:  # Windows host used by the frozen SciPy subject.
    resource = None


DESIGN_ID = "JSS-P5D-PERFORMANCE-1.0"
MODES = {"M0_AUDIT_OFF", "M3_GENERIC_REPLAY", "M6_FULL_TLA"}
FINITE_LIMIT = 1.0e100


def _canonical(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return _canonical(dataclasses.asdict(value))
    if isinstance(value, np.ndarray):
        return {
            "__ndarray__": [_canonical(item) for item in value.reshape(-1).tolist()],
            "dtype": str(value.dtype),
            "shape": list(value.shape),
        }
    if isinstance(value, np.generic):
        return _canonical(value.item())
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("canonical payload requires finite floats")
        return {"__float_hex__": value.hex()}
    if isinstance(value, dict):
        return {str(key): _canonical(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    if isinstance(value, Path):
        return value.as_posix()
    raise TypeError(f"unsupported canonical value: {type(value)!r}")


def canonical_json(value: Any) -> str:
    return json.dumps(_canonical(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("ascii")).hexdigest()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def write_json_new(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(path)
    payload = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    path.write_text(payload, encoding="utf-8", newline="\n")


def finite_values(values: Any) -> bool:
    if isinstance(values, dict):
        return all(finite_values(item) for item in values.values())
    if isinstance(values, (list, tuple)):
        return all(finite_values(item) for item in values)
    if isinstance(values, (float, int, np.number)):
        return math.isfinite(float(values)) and abs(float(values)) < FINITE_LIMIT
    return True


def bind_process_to_cpu0() -> None:
    if hasattr(os, "sched_setaffinity"):
        os.sched_setaffinity(0, {0})
        return
    import ctypes

    kernel32 = ctypes.windll.kernel32
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    kernel32.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
    kernel32.SetProcessAffinityMask.restype = ctypes.c_int
    handle = kernel32.GetCurrentProcess()
    if not kernel32.SetProcessAffinityMask(handle, ctypes.c_size_t(1)):
        raise OSError("SetProcessAffinityMask failed")


def current_affinity() -> list[int]:
    if hasattr(os, "sched_getaffinity"):
        return sorted(os.sched_getaffinity(0))
    import ctypes

    kernel32 = ctypes.windll.kernel32
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    kernel32.GetProcessAffinityMask.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_size_t),
        ctypes.POINTER(ctypes.c_size_t),
    ]
    kernel32.GetProcessAffinityMask.restype = ctypes.c_int
    process_mask = ctypes.c_size_t()
    system_mask = ctypes.c_size_t()
    handle = kernel32.GetCurrentProcess()
    if not kernel32.GetProcessAffinityMask(
        handle, ctypes.byref(process_mask), ctypes.byref(system_mask)
    ):
        raise OSError("GetProcessAffinityMask failed")
    return [index for index in range(process_mask.value.bit_length()) if process_mask.value & (1 << index)]


def peak_rss_bytes() -> int:
    if resource is not None:
        value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        return value * 1024 if sys.platform.startswith("linux") else value
    import ctypes

    class ProcessMemoryCounters(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_ulong),
            ("PageFaultCount", ctypes.c_ulong),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    counters = ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    kernel32 = ctypes.windll.kernel32
    psapi = ctypes.windll.psapi
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    psapi.GetProcessMemoryInfo.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ProcessMemoryCounters),
        ctypes.c_ulong,
    ]
    psapi.GetProcessMemoryInfo.restype = ctypes.c_int
    handle = kernel32.GetCurrentProcess()
    if not psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
        raise OSError("GetProcessMemoryInfo failed")
    return int(counters.PeakWorkingSetSize)


def environment_packet() -> dict[str, Any]:
    affinity = current_affinity()
    packet: dict[str, Any] = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "python_executable": Path(sys.executable).name,
        "machine": platform.machine(),
        "processor": platform.processor(),
        "pid_namespace_visible_cpu_count": os.cpu_count(),
        "affinity": affinity,
        "threads": {
            "OMP_NUM_THREADS": os.environ.get("OMP_NUM_THREADS"),
            "OPENBLAS_NUM_THREADS": os.environ.get("OPENBLAS_NUM_THREADS"),
            "MKL_NUM_THREADS": os.environ.get("MKL_NUM_THREADS"),
        },
    }
    try:
        import scipy

        packet["scipy"] = scipy.__version__
    except Exception:
        packet["scipy"] = "NOT_IMPORTED"
    try:
        import dolfinx
        from petsc4py import PETSc
        import mpi4py

        packet["dolfinx"] = dolfinx.__version__
        packet["petsc"] = PETSc.Sys.getVersion()
        packet["mpi4py"] = mpi4py.__version__
        packet["mpi_size"] = PETSc.COMM_WORLD.getSize()
    except Exception:
        packet["dolfinx"] = "NOT_IMPORTED"
        packet["mpi4py"] = "NOT_USED"
        packet["mpi_size"] = 1
    packet["semantic_fingerprint"] = canonical_hash(packet)
    return packet


def normalize_event(event: dict[str, Any]) -> dict[str, Any]:
    excluded = {
        "run_id",
        "path_id",
        "solve_id",
        "attempt_id",
        "event_id",
        "candidate_source_event_id",
        "accepted_residual_event_id",
        "timestamp",
        "file_path",
    }
    return {key: value for key, value in event.items() if key not in excluded}


def validate_mode(mode: str) -> None:
    if mode not in MODES:
        raise ValueError(f"unsupported P5D mode: {mode}")
