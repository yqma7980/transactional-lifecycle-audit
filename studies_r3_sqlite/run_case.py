from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from r3sqlite.subject import execute_case  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--mode", choices=("diagnostic", "enforce"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8"))
    cases = {item["case_id"]: item for item in config["cases"]}
    if args.case_id not in cases:
        raise SystemExit(f"unknown case: {args.case_id}")
    result = execute_case(
        cases[args.case_id], run_id=args.run_id, mode=args.mode, output_dir=args.output
    )
    print(json.dumps(result, sort_keys=True))
    return 0 if result["verdict_match"] and result["containment_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

