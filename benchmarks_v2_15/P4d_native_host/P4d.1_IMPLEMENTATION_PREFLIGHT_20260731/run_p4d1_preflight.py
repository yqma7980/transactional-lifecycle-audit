from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

ALLOWED = {
    "P4D1-ENV-01",
    "P4D1-BRIDGE-01",
    "P4D1-ORACLE-01",
    "P4D1-TOPOLOGY-01",
    "P4D1-SMOKE-01",
    "P4D1-GUARD-01",
}
FORBIDDEN_PREFIX = "P4D-"


def write_json(path: pathlib.Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--mode", choices=("environment", "observer_off", "observer_on"), required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--ledger")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.preflight_id.startswith(FORBIDDEN_PREFIX) or args.preflight_id not in ALLOWED:
        raise SystemExit("unauthorized preflight or formal case id")
    for variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        if os.environ.get(variable) != "1":
            raise SystemExit(f"{variable}=1 is required")
    output = pathlib.Path(args.output)
    if output.exists():
        raise SystemExit(f"refusing to overwrite {output}")
    if args.mode == "environment":
        if args.preflight_id != "P4D1-ENV-01":
            raise SystemExit("environment mode requires P4D1-ENV-01")
        from p4d_environment import collect_environment
        result = collect_environment(args.run_id)
    else:
        if args.preflight_id != "P4D1-BRIDGE-01":
            raise SystemExit("observer modes require P4D1-BRIDGE-01")
        from p4d_canonical import file_sha256
        from p4d_zero_case import classify_native_nonaccepting_candidate, read_c_ledger, run_dolfinx_owned_zero_case
        enabled = args.mode == "observer_on"
        library = ROOT / "runtime_evidence" / "bridge_build" / "libp4d_observer.so"
        ledger = pathlib.Path(args.ledger) if args.ledger else None
        if enabled and ledger is None:
            raise SystemExit("observer_on requires --ledger")
        if ledger is not None and ledger.exists():
            raise SystemExit(f"refusing to overwrite {ledger}")
        result = run_dolfinx_owned_zero_case(
            observer_enabled=enabled,
            run_id=args.run_id,
            library_path=library if enabled else None,
            ledger_path=ledger,
            observer_build_hash=file_sha256(library) if enabled else None,
        )
        if enabled:
            result["native_candidate_classification"] = classify_native_nonaccepting_candidate(read_c_ledger(ledger))
    write_json(output, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
