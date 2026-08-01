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

MODE_TO_ID = {
    "oracle": "P4D1-ORACLE-01",
    "topology": "P4D1-TOPOLOGY-01",
    "safe_smoke": "P4D1-SMOKE-01",
}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight-id", required=True)
    parser.add_argument("--mode", choices=tuple(MODE_TO_ID), required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    if args.preflight_id.startswith("P4D-") or args.preflight_id != MODE_TO_ID[args.mode]:
        raise SystemExit("unauthorized preflight or formal case id")
    for variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        if os.environ.get(variable) != "1":
            raise SystemExit(f"{variable}=1 is required")
    output = pathlib.Path(args.output)
    if output.exists():
        raise SystemExit(f"refusing to overwrite {output}")
    if args.mode == "oracle":
        from p4d_oracle_stage import run_oracle_stage
        result = run_oracle_stage(ROOT)
    elif args.mode == "topology":
        from p4d_topology_state import build_topology_packet
        result, _domain, _space = build_topology_packet()
    else:
        from p4d_safe_smoke import run_safe_increment_smoke
        result = run_safe_increment_smoke()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
