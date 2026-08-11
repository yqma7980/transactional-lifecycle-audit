from __future__ import annotations

import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parent
INDEX = ROOT / "SHA256SUMS_v3_0_0.txt"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    failures: list[str] = []
    checked = 0
    for raw in INDEX.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        expected, relative = raw.split("  ", 1)
        path = ROOT / relative
        if not path.is_file():
            failures.append(f"MISSING {relative}")
            continue
        actual = sha256(path)
        if actual.lower() != expected.lower():
            failures.append(f"HASH {relative}: {actual} != {expected}")
        checked += 1
    print(f"indexed_files={checked}")
    print(f"failures={len(failures)}")
    for failure in failures:
        print(failure)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
