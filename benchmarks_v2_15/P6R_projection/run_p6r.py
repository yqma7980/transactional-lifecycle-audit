from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from p6r_contracts import require_execution_authorized, require_single_thread_environment
from p6r_execution import execute_one_projection_process


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="P6R read-only secondary-projection runner")
    parser.add_argument("--ncs-root", required=True)
    parser.add_argument("--study-root", required=True)
    parser.add_argument("--results-root", required=True)
    parser.add_argument("--execution-tag", required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--repetition", required=True, type=int, choices=(1, 2))
    parser.add_argument("--execute-authorized", action="store_true")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    # Both locks are checked before evidence is loaded or an output directory is resolved/created.
    require_execution_authorized(args.execute_authorized, os.environ)
    require_single_thread_environment(os.environ)
    execute_one_projection_process(
        ncs_root=Path(args.ncs_root),
        study_root=Path(args.study_root),
        implementation_root=ROOT,
        results_root=Path(args.results_root),
        execution_tag=args.execution_tag,
        case_id=args.case_id,
        repetition=args.repetition,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

