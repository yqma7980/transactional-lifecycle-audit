from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "release_manifest_v6_0_0.json"
CHECKSUMS = ROOT / "SHA256SUMS_v6_0_0.txt"
EXCLUDED = {MANIFEST.name, CHECKSUMS.name}


def indexed_files() -> list[tuple[str, str, str]]:
    raw = subprocess.check_output(
        ["git", "ls-files", "-s", "-z"], cwd=ROOT
    )
    records: list[tuple[str, str, str]] = []
    for item in raw.split(b"\0"):
        if not item:
            continue
        metadata, encoded_path = item.split(b"\t", 1)
        mode, object_id, stage = metadata.decode("ascii").split()
        if stage != "0":
            raise RuntimeError(f"unmerged index entry: {encoded_path!r}")
        path = encoded_path.decode("utf-8", errors="surrogateescape")
        if path not in EXCLUDED:
            records.append((path, mode, object_id))
    return sorted(records)


def read_blobs(object_ids: list[str]) -> dict[str, bytes]:
    unique = list(dict.fromkeys(object_ids))
    request = "".join(f"{object_id}\n" for object_id in unique).encode("ascii")
    process = subprocess.Popen(
        ["git", "cat-file", "--batch"],
        cwd=ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    output, errors = process.communicate(request)
    if process.returncode:
        raise RuntimeError(errors.decode("utf-8", errors="replace"))

    blobs: dict[str, bytes] = {}
    offset = 0
    for requested in unique:
        end = output.index(b"\n", offset)
        header = output[offset:end].decode("ascii")
        object_id, object_type, raw_size = header.split()
        if object_type != "blob" or object_id != requested:
            raise RuntimeError(f"unexpected cat-file header: {header}")
        size = int(raw_size)
        start = end + 1
        blobs[requested] = output[start : start + size]
        offset = start + size + 1
    return blobs


def main() -> int:
    records = indexed_files()
    blobs = read_blobs([object_id for _, _, object_id in records])
    entries = []
    checksum_lines = []
    for path, mode, object_id in records:
        payload = blobs[object_id]
        digest = hashlib.sha256(payload).hexdigest()
        entries.append(
            {
                "path": path,
                "bytes": len(payload),
                "sha256": digest,
                "git_mode": mode,
                "git_blob": object_id,
            }
        )
        checksum_lines.append(f"{digest}  {path}")

    payload_tree = subprocess.check_output(
        ["git", "write-tree"], cwd=ROOT, text=True
    ).strip()
    manifest = {
        "schema_version": "TLA-RELEASE-MANIFEST-6.0",
        "release": "v6.0.0",
        "generated_on": "2026-09-04",
        "byte_authority": "staged Git index blobs",
        "payload_tree_sha1": payload_tree,
        "indexed_files": len(entries),
        "excluded_self_referential_files": sorted(EXCLUDED),
        "files": entries,
    }
    MANIFEST.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    CHECKSUMS.write_text(
        "\n".join(checksum_lines) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"payload_tree_sha1={payload_tree}")
    print(f"indexed_files={len(entries)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
