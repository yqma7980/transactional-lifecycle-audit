from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from p5_contracts import case_authorized, require_case_and_run, require_descendant, require_single_thread_environment, verify_frozen_evidence


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="P5 formal runner contract; FE backend intentionally absent during preflight")
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--results-root", required=True)
    parser.add_argument("--execute-authorized", action="store_true")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    if not case_authorized(args.execute_authorized):
        raise SystemExit("P5 formal execution requires both authorization locks")
    require_single_thread_environment()
    verify_frozen_evidence()
    require_case_and_run(args.case_id, args.run_id)
    require_descendant(Path(args.results_root), ROOT / "results")
    raise SystemExit("P5 full FE execution backend is not installed by the implementation preflight")


if __name__ == "__main__":
    raise SystemExit(main())
