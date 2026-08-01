from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys

import numpy as np


ROOT = pathlib.Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _json_default(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    raise TypeError(f"not JSON serializable: {type(value)!r}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight-id", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    if args.preflight_id != "P4D1-TOPOLOGY-01" or args.preflight_id.startswith("P4D-"):
        raise SystemExit("unauthorized preflight or formal case id")
    for variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        if os.environ.get(variable) != "1":
            raise SystemExit(f"{variable}=1 is required")
    output = pathlib.Path(args.output)
    if output.exists():
        raise SystemExit(f"refusing to overwrite {output}")
    from p4d_topology_state import build_topology_packet
    result, _domain, _space = build_topology_packet()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, indent=2, sort_keys=True, default=_json_default) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
