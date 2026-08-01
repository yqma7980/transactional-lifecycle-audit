from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
for path in (ROOT / "src",):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from p4d5_protocol import (
    P4D2_RESULTS_ROOT,
    P4D2_ROOT,
    case_authorized,
    require_case_and_run,
    require_descendant,
    require_single_thread_environment,
    verify_inherited_prerequisites,
    verify_protected_inputs,
)


def parse_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--results-root", required=True)
    parser.add_argument("--dependency-root", required=True)
    parser.add_argument("--execute-authorized", action="store_true")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    require_case_and_run(args.case_id, args.run_id)
    if not case_authorized(args.execute_authorized):
        raise SystemExit("P4d.5 case execution requires both authorization locks")
    require_single_thread_environment()
    verify_protected_inputs()
    verify_inherited_prerequisites()

    results_root = require_descendant(Path(args.results_root), ROOT / "results")
    dependency_root = Path(args.dependency_root).resolve()
    if dependency_root != P4D2_RESULTS_ROOT.resolve():
        raise SystemExit(
            "dependency root must be the protected P4d.2 formal evidence root"
        )
    result_directory = results_root / args.case_id / args.run_id
    if result_directory.exists():
        raise SystemExit(f"refusing to overwrite {result_directory}")

    # Numerical imports occur only after authorization, identity and path checks.
    for path in (P4D2_ROOT / "src", P4D2_ROOT / "oracle"):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    from p4d_environment import collect_environment
    from p4d_cases import execute_case

    result_directory.mkdir(parents=True)
    result = execute_case(
        root=P4D2_ROOT,
        case_id=args.case_id,
        run_id=args.run_id,
        result_directory=result_directory,
        dependency_root=dependency_root,
        environment=collect_environment(args.run_id),
    )
    pass_flag = result.get("pass_flag")
    return 0 if pass_flag is True or (type(pass_flag) is int and pass_flag == 1) else 2


if __name__ == "__main__":
    raise SystemExit(main())
