from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from p6r_loader import validate_raw_evidence, validate_raw_schemas


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="P6R hash/schema-only preflight")
    parser.add_argument("--ncs-root", required=True)
    parser.add_argument("--study-root", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args(argv)
    report = validate_raw_evidence(Path(args.ncs_root), Path(args.study_root))
    report.update(validate_raw_schemas(Path(args.ncs_root), Path(args.study_root)))
    report.update(
        {
            "status": "PASS_READ_ONLY_HASH_AND_SCHEMA_PREFLIGHT",
            "formal_projection_executed": False,
            "new_fe_solve_executed": False,
            "abaqus_used": False,
        }
    )
    Path(args.report).write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

