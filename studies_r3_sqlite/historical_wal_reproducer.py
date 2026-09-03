from __future__ import annotations

import argparse
import csv
import json
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
SQL_SCRIPT = r"""
.bail on
.open test.db
PRAGMA synchronous = NORMAL;
PRAGMA page_size = 4096;
PRAGMA auto_vacuum = FULL;
PRAGMA journal_mode = WAL;
PRAGMA cache_size = 1;
CREATE TABLE t1 (i INTEGER PRIMARY KEY, s TEXT);
PRAGMA wal_checkpoint;
INSERT INTO t1 (i, s) VALUES (0, randomblob(4096));
INSERT INTO t1 (i, s) VALUES (1, randomblob(4096));
SAVEPOINT one;
INSERT INTO t1 (i, s) VALUES (2, randomblob(4096));
INSERT INTO t1 (i, s) VALUES (3, randomblob(4096));
INSERT INTO t1 (i, s) VALUES (4, randomblob(4096));
INSERT INTO t1 (i, s) VALUES (5, randomblob(4096));
INSERT INTO t1 (i, s) VALUES (6, randomblob(4096));
INSERT INTO t1 (i, s) VALUES (7, randomblob(4096));
INSERT INTO t1 (i, s) VALUES (8, randomblob(4096));
ROLLBACK TO one;
RELEASE one;
INSERT INTO t1 (i, s) VALUES (9, randomblob(4096));
.shell copy /Y test.db test2.db >NUL
.shell copy /Y test.db-wal test2.db-wal >NUL
.open test2.db
.print __R3_RESULT_BEGIN__
PRAGMA integrity_check;
SELECT count(*) FROM t1;
.print __R3_RESULT_END__
.quit
""".strip() + "\n"


def _parse(stdout: str) -> tuple[str | None, int | None]:
    lines = [line.strip() for line in stdout.splitlines()]
    try:
        start = lines.index("__R3_RESULT_BEGIN__") + 1
        end = lines.index("__R3_RESULT_END__")
    except ValueError:
        return None, None
    payload = [line for line in lines[start:end] if line]
    integrity = payload[0] if payload else None
    count = int(payload[1]) if len(payload) > 1 and payload[1].isdigit() else None
    return integrity, count


def _run(executable: Path, version: str, index: int, root: Path) -> dict[str, Any]:
    run_dir = root / "runs" / version / f"run-{index:02d}"
    run_dir.mkdir(parents=True, exist_ok=False)
    process = subprocess.run(
        [str(executable)],
        input=SQL_SCRIPT,
        cwd=run_dir,
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )
    (run_dir / "stdout.log").write_text(process.stdout, encoding="utf-8", newline="\n")
    (run_dir / "stderr.log").write_text(process.stderr, encoding="utf-8", newline="\n")
    (run_dir / "reproducer.sql").write_text(SQL_SCRIPT, encoding="utf-8", newline="\n")
    integrity, count = _parse(process.stdout)
    return {
        "runtime": version,
        "run_index": index,
        "return_code": process.returncode,
        "integrity_check": integrity,
        "row_count": count,
        "parse_success": integrity is not None and count is not None,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "config" / "preregistration.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite existing output: {args.output}")
    args.output.mkdir(parents=True)
    config = json.loads(args.config.read_text(encoding="utf-8"))["historical_case"]
    tools = {
        "3.50.1": ROOT / "external_tools" / "sqlite-3500100" / "sqlite3.exe",
        "3.50.2": ROOT / "external_tools" / "sqlite-3500200" / "sqlite3.exe",
    }
    rows: list[dict[str, Any]] = []
    for version in (config["vulnerable_runtime"], config["fixed_runtime"]):
        for index in range(1, int(config["fresh_processes_per_version"]) + 1):
            rows.append(_run(tools[version], version, index, args.output))
    with (args.output / "historical_results.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=tuple(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    vulnerable = [row for row in rows if row["runtime"] == config["vulnerable_runtime"]]
    fixed = [row for row in rows if row["runtime"] == config["fixed_runtime"]]
    reproduced = (
        all(row["return_code"] == 0 and row["integrity_check"] == "ok" for row in rows)
        and all(row["row_count"] == config["expected_vulnerable_row_count"] for row in vulnerable)
        and all(row["row_count"] == config["expected_fixed_row_count"] for row in fixed)
    )
    summary = {
        "schema_version": "M2026-003-R3-SQLITE-HISTORICAL-1.0",
        "case_id": config["case_id"],
        "official_forum_post": config["official_forum_post"],
        "runs": len(rows),
        "vulnerable_counts": [row["row_count"] for row in vulnerable],
        "fixed_counts": [row["row_count"] for row in fixed],
        "historical_defect_reproduced": reproduced,
        "interpretation": (
            "official defect differential reproduced"
            if reproduced
            else "NOT_REPRODUCED; retained without favorable rerun"
        ),
    }
    (args.output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

