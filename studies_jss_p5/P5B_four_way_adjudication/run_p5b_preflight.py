from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from jss_p5b.adjudication import adjudicate  # noqa: E402
from jss_p5b.adapters import safe_null_request  # noqa: E402
from jss_p5b.runner_guard import authorize_preflight  # noqa: E402
from jss_p5b.schema import validate_case_result_payload  # noqa: E402


PREFLIGHT_SUBJECTS = {
    "P5B-PREFLIGHT-SAFE-NULL-S01": "JSS-S01",
    "P5B-PREFLIGHT-SAFE-NULL-S02": "JSS-S02",
    "P5B-PREFLIGHT-SAFE-NULL-S03": "JSS-S03",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="JSS P5B safe-null preflight only")
    parser.add_argument("--preflight-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--preflight-authorized", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = authorize_preflight(
        ROOT,
        preflight_id=args.preflight_id,
        run_id=args.run_id,
        cli_authorized=args.preflight_authorized,
    )
    subject_id = PREFLIGHT_SUBJECTS[args.preflight_id]
    result = adjudicate(safe_null_request(subject_id, args.run_id))
    payload = result.to_dict()
    validate_case_result_payload(payload)
    output.parent.mkdir(parents=True, exist_ok=False)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

