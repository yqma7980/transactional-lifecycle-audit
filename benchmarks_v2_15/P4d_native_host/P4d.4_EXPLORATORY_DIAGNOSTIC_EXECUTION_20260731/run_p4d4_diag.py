from __future__ import annotations

import argparse
import os
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

AUTHORIZED_CASES = {
    "P4D4-DIAG-LS-01",
    "P4D4-DIAG-LS-02",
    "P4D4-DIAG-LS-03",
}


def parse_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--results-root", required=True)
    parser.add_argument("--p4d2-root", required=True)
    parser.add_argument("--execute-authorized", action="store_true")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.case_id not in AUTHORIZED_CASES:
        raise SystemExit("unauthorized or unknown P4d.4 diagnostic case")
    if args.run_id != "run_1":
        raise SystemExit("P4d.4 exploratory freeze permits only run_1")
    if (
        not args.execute_authorized
        or os.environ.get("P4D4_DIAGNOSTIC_EXECUTION_AUTHORIZED") != "YES"
    ):
        raise SystemExit("P4d.4 diagnostic execution requires both authorization locks")
    for variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        if os.environ.get(variable) != "1":
            raise SystemExit(f"{variable}=1 is required")

    p4d2_root = pathlib.Path(args.p4d2_root).resolve()
    p4d2_src = p4d2_root / "src"
    if str(p4d2_src) not in sys.path:
        sys.path.insert(0, str(p4d2_src))

    result_directory = pathlib.Path(args.results_root) / args.case_id / args.run_id
    if result_directory.exists():
        raise SystemExit(f"refusing to overwrite {result_directory}")
    result_directory.mkdir(parents=True)

    from p4d_environment import collect_environment
    from p4d4_diagnostic import execute_diagnostic

    result = execute_diagnostic(
        case_id=args.case_id,
        run_id=args.run_id,
        result_directory=result_directory,
        p4d2_root=p4d2_root,
        environment=collect_environment(args.run_id),
    )
    return 0 if result.get("execution_completed") is True else 2


if __name__ == "__main__":
    raise SystemExit(main())
