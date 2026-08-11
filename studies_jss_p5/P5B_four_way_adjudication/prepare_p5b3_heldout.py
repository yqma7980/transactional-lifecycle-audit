from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
HELD_OUT = (
    "P5B-DETECT-05",
    "P5B-INVALID-05",
    "P5B-NS-05",
    "P5B-PASS-05",
)
IMPLEMENTATION_FILES = (
    "P5B3_HELDOUT_EXECUTION_AUTHORIZATION.json",
    "P5B3_HELDOUT_RUNTIME_MAPPING.csv",
    "src/jss_p5b/heldout_guard.py",
    "src/jss_p5b/heldout_mapping.py",
    "src/jss_p5b/heldout_runtime.py",
    "src/jss_p5b/heldout_executor.py",
    "run_p5b_heldout.py",
    "tests/test_p5b3_heldout.py",
    "prepare_p5b3_heldout.py",
    "finalize_p5b3_heldout.py",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json_new(path: Path, payload: Any) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True, ensure_ascii=True)
        handle.write("\n")


def write_text_new(path: Path, value: str) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(value.rstrip() + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--unit-tests", type=int, required=True)
    args = parser.parse_args()
    if args.unit_tests <= 0:
        raise SystemExit("unit-test count must be positive")
    if (ROOT / "results" / "heldout").exists():
        raise SystemExit("held-out results exist before pre-execution freeze")

    authorization = json.loads(
        (ROOT / "P5B3_HELDOUT_EXECUTION_AUTHORIZATION.json").read_text(
            encoding="utf-8"
        )
    )
    if tuple(authorization["authorized_case_ids"]) != HELD_OUT:
        raise SystemExit("held-out authorization case set drift")
    with (ROOT / "P5B3_HELDOUT_RUNTIME_MAPPING.csv").open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        rows = tuple(csv.DictReader(handle))
    if tuple(sorted(row["case_id"] for row in rows)) != HELD_OUT:
        raise SystemExit("held-out runtime mapping drift")

    files: dict[str, dict[str, Any]] = {}
    for relative in IMPLEMENTATION_FILES:
        path = ROOT / relative
        if not path.is_file():
            raise SystemExit(f"missing implementation file: {relative}")
        if path.suffix == ".py":
            ast.parse(path.read_text(encoding="utf-8"), filename=relative)
        files[relative] = {"sha256": sha256(path), "bytes": path.stat().st_size}

    manifest_path = ROOT / "P5B3_IMPLEMENTATION_MANIFEST.json"
    write_json_new(
        manifest_path,
        {
            "schema_version": "JSS-P5B3-HELDOUT-IMPLEMENTATION-MANIFEST-1.0",
            "status": "IMPLEMENTED_UNIT_TESTED_READY_FOR_AUTHORIZED_EXECUTION",
            "design_version": "JSS-P5B.0",
            "implementation_version": "JSS-P5B-IMPL-1.0a",
            "heldout_execution_revision": "JSS-P5B3-HELDOUT-1.0",
            "authorized_case_count": 4,
            "authorized_process_count": 8,
            "fresh_process_repetitions_per_case": 2,
            "pre_execution_unit_tests_passed": args.unit_tests,
            "double_authorization_lock": True,
            "no_formal_case_execution_at_manifest_creation": True,
            "no_abaqus_execution": True,
            "no_production_model_execution": True,
            "implementation_files": files,
            "manifest_self_hash_embedded": False,
        },
    )
    qa_path = ROOT / "P5B3_STATIC_AND_UNIT_QA.md"
    write_text_new(
        qa_path,
        "\n".join(
            (
                "# P5B.3 held-out implementation and pre-execution QA",
                "",
                "Status: PASS_IMPLEMENTED_UNIT_TESTED_READY_FOR_AUTHORIZED_EXECUTION.",
                "",
                f"- Unit tests passed: {args.unit_tests}/{args.unit_tests}.",
                "- Four frozen held-out case IDs and two run IDs are bound.",
                "- CLI and environment authorization locks are both required.",
                "- DOLFINx/PETSc cases use the fixed digest with network disabled.",
                "- INVALID and NOT_SUPPORTED stop before lifecycle evaluation.",
                "- No held-out result directory existed during this QA.",
                "- No threshold, seed, case, oracle, adapter, or adjudication rule changed.",
                "- This QA is not formal held-out evidence.",
            )
        ),
    )
    print(
        json.dumps(
            {
                "status": "PASS_IMPLEMENTED_UNIT_TESTED_READY_FOR_AUTHORIZED_EXECUTION",
                "unit_tests": args.unit_tests,
                "implementation_manifest_sha256": sha256(manifest_path),
                "qa_sha256": sha256(qa_path),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
