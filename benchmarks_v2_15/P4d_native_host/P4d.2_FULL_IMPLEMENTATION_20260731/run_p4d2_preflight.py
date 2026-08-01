from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parent
for path in (ROOT / "src", ROOT / "oracle"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight-id", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    if args.preflight_id != "P4D2-INTEGRATION-01" or args.preflight_id.startswith("P4D-"):
        raise SystemExit("unauthorized preflight or formal case ID")
    for variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        if os.environ.get(variable) != "1":
            raise SystemExit(f"{variable}=1 is required")
    output = pathlib.Path(args.output)
    if output.exists():
        raise SystemExit(f"refusing to overwrite {output}")
    from p4d_preflight import run_bounded_host_integration
    result = run_bounded_host_integration()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if result["pass_flag"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
