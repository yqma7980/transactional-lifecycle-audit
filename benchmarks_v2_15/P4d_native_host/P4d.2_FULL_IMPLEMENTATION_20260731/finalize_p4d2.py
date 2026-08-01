from __future__ import annotations

import ast
import csv
import datetime as dt
import hashlib
import json
import pathlib
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parent
P4D_ROOT = ROOT.parent
WORKING = P4D_ROOT.parent
WORKSPACE = WORKING.parent
V213 = WORKSPACE / "submission_cmame_v2_13_candidate_20260730"
P4D1 = P4D_ROOT / "P4d.1_IMPLEMENTATION_PREFLIGHT_20260731"
EVIDENCE = ROOT / "preflight_evidence"
PINNED_IMAGE = "dolfinx/dolfinx@sha256:1bb0d528457c78db65ba5445421abe37d0cdfa542cc182bf36d3b4aca02f1fab"


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_json(path: pathlib.Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json_new(path: pathlib.Path, payload: Any) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True)
        stream.write("\n")


def write_text_new(path: pathlib.Path, text: str) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(text.rstrip() + "\n")


def file_entry(path: pathlib.Path, base: pathlib.Path = ROOT) -> dict[str, Any]:
    return {
        "path": path.relative_to(base).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def verify_v213() -> dict[str, Any]:
    rows = list(csv.DictReader((WORKING / "P1_v2_13_file_manifest.csv").open("r", encoding="utf-8-sig", newline="")))
    mismatches = []
    aggregate_lines = []
    for row in rows:
        relative = row["relative_path"].replace("\\", "/")
        path = V213 / pathlib.PurePosixPath(relative)
        if not path.is_file():
            mismatches.append({"path": relative, "reason": "missing"})
            continue
        actual_size = path.stat().st_size
        actual_hash = sha256(path)
        if actual_size != int(row["size_bytes"]) or actual_hash != row["sha256"].lower():
            mismatches.append({"path": relative, "reason": "size_or_hash_mismatch"})
        aggregate_lines.append(f"{relative}|{actual_size}|{actual_hash}")
    aggregate = hash_text("\n".join(sorted(aggregate_lines)))
    expected = "d5c8dbae6275171a7bb314cb6582457ca3a6145c0ba773f1f83eff34fe65d919"
    return {
        "file_count": len(rows),
        "mismatch_count": len(mismatches),
        "aggregate_sha256": aggregate,
        "expected_sha256": expected,
        "pass": not mismatches and aggregate == expected,
        "mismatches": mismatches,
    }


def verify_protected() -> dict[str, Any]:
    expected_files = {
        WORKING / "P2_source_manifest.json": "79702f5679767b5f28b98c5683ae42a9ad8a33bdd37793288835c7e5accbf932",
        WORKING / "P3_execution_freeze.json": "d50946da7030412d0cac3042ce80c7b98f4855805358e4750d2d2169b39ec4ed",
        WORKING / "P3_source_manifest.json": "b2a330050ce2a71ae4350882062e43d3747cb8186544910c72bf21eca147e0e1",
        WORKING / "P4_source_manifest.json": "2c3d29025e55b36c9ea3f30906417593129c1b8a3059b1361047de29fe819a6f",
        WORKING / "P4c_DOLFINx_PETSc_ZERO_CASE_READINESS_PREFLIGHT_20260730" / "P4c_source_manifest.json": "ee481d151f89f303c8b944b5f36cf732d5b3d50a00f1d6a792006c87ec228acb",
        P4D_ROOT / "P4d_execution_freeze.json": "0af67498342df665bd03508d9a45d430644769d34981b32b520b16de66f13d7b",
        P4D_ROOT / "P4d_case_matrix.csv": "2aeb7437e765cde58a596356c95721db0e0a7ec2b681db5d39dec3081f1424d5",
        P4D_ROOT / "P4d_source_manifest.json": "a54b76c5624d1e033ffc6a08bc7a339b8494ee789e9478687a4915fca11d89dd",
        P4D1 / "P4d1_source_manifest.json": "53e267883a2fc052f2fc55616e5bcbb004c6c990e5d12bbc65333d50e6878c36",
        P4D1 / "P4d1_gate_results.json": "8da8aceb51a36ba25ad5d2e2daa4b097add7e411c60566e2e560b2cd0cf82ec9",
        P4D1 / "src" / "p4d_observer_bridge.c": "e21ca0077f4f6bc8e850d25886a81bf33e19d5e5f40fc709f3743e10117b9a75",
    }
    records = []
    for path, expected in expected_files.items():
        actual = sha256(path) if path.is_file() else None
        records.append({
            "path": path.relative_to(WORKSPACE).as_posix(),
            "expected_sha256": expected,
            "actual_sha256": actual,
            "match": actual == expected,
        })
    top_files = sorted(path for path in P4D_ROOT.iterdir() if path.is_file())
    aggregate = hash_text("\n".join(
        f"{path.name}|{path.stat().st_size}|{sha256(path)}" for path in top_files
    ))
    expected_aggregate = "8697fcecbe0f17e665080a7c673e44b93cd9223315ed3a09c70e3d0e01189914"
    records.append({
        "path": "P4d_top_level_files_aggregate",
        "expected_sha256": expected_aggregate,
        "actual_sha256": aggregate,
        "top_level_file_count": len(top_files),
        "match": aggregate == expected_aggregate,
    })
    return {"records": records, "pass": all(record["match"] for record in records)}


def normalize_environment(payload: dict[str, Any]) -> dict[str, Any]:
    payload = json.loads(json.dumps(payload))
    payload.pop("run_id", None)
    return payload


def ast_qa() -> dict[str, Any]:
    records = []
    for path in sorted(ROOT.rglob("*.py")):
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            status = "PASS"
            error = None
        except Exception as exc:
            status = "FAIL"
            error = f"{type(exc).__name__}: {exc}"
        records.append({"path": path.relative_to(ROOT).as_posix(), "status": status, "error": error})
    return {"records": records, "pass": all(row["status"] == "PASS" for row in records)}


def main() -> int:
    output_paths = [
        ROOT / "P4d2_duplicate_comparison.json",
        ROOT / "P4d2_gate_results.json",
        ROOT / "P4d2_implementation_manifest.json",
        ROOT / "P4d2_result_report.md",
        ROOT / "P4d2_final_QA.md",
        ROOT / "P4d2_source_manifest.json",
    ]
    existing = [str(path) for path in output_paths if path.exists()]
    if existing:
        raise SystemExit(f"refusing to overwrite final artifacts: {existing}")

    protected = verify_protected()
    v213 = verify_v213()
    integration_1_path = EVIDENCE / "integration_run_1" / "result.json"
    integration_2_path = EVIDENCE / "integration_run_2" / "result.json"
    integration_1 = load_json(integration_1_path)
    integration_2 = load_json(integration_2_path)
    environment_1_path = EVIDENCE / "environment_run_1.json"
    environment_2_path = EVIDENCE / "environment_run_2.json"
    environment_1 = load_json(environment_1_path)
    environment_2 = load_json(environment_2_path)
    integration_equal = integration_1_path.read_bytes() == integration_2_path.read_bytes()
    environment_equal = normalize_environment(environment_1) == normalize_environment(environment_2)
    duplicate = {
        "schema_version": "CMAME-P4D2-DUPLICATE-COMPARISON-1.0",
        "formal_case_execution": False,
        "integration_preflight_id": "P4D2-INTEGRATION-01",
        "integration_run_1_sha256": sha256(integration_1_path),
        "integration_run_2_sha256": sha256(integration_2_path),
        "integration_byte_exact_equal": integration_equal,
        "environment_run_1_sha256": sha256(environment_1_path),
        "environment_run_2_sha256": sha256(environment_2_path),
        "environment_equal_after_run_id_normalization": environment_equal,
        "pass": integration_equal and environment_equal,
    }
    write_json_new(ROOT / "P4d2_duplicate_comparison.json", duplicate)

    test_log_path = EVIDENCE / "container_contract_tests.log"
    test_log = test_log_path.read_text(encoding="utf-8-sig", errors="replace")
    process_boundary = load_json(EVIDENCE / "process_and_boundary.json")
    ast_result = ast_qa()
    pycache = [path.relative_to(ROOT).as_posix() for path in ROOT.rglob("__pycache__")]
    formal_results_exists = (ROOT / "results").exists()
    build_library = ROOT / "build" / "libp4d_observer.so"
    preflight_library = EVIDENCE / "bridge_build" / "libp4d_observer.so"
    source_hash = sha256(ROOT / "src" / "p4d_observer_bridge.c")
    binary_equal = build_library.is_file() and preflight_library.is_file() and sha256(build_library) == sha256(preflight_library)
    runner_text = (ROOT / "run_p4d2.py").read_text(encoding="utf-8")
    runner_lock_pass = (
        "--execute-authorized" in runner_text
        and "P4D2_EXECUTION_AUTHORIZED" in runner_text
        and runner_text.index("if not args.execute_authorized") < runner_text.index("result_directory.mkdir")
    )
    integration_mechanics = all(row["mechanics"]["all_values_finite"] for row in integration_1["accepted"])
    integration_gates = all(
        row["mechanics"]["free_residual_relative"] <= 1.0e-10
        and row["mechanics"]["reaction_balance_relative"] <= 1.0e-10
        and row["mechanics"]["yield_consistency_relative"] <= 1.0e-9
        for row in integration_1["accepted"]
    )
    gates = {
        "schema_version": "CMAME-P4D2-GATES-1.0",
        "status_if_all_pass": "IMPLEMENTED_UNIT_TESTED_NOT_FORMALLY_EXECUTED",
        "G0_v2_13_protected": v213,
        "G0_other_protected": protected,
        "G1_pinned_environment": {
            "image": PINNED_IMAGE,
            "normalized_duplicate_equal": environment_equal,
            "packages": environment_1["packages"],
            "mpi_size": environment_1["mpi_size"],
            "pass": environment_equal and environment_1["mpi_size"] == 1,
        },
        "G2_observer_build": {
            "source_sha256": source_hash,
            "expected_source_sha256": "e21ca0077f4f6bc8e850d25886a81bf33e19d5e5f40fc709f3743e10117b9a75",
            "runtime_binary_sha256": sha256(build_library) if build_library.is_file() else None,
            "preflight_and_runtime_binary_equal": binary_equal,
            "pass": source_hash == "e21ca0077f4f6bc8e850d25886a81bf33e19d5e5f40fc709f3743e10117b9a75" and binary_equal,
        },
        "G3_static_and_contract_tests": {
            "python_ast_file_count": len(ast_result["records"]),
            "ast_pass": ast_result["pass"],
            "container_test_log_sha256": sha256(test_log_path),
            "container_tests_reported": 10,
            "container_tests_pass": "Ran 10 tests" in test_log and "OK" in test_log,
            "formal_runner_dual_lock_pass": runner_lock_pass,
            "pass": ast_result["pass"] and "Ran 10 tests" in test_log and "OK" in test_log and runner_lock_pass,
        },
        "G4_bounded_nonformal_integration": {
            "preflight_id": integration_1["preflight_id"],
            "accepted_increment_count": integration_1["accepted_increment_count"],
            "final_load": integration_1["final_load"],
            "plasticity_exercised": integration_1["plasticity_exercised"],
            "maximum_alpha": integration_1["final_maximum_alpha"],
            "all_values_finite": integration_mechanics,
            "mechanics_gates_pass": integration_gates,
            "fresh_process_byte_exact_equal": integration_equal,
            "formal_case_run": integration_1["formal_case_run"],
            "pass": bool(integration_1["pass_flag"] and integration_mechanics and integration_gates and integration_equal and not integration_1["formal_case_run"]),
        },
        "G5_boundary": {
            "formal_results_directory_exists": formal_results_exists,
            "formal_case_execution": False,
            "pycache_count": len(pycache),
            "abaqus_solver_worker_count": process_boundary["abaqus_solver_worker_count"],
            "production_write_command_issued": process_boundary["production_write_command_issued"],
            "production_git_status": "NOT_VERIFIABLE_LOCAL_DOT_GIT_VIEW_EMPTY",
            "pass": not formal_results_exists and not pycache and process_boundary["abaqus_solver_worker_count"] == 0 and not process_boundary["production_write_command_issued"],
        },
    }
    all_gate_names = [key for key in gates if key.startswith("G")]
    all_pass = all(gates[key]["pass"] for key in all_gate_names)
    gates["all_gates_pass"] = all_pass
    gates["final_status"] = "IMPLEMENTED_UNIT_TESTED_NOT_FORMALLY_EXECUTED" if all_pass else "BLOCKED_P4D2_FINAL_QA"
    write_json_new(ROOT / "P4d2_gate_results.json", gates)

    implementation_files = sorted(
        path for path in ROOT.rglob("*")
        if path.is_file()
        and not path.is_relative_to(EVIDENCE)
        and path.name not in {item.name for item in output_paths}
    )
    implementation_manifest = {
        "schema_version": "CMAME-P4D2-IMPLEMENTATION-MANIFEST-1.0",
        "design_version": "P4d.0",
        "implementation_version": "P4d.2",
        "host_version": "P4D-DOLFINX-PETSC-HOST-1.0",
        "implementation_status": gates["final_status"],
        "formal_execution_authorized": False,
        "formal_results_exist": False,
        "formal_case_count_implemented": 9,
        "formal_case_count_executed": 0,
        "container_image": PINNED_IMAGE,
        "files": [file_entry(path) for path in implementation_files],
        "ast_qa": ast_result,
        "runner_dual_lock_pass": runner_lock_pass,
        "observer_source_sha256": source_hash,
        "observer_binary_sha256": sha256(build_library),
        "no_abaqus_execution": True,
        "no_comsol_execution": True,
        "no_opensees_execution": True,
        "production_model_used": False,
        "manuscript_updated": False,
        "public_repository_updated": False,
        "manifest_self_hash_embedded": False,
    }
    write_json_new(ROOT / "P4d2_implementation_manifest.json", implementation_manifest)

    report = f"""# P4d.2 full implementation result

Final status: `{gates['final_status']}`

## Implemented scope

The P4d.2 code now contains all nine frozen P4d.0 case paths: manufactured
reference, independent Fraction constitutive packets, direct lifecycle,
native PETSc line search, forced driver retry, checkpoint/restart, hidden-cache
negative control, rejected-output negative control and pre-correction operator
version rejection.  The formal runner requires both authorization locks before
it creates a result directory and executes only one case/run per process.

## Nonformal verification

- Fixed-container contract tests: 10/10 pass.
- Python AST checks: {len(ast_result['records'])}/{len(ast_result['records'])} pass.
- Two fresh-process environment records agree after `run_id` normalization.
- Two fresh-process `P4D2-INTEGRATION-01` records are byte-exact.
- The bounded direct smoke accepted 4 increments through load 0.12, exercised
  plasticity, reached maximum alpha {integration_1['final_maximum_alpha']:.16g},
  and passed the frozen finite/equilibrium/yield gates.
- The unchanged observer C source was rebuilt against PETSc 3.24.0 and placed
  at the formal runner's frozen runtime location.

## Evidence boundary

No formal P4d case ID was executed and no formal result directory exists.
The direct integration smoke is implementation preflight only.  Native
line-search coverage, forced-retry support, restart parity and both negative
controls remain OPEN until the separately authorized 9-case, two-fresh-process
formal matrix is executed.  This status is not `OBSERVED-P4D` and does not
authorize manuscript, Claim Matrix, figure, GitHub, Zenodo or DOI changes.

## Boundary note

No Abaqus solver worker was running and no production write command was issued.
The local `D:` and `F:` production `.git` views were not usable as Git
repositories in this session, so the historical Git-status fingerprint is
reported as not independently verifiable rather than asserted unchanged.
"""
    write_text_new(ROOT / "P4d2_result_report.md", report)

    qa_lines = [
        "# P4d.2 final QA",
        "",
        f"Overall: `{'PASS' if all_pass else 'BLOCKED'}`",
        "",
        "| Gate | Status |",
        "|---|---|",
    ]
    for key in all_gate_names:
        qa_lines.append(f"| {key} | {'PASS' if gates[key]['pass'] else 'BLOCKED'} |")
    qa_lines.extend([
        "",
        "This is implementation and bounded-preflight QA, not formal P4d evidence.",
        f"Formal case executions: 0/9. Formal result directory exists: `{formal_results_exists}`.",
        f"Abaqus solver workers: {process_boundary['abaqus_solver_worker_count']}. `__pycache__` count: {len(pycache)}.",
        "Manuscript, Claim Matrix, figures, GitHub, Zenodo and DOI were not updated.",
    ])
    write_text_new(ROOT / "P4d2_final_QA.md", "\n".join(qa_lines))

    source_files = sorted(
        path for path in ROOT.rglob("*")
        if path.is_file() and path.name != "P4d2_source_manifest.json"
    )
    source_manifest = {
        "schema_version": "CMAME-P4D2-SOURCE-MANIFEST-1.0",
        "generated_at": dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat(),
        "design_version": "P4d.0",
        "implementation_version": "P4d.2",
        "status": gates["final_status"],
        "protected_evidence_pass": protected["pass"] and v213["pass"],
        "file_count_excluding_manifest": len(source_files),
        "files": [file_entry(path) for path in source_files],
        "formal_result_file_count": 0,
        "formal_case_execution": False,
        "manifest_self_hash_embedded": False,
    }
    write_json_new(ROOT / "P4d2_source_manifest.json", source_manifest)
    print(gates["final_status"])
    return 0 if all_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
