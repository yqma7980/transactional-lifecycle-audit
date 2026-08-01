from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from p5_backend_contracts import (
    NULL_CASE_LIMITS,
    SCALED_CASES,
    case_authorized,
    load_strength_grid,
    require_case_and_run,
    require_descendant,
    require_single_thread_environment,
    strength_index_for_run,
    verify_protected_evidence,
)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="P5 full FE single-case runner")
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--results-root", required=True)
    parser.add_argument("--thresholds-file")
    parser.add_argument("--selection-file")
    parser.add_argument("--execute-authorized", action="store_true")
    return parser.parse_args(argv)


def _read_thresholds(path: Path | None) -> dict[str, float] | None:
    if path is None:
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    values = payload.get("thresholds")
    if not isinstance(values, dict):
        raise SystemExit("threshold file has no threshold mapping")
    return {str(key): float(value) for key, value in values.items()}


def main(argv=None) -> int:
    args = parse_args(argv)
    if not case_authorized(args.execute_authorized):
        raise SystemExit("P5 formal execution requires both authorization locks")
    require_single_thread_environment()
    verify_protected_evidence()
    require_case_and_run(args.case_id, args.run_id)

    results_root = require_descendant(Path(args.results_root), ROOT / "results")
    threshold_path = Path(args.thresholds_file).resolve() if args.thresholds_file else None
    selection_path = Path(args.selection_file).resolve() if args.selection_file else None
    if threshold_path is not None:
        require_descendant(threshold_path, results_root)
    if selection_path is not None:
        require_descendant(selection_path, results_root)
    thresholds = _read_thresholds(threshold_path)
    if args.case_id == "P5-NULL-ARITH-CONF-01" and thresholds is None:
        raise SystemExit("null confirmation requires --thresholds-file")
    if args.case_id in SCALED_CASES and thresholds is None:
        raise SystemExit("scaled P5 cases require --thresholds-file")

    strength_index = strength_index_for_run(args.case_id, args.run_id, selection_path)
    eta = None if strength_index is None else float(load_strength_grid()[strength_index]["eta"])

    p4d2_src = ROOT.parent / "P4d_DOLFINx_PETSc_MINIMAL_FE_HOST_20260731" / "P4d.2_FULL_IMPLEMENTATION_20260731" / "src"
    sys.path.insert(0, str(p4d2_src))
    from p4d_canonical import canonical_hash
    from p4d_environment import collect_environment

    environment = collect_environment(args.run_id)
    environment["semantic_environment_hash"] = canonical_hash({key: value for key, value in environment.items() if key != "run_id"})

    result_directory = results_root / args.case_id / args.run_id
    if result_directory.exists():
        raise SystemExit(f"refusing to overwrite existing result directory: {result_directory}")
    result_directory.mkdir(parents=True, exist_ok=False)

    from p5_case_executor import execute_case

    result = execute_case(
        case_id=args.case_id,
        run_id=args.run_id,
        result_directory=result_directory,
        environment=environment,
        strength_index=strength_index,
        eta=eta,
        thresholds=thresholds,
    )
    print(json.dumps({"case_id": args.case_id, "run_id": args.run_id, "classification": result["observed_classification"], "pass_flag": result["pass_flag"]}, sort_keys=True))
    return 0 if result["pass_flag"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
