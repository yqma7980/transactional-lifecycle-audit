from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
from pathlib import Path


HERE = Path(__file__).resolve().parent
BASE = HERE / "build_p5_evidence_sync.py"
SPEC = importlib.util.spec_from_file_location("p5_sync_base", BASE)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load evidence-sync base module")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def verify_sources_sorted() -> dict:
    mismatches = []
    for path, expected in MODULE.EXPECTED.items():
        actual = MODULE.sha256(path)
        if actual != expected:
            mismatches.append({"path": str(path), "expected": expected, "actual": actual})

    manifest_path = MODULE.FORMAL / "final" / "execution_manifest.json"
    manifest = MODULE.read_json(manifest_path)
    aggregate_rows = []
    for item in manifest["files"]:
        path = MODULE.FORMAL / item["path"]
        actual = MODULE.sha256(path)
        if actual != item["sha256"]:
            mismatches.append(
                {"path": str(path), "expected": item["sha256"], "actual": actual}
            )
        aggregate_rows.append((item["path"], actual))

    lines = [f"{path}|{digest}" for path, digest in sorted(aggregate_rows)]
    aggregate = hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()
    if aggregate != MODULE.RAW_AGGREGATE_EXPECTED:
        mismatches.append(
            {
                "path": "formal_raw_aggregate",
                "expected": MODULE.RAW_AGGREGATE_EXPECTED,
                "actual": aggregate,
            }
        )
    if mismatches:
        raise RuntimeError(json.dumps(mismatches, indent=2))
    return {
        "protected_hash_gate": "PASS",
        "formal_raw_file_count": len(manifest["files"]),
        "formal_raw_aggregate_sha256": aggregate,
    }


def refresh_output_manifest() -> None:
    out = MODULE.OUT
    wrapper_target = out / Path(__file__).name
    shutil.copy2(Path(__file__), wrapper_target)
    manifest_path = out / "P5_source_manifest.json"
    manifest = MODULE.read_json(manifest_path)
    outputs = []
    for path in sorted(out.iterdir(), key=lambda p: p.name.lower()):
        if not path.is_file() or path.name == manifest_path.name:
            continue
        outputs.append(
            {"path": path.name, "bytes": path.stat().st_size, "sha256": MODULE.sha256(path)}
        )
    manifest["outputs"] = outputs
    MODULE.dump_json(manifest_path, manifest)


if __name__ == "__main__":
    MODULE.verify_sources = verify_sources_sorted
    MODULE.main()
    refresh_output_manifest()
    print(json.dumps({"status": "CORRECTED_SORTED_AGGREGATE_WRAPPER_COMPLETE"}, indent=2))
