"""Bounded, no-overwrite subprocess capture for trusted local workloads.

Windows: a gated launcher enters a kill-on-close Job Object before spawning the
requested child. POSIX: a new session/process group is terminated on completion.
This is resource hygiene, not a security sandbox or a network/disk isolation tool.
"""

import argparse
import ctypes
import datetime as dt
import json
import math
import os
import platform
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from kit_io import sha256, write_json_new, read_json

ENV_ALLOWLIST = ("SystemRoot", "WINDIR", "PATH", "PATHEXT", "LANG", "LC_ALL", "TZ")


class WindowsJob:
    def __init__(self):
        from ctypes import wintypes as w

        class Basic(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                        ("LimitFlags", w.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", w.DWORD),
                        ("Affinity", ctypes.c_size_t), ("PriorityClass", w.DWORD), ("SchedulingClass", w.DWORD)]

        class IO(ctypes.Structure):
            _fields_ = [(name, ctypes.c_uint64) for name in
                        ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                         "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

        class Extended(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", Basic), ("IoInfo", IO),
                        ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                        ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

        class Accounting(ctypes.Structure):
            _fields_ = [(name, ctypes.c_int64) for name in
                        ("TotalUserTime", "TotalKernelTime", "ThisPeriodTotalUserTime", "ThisPeriodTotalKernelTime")]
            _fields_ += [(name, w.DWORD) for name in
                         ("TotalPageFaultCount", "TotalProcesses", "ActiveProcesses", "TotalTerminatedProcesses")]
        self.Extended, self.Accounting = Extended, Accounting

        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        signatures = {
            "CreateJobObjectW": ([ctypes.c_void_p, w.LPCWSTR], w.HANDLE),
            "SetInformationJobObject": ([w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD], w.BOOL),
            "OpenProcess": ([w.DWORD, w.BOOL, w.DWORD], w.HANDLE),
            "AssignProcessToJobObject": ([w.HANDLE, w.HANDLE], w.BOOL),
            "CloseHandle": ([w.HANDLE], w.BOOL),
            "QueryInformationJobObject": ([w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD, ctypes.c_void_p], w.BOOL),
            "TerminateJobObject": ([w.HANDLE, w.UINT], w.BOOL),
        }
        for name, (args, result) in signatures.items():
            function = getattr(self.api, name)
            function.argtypes, function.restype = args, result
        self.handle = self.api.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        info = Extended()
        info.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.api.SetInformationJobObject(self.handle, 9, ctypes.byref(info), ctypes.sizeof(info)):
            error = ctypes.WinError(ctypes.get_last_error())
            self.close()
            raise error

    def assign(self, process):
        handle = self.api.OpenProcess(0x0100 | 0x0001, False, process.pid)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            if not self.api.AssignProcessToJobObject(self.handle, handle):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            self.api.CloseHandle(handle)

    def close(self):
        if self.handle:
            if not self.api.CloseHandle(self.handle):
                raise ctypes.WinError(ctypes.get_last_error())
            self.handle = None

    def metrics(self):
        accounting, memory = self.Accounting(), self.Extended()
        for cls, obj in [(1, accounting), (9, memory)]:
            if not self.api.QueryInformationJobObject(self.handle, cls, ctypes.byref(obj), ctypes.sizeof(obj), None):
                raise ctypes.WinError(ctypes.get_last_error())
        return dict(cpu_seconds=(accounting.TotalUserTime + accounting.TotalKernelTime) / 1e7,
                    total_processes=accounting.TotalProcesses, active_processes=accounting.ActiveProcesses,
                    peak_process_memory_bytes=memory.PeakProcessMemoryUsed,
                    peak_job_memory_bytes=memory.PeakJobMemoryUsed)

    def terminate_wait(self):
        if not self.api.TerminateJobObject(self.handle, 124):
            raise ctypes.WinError(ctypes.get_last_error())
        end = time.monotonic() + 5
        while self.metrics()['active_processes'] and time.monotonic() < end:
            time.sleep(.02)
        result = self.metrics()
        if result['active_processes']:
            raise RuntimeError('owned job members remain after termination deadline')
        return result


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _environment(folder):
    env = {key: os.environ[key] for key in ENV_ALLOWLIST if key in os.environ}
    for name in ("tmp", "home", "home/appdata", "home/localappdata"):
        (folder / name).mkdir(parents=True, exist_ok=False)
    env.update({"PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0", "PYTHONUTF8": "1",
                "PYTHONNOUSERSITE": "1", "PYTHONUNBUFFERED": "1",
                "TEMP": str(folder / "tmp"), "TMP": str(folder / "tmp"), "TMPDIR": str(folder / "tmp"),
                "HOME": str(folder / "home"), "USERPROFILE": str(folder / "home"),
                "APPDATA": str(folder / "home/appdata"), "LOCALAPPDATA": str(folder / "home/localappdata")})
    return env


def _pump(pipe, path, limit, stop, stats):
    try:
        with path.open("xb") as log:
            while True:
                block = pipe.read(65536)
                if not block:
                    break
                stats["observed_bytes"] += len(block)
                keep = block[:max(0, limit - stats["saved_bytes"])]
                log.write(keep)
                log.flush()
                stats["saved_bytes"] += len(keep)
                if len(keep) != len(block):
                    stats["truncated"] = True
                    stop.set()
    except Exception as exc:
        stats["error"] = type(exc).__name__ + ": " + str(exc)
        stop.set()
    finally:
        pipe.close()


def capture(argv, run_dir, *, cwd, timeout_seconds, max_log_bytes=1048576,
            extra_environment=None, directory_limits=None):
    """cwd is a required relative directory inside the NEW run directory."""
    if isinstance(argv, (str, bytes)) or not argv:
        raise ValueError("argv must be a nonempty sequence, never a shell string")
    argv = [os.fspath(part) for part in argv]
    if not Path(argv[0]).is_absolute():
        raise ValueError("argv[0] must be an explicit absolute executable path")
    if Path(argv[0]).suffix.lower() in {".bat", ".cmd", ".ps1"}:
        raise ValueError("implicit shell scripts are not supported")
    timeout_seconds = float(timeout_seconds)
    if not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 1800:
        raise ValueError("timeout must be finite, > 0 and <= 1800 seconds")
    if type(max_log_bytes) is not int or not 1 <= max_log_bytes <= 16 * 1024 * 1024:
        raise ValueError("log limit must be 1..16777216 bytes per stream")
    relative = Path(cwd)
    if relative.is_absolute() or relative.drive or ".." in relative.parts:
        raise ValueError("cwd must stay within the new run directory")
    reserved = {"tmp", "home", "reservation.json", "request.json", "process.json", "target_start.json",
                "target_exit.json", "stdout.log", "stderr.log"}
    if relative.parts and relative.parts[0].lower() in reserved:
        raise ValueError("cwd conflicts with runner-owned metadata or environment directories")
    if any("\x00" in part for part in argv):
        raise ValueError("argv may not contain NUL characters")
    task_root = Path(__file__).resolve().parents[1]
    requested = Path(run_dir).resolve()
    if not requested.is_relative_to(task_root):
        raise ValueError('run directory must stay inside new execution root')
    protected_env = {'HOME','USERPROFILE','APPDATA','LOCALAPPDATA','TEMP','TMP','TMPDIR',
                     'PYTHONDONTWRITEBYTECODE','PYTHONNOUSERSITE','PYTHONHASHSEED','PYTHONUTF8'}
    if extra_environment and protected_env.intersection(str(k).upper() for k in extra_environment):
        raise ValueError('reserved isolated environment may not be overridden')
    if requested.exists() or requested.is_symlink():
        raise FileExistsError("refusing existing run directory: " + str(requested))
    requested.mkdir(parents=True, exist_ok=False)
    folder = requested.resolve()
    work = (folder / relative).resolve()
    if not work.is_relative_to(folder):
        raise ValueError("cwd escapes the run directory")
    launcher = Path(__file__).resolve().with_name("_child_launcher.py")
    launcher_argv = [sys.executable, "-B", "-I", str(launcher)]
    # A durable identity survives unexpected setup failures before launch.
    write_json_new(folder / "reservation.json", {"schema": "S08-RESERVATION-1", "created_utc": utc_now(),
                   "argv": argv, "cwd": str(work), "timeout_seconds": timeout_seconds})
    work.mkdir(parents=True, exist_ok=True)
    env = _environment(folder)
    if extra_environment:
        env.update({str(k): str(v) for k, v in extra_environment.items()})
    task_root = Path(__file__).resolve().parents[1]
    limits = []
    for item in directory_limits or []:
        paths = [Path(p).resolve() for p in item['paths']]
        if not all(p.is_relative_to(task_root) for p in paths):
            raise ValueError('directory monitoring must stay inside new execution root')
        if type(item['bytes']) is not int or item['bytes'] <= 0:
            raise ValueError('invalid directory byte limit')
        limits.append(dict(paths=[str(p) for p in paths], bytes=item['bytes']))
    request = {"schema": "S08-PROCESS-1", "run_id": folder.name, "run_directory": str(folder),
               "argv": argv, "cwd": str(work), "cwd_relative": relative.as_posix(), "shell": False,
               "timeout_seconds": timeout_seconds, "max_log_bytes_per_stream": max_log_bytes,
               "started_utc": utc_now(), "environment_policy": "allowlist_and_run_local_home_temp",
               "inherited_allowlist": list(ENV_ALLOWLIST), "effective_environment": env,
               "supervisor": {"python": sys.version, "executable": sys.executable,
                              "executable_sha256": sha256(sys.executable), "platform": platform.platform(),
                              "machine": platform.machine(), "prefix": sys.prefix, "base_prefix": sys.base_prefix},
               "launcher_argv": launcher_argv, "launcher_sha256": sha256(launcher),
               "runner_sha256": sha256(__file__), "target_executable_sha256":
               sha256(argv[0]) if Path(argv[0]).is_file() else None,
               "containment": "windows_job_kill_on_close_gated" if os.name == "nt" else "posix_new_process_group",
               "evidence_class": "SOFTWARE_QA_NOT_INDEPENDENT_HUMAN_REPRODUCTION"}
    request['directory_limits'] = limits
    request['directory_limit_policy'] = 'sampled size checks every >=1s with termination; transient overshoot possible, not a filesystem quota'
    request['supervisor']['pid'] = os.getpid()
    write_json_new(folder / "request.json", request)
    begin = time.monotonic()
    process = job = None
    threads = []
    stop = threading.Event()
    stats = {name: {"observed_bytes": 0, "saved_bytes": 0, "truncated": False} for name in ("stdout", "stderr")}
    status, error, cleanup_errors = "COMPLETED", None, []
    resource_metrics, sizes, next_disk_check = None, [], 0
    try:
        if os.name == "nt":
            job = WindowsJob()
        process = subprocess.Popen(launcher_argv, cwd=work, env=env, stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0, shell=False,
                                   start_new_session=os.name != "nt",
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if job:
            job.assign(process)
        for name in stats:
            thread = threading.Thread(target=_pump, args=(getattr(process, name), folder / (name + ".log"),
                                      max_log_bytes, stop, stats[name]), daemon=True)
            thread.start()
            threads.append(thread)
        payload = {"argv": argv, "cwd": str(work), "start": str(folder / "target_start.json"),
                   "result": str(folder / "target_exit.json")}
        process.stdin.write((json.dumps(payload) + "\n").encode("utf-8"))
        process.stdin.close()
        while process.poll() is None:
            if stop.is_set():
                status = "OUTPUT_LIMIT"
                break
            if time.monotonic() - begin >= timeout_seconds:
                status = "TIMEOUT"
                break
            if limits and time.monotonic() >= next_disk_check:
                sizes = []
                for item in limits:
                    total = sum(p.stat().st_size for path in item['paths'] for p in Path(path).rglob('*') if p.is_file())
                    sizes.append(dict(paths=item['paths'], observed_bytes=total, limit_bytes=item['bytes']))
                next_disk_check = time.monotonic() + 1
                if any(x['observed_bytes'] > x['limit_bytes'] for x in sizes):
                    status = 'DIRECTORY_LIMIT'
                    break
            stop.wait(0.02)
    except Exception as exc:
        status, error = "SUPERVISOR_ERROR", {"type": type(exc).__name__, "message": str(exc)}
    finally:
        # Only the job or process group created above is eligible for cleanup.
        try:
            if job:
                try:
                    resource_metrics = job.metrics()
                    resource_metrics['cleanup'] = job.terminate_wait()
                finally:
                    job.close()
            elif process and os.name != "nt":
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        except Exception as exc:
            cleanup_errors.append(type(exc).__name__ + ": " + str(exc))
        if process:
            if process.poll() is None:
                process.kill()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                cleanup_errors.append("owned launcher did not exit within 5 seconds")
            if process.stdin and not process.stdin.closed:
                process.stdin.close()
            if not threads:
                process.stdout.close()
                process.stderr.close()
        for thread in threads:
            thread.join(timeout=5)
        if any(thread.is_alive() for thread in threads):
            cleanup_errors.append("log reader did not finish within 5 seconds")
        for name in stats:
            path = folder / (name + ".log")
            if not path.exists():
                path.touch(exist_ok=False)
    if status == "COMPLETED" and any(item["truncated"] for item in stats.values()):
        status = "OUTPUT_LIMIT"
    if cleanup_errors or any("error" in item for item in stats.values()):
        status = "SUPERVISOR_ERROR"
    if limits:
        try:
            sizes = [dict(paths=item['paths'], limit_bytes=item['bytes'], observed_bytes=
                     sum(p.stat().st_size for path in item['paths'] for p in Path(path).rglob('*') if p.is_file()))
                     for item in limits]
            if any(x['observed_bytes'] > x['limit_bytes'] for x in sizes) and status in ('COMPLETED', 'NONZERO_EXIT'):
                status = 'DIRECTORY_LIMIT'
        except Exception as exc:
            cleanup_errors.append('final directory measurement: ' + repr(exc))
            status = 'SUPERVISOR_ERROR'
    target_path = folder / "target_exit.json"
    target, code = None, None
    try:
        candidate = read_json(target_path) if target_path.exists() else None
        if candidate is not None:
            if (not isinstance(candidate, dict) or type(candidate.get('started')) is not bool or
                (candidate['started'] and (set(candidate) != {'started','pid','returncode'} or
                 type(candidate.get('pid')) is not int or candidate['pid'] <= 0 or
                 type(candidate.get('returncode')) is not int)) or
                (not candidate['started'] and (set(candidate) != {'started','returncode','error_type','message'} or
                 candidate['returncode'] is not None or not isinstance(candidate['error_type'],str) or
                 not isinstance(candidate['message'],str)))):
                raise ValueError('invalid native launcher footer schema')
            json.dumps(candidate, allow_nan=False)
            target = candidate
            code = target.get('returncode')
    except Exception as exc:
        target, code = None, None
        status = 'SUPERVISOR_ERROR'
        error = {'type': type(exc).__name__, 'message': 'terminal footer: ' + str(exc)}
    if status == "COMPLETED":
        if target is None:
            status = "SUPERVISOR_ERROR"
        elif not target["started"]:
            status = "LAUNCH_ERROR"
        elif code != 0:
            status = "NONZERO_EXIT"
    cli_code = {"TIMEOUT": 124, "OUTPUT_LIMIT": 125, "DIRECTORY_LIMIT": 125, "SUPERVISOR_ERROR": 126, "LAUNCH_ERROR": 127}.get(status)
    if cli_code is None:
        cli_code = code if 0 <= code <= 255 else 1
    result = dict(request, finished_utc=utc_now(), elapsed_seconds=time.monotonic() - begin,
                  status=status, exit_code=code, launcher_exit_code=process.returncode if process else None,
                  runner_exit_code=cli_code, timeout=status == "TIMEOUT", streams=stats,
                  error=error, cleanup_errors=cleanup_errors, target_result=target,
                  resource_metrics=resource_metrics, directory_measurements=sizes,
                  artifacts={name: {"path": name + ".log", "sha256": sha256(folder / (name + ".log"))} for name in stats})
    # Reserve the exact bytes of final metadata in each enclosing sampled limit.
    # Iterate only over metadata, never rerun a target. Publication is atomic.
    for _ in range(30):
        try:
            encoded = (json.dumps(result, indent=2, ensure_ascii=True, allow_nan=False) + '\n').encode('utf-8')
        except (ValueError, TypeError) as exc:
            result = dict(schema='M003-SUPERVISOR-FAILURE-1',run_id=folder.name,run_directory=str(folder),
                status='SUPERVISOR_ERROR',exit_code=None,runner_exit_code=126,
                error={'type':type(exc).__name__,'message':'terminal serialization failed'},
                raw_request_retained='request.json',raw_footer_retained='target_exit.json',
                directory_measurements=[],cleanup_errors=['unsafe terminal serialization rejected'])
            encoded = (json.dumps(result,indent=2,ensure_ascii=True,allow_nan=False)+'\n').encode('utf-8')
        measured = []
        for item in limits:
            total = sum(p.stat().st_size for path in item['paths'] for p in Path(path).rglob('*') if p.is_file())
            if any((folder / 'process.json').is_relative_to(Path(path)) for path in item['paths']):
                total += len(encoded)
            measured.append(dict(paths=item['paths'], limit_bytes=item['bytes'], observed_bytes=total))
        previous = (result['status'], result['directory_measurements'])
        result['directory_measurements'] = measured
        if any(x['observed_bytes'] > x['limit_bytes'] for x in measured):
            result['status'] = 'DIRECTORY_LIMIT'
            result['runner_exit_code'] = 125
        if previous == (result['status'], measured):
            break
    else:
        result['status'], result['runner_exit_code'] = 'SUPERVISOR_ERROR', 126
        result['cleanup_errors'].append('final metadata size did not converge')
    temporary = folder / 'process.json.partial'
    write_json_new(temporary, result)
    os.rename(temporary, folder / 'process.json')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--cwd", required=True, help="relative to NEW run-dir (e.g. work)")
    parser.add_argument("--timeout", required=True, type=float)
    parser.add_argument("--max-log-bytes", type=int, default=1048576)
    parser.add_argument("argv", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    argv = args.argv[1:] if args.argv[:1] == ["--"] else args.argv
    try:
        result = capture(argv, args.run_dir, cwd=args.cwd, timeout_seconds=args.timeout, max_log_bytes=args.max_log_bytes)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps({"status": result["status"], "exit_code": result["exit_code"],
                      "runner_exit_code": result["runner_exit_code"], "process_record": str(args.run_dir.resolve() / "process.json")}))
    return result["runner_exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
