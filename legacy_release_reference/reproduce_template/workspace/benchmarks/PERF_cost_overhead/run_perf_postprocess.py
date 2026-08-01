from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys


_ROOT = Path(__file__).resolve().parent
_WORKSPACE = _ROOT.parents[1]
if str(_WORKSPACE) not in sys.path:
    sys.path.insert(0, str(_WORKSPACE))

from benchmarks.PERF_cost_overhead.src.perf_postprocess import build_evidence

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute-authorized", action="store_true")
    args = parser.parse_args()
    if (
        not args.execute_authorized
        or os.environ.get("PERF_D1_POSTPROCESS_AUTHORIZED") != "YES"
    ):
        parser.error("PERF-D1 postprocessing is not authorized")

    root = _ROOT

    summary = build_evidence(root)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
