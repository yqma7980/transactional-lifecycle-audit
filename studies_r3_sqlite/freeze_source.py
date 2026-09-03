from __future__ import annotations

import json
import platform
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from r3sqlite.canonical import file_sha256  # noqa: E402


def _source_files() -> list[Path]:
    fixed = [
        ROOT / ".gitignore",
        ROOT / "README.md",
        ROOT / "freeze_source.py",
        ROOT / "historical_wal_reproducer.py",
        ROOT / "run_case.py",
        ROOT / "run_study.py",
        ROOT / "config" / "preregistration.json",
        ROOT / "formal" / "CONDITIONAL_PROOFS.md",
        ROOT / "formal" / "bounded_model.py",
    ]
    discovered = list((ROOT / "src").rglob("*.py")) + list((ROOT / "tests").rglob("*.py"))
    return sorted(set(fixed + discovered), key=lambda path: path.as_posix())


def _git(*args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(ROOT.parent), *args], text=True, encoding="utf-8"
    ).strip()


def main() -> int:
    output = ROOT / "config" / "source_freeze_manifest.json"
    if output.exists():
        raise SystemExit(f"refusing to overwrite frozen manifest: {output}")
    files = _source_files()
    external = sorted((ROOT / "external_tools").glob("*.zip"))
    payload = {
        "schema_version": "M2026-003-R3-SQLITE-SOURCE-FREEZE-1.0",
        "frozen_on": "2026-09-03T21:15:00+08:00",
        "git_head": _git("rev-parse", "HEAD"),
        "git_branch": _git("branch", "--show-current"),
        "python_version": sys.version,
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "sqlite_runtime_version": sqlite3.sqlite_version,
        "source_files": [
            {
                "path": path.relative_to(ROOT).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": file_sha256(path),
            }
            for path in files
        ],
        "official_binary_archives": [
            {
                "path": path.relative_to(ROOT).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": file_sha256(path),
            }
            for path in external
        ],
        "upstream_release_verifier_status": "FAILED_BEFORE_R3_EDITS",
        "upstream_release_verifier_failures_lf_archive": 153,
        "boundary": (
            "The R3 formal runs use only files indexed here. Existing v3 evidence and its "
            "stale nested manifests are not rewritten or counted as R3 validation."
        ),
    }
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    print(output)
    print(file_sha256(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
