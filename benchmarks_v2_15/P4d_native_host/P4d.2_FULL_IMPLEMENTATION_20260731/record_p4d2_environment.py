from __future__ import annotations

import argparse
import json
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parent
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    output = pathlib.Path(args.output)
    if output.exists():
        raise SystemExit(f"refusing to overwrite {output}")
    from p4d_environment import collect_environment

    payload = collect_environment(args.run_id)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
