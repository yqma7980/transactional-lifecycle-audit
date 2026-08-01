from __future__ import annotations

import argparse
import os
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parent
for path in (ROOT / "src", ROOT / "oracle"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


def parse_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--results-root", required=True)
    parser.add_argument("--dependency-root")
    parser.add_argument("--execute-authorized", action="store_true")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    from p4d_config import FORMAL_CASE_IDS

    if args.case_id not in FORMAL_CASE_IDS:
        raise SystemExit("unauthorized or unknown formal P4d case")
    if not args.execute_authorized or os.environ.get("P4D2_EXECUTION_AUTHORIZED") != "YES":
        raise SystemExit("formal P4d execution requires both authorization locks")
    for variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        if os.environ.get(variable) != "1":
            raise SystemExit(f"{variable}=1 is required")
    results_root = pathlib.Path(args.results_root)
    result_directory = results_root / args.case_id / args.run_id
    if result_directory.exists():
        raise SystemExit(f"refusing to overwrite {result_directory}")
    result_directory.mkdir(parents=True)
    try:
        from p4d_environment import collect_environment
        from p4d_cases import execute_case

        result = execute_case(
            root=ROOT,
            case_id=args.case_id,
            run_id=args.run_id,
            result_directory=result_directory,
            dependency_root=pathlib.Path(args.dependency_root) if args.dependency_root else None,
            environment=collect_environment(args.run_id),
        )
    except Exception:
        # Preserve the created directory as failure evidence; never reuse it.
        raise
    return 0 if result.get("pass_flag") is True else 2


if __name__ == "__main__":
    raise SystemExit(main())
