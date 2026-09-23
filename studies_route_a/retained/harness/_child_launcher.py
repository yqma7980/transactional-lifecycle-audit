"""Private gate: do not start the requested child before containment is ready."""

import json
import os
import subprocess
import sys
from pathlib import Path


def record(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def main():
    line = sys.stdin.buffer.readline()
    if not line:
        return 126
    spec = json.loads(line)
    try:
        child = subprocess.Popen(spec["argv"], cwd=spec["cwd"], env=os.environ.copy(),
                                 stdin=subprocess.DEVNULL, shell=False,
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except OSError as exc:
        record(spec["result"], {"started": False, "returncode": None,
                                "error_type": type(exc).__name__, "message": str(exc)})
        return 127
    record(spec["start"], {"pid": child.pid, "argv": spec["argv"], "cwd": spec["cwd"]})
    code = child.wait()
    record(spec["result"], {"started": True, "pid": child.pid, "returncode": code})
    # The parent reads the native returncode from result, including negative signals.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
