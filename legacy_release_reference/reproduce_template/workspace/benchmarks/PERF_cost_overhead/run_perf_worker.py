from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--phase", choices=("warmup", "preflight", "formal"), required=True)
    parser.add_argument("--output-dir")
    parser.add_argument("--worker-authorized", action="store_true")
    args = parser.parse_args()

    if not args.worker_authorized or os.environ.get("PERF_D1_WORKER_AUTHORIZED") != "YES":
        parser.error("PERF-D1 worker execution is not authorized")

    root = Path(__file__).resolve().parent
    workspace = root.parents[1]
    if str(workspace) not in sys.path:
        sys.path.insert(0, str(workspace))

    from benchmarks.PERF_cost_overhead.src.perf_worker import (
        execute_performance_case,
    )

    result = execute_performance_case(
        root,
        case_id=args.case_id,
        run_id=args.run_id,
        phase=args.phase,
        output_dir=Path(args.output_dir) if args.output_dir else None,
    )
    print(
        json.dumps(
            {
                "case_id": result["case_id"],
                "run_id": result["run_id"],
                "phase": result["phase"],
                "accepted_output_fingerprint": result[
                    "accepted_output_fingerprint"
                ],
                "pass_flag": result["pass_flag"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())