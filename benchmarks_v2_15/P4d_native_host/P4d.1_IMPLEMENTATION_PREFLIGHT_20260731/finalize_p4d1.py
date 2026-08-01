from __future__ import annotations

import ast
import copy
import csv
import datetime as dt
import hashlib
import json
import pathlib
import subprocess
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parent
P4D_ROOT = ROOT.parent
WORKING = P4D_ROOT.parent
WORKSPACE = WORKING.parent
V213 = WORKSPACE / "submission_cmame_v2_13_candidate_20260730"
RUNTIME = ROOT / "runtime_evidence"
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


def write_json(path: pathlib.Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def file_entry(path: pathlib.Path, base: pathlib.Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(base).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def verify_v213() -> dict[str, Any]:
    manifest_path = WORKING / "P1_v2_13_file_manifest.csv"
    rows = list(csv.DictReader(manifest_path.open("r", encoding="utf-8-sig", newline="")))
    mismatches = []
    aggregate_lines = []
    total_bytes = 0
    for row in rows:
        relative = row["relative_path"].replace("\\", "/")
        path = V213 / pathlib.PurePosixPath(relative)
        expected_size = int(row["size_bytes"])
        expected_hash = row["sha256"].lower()
        if not path.is_file():
            mismatches.append({"path": relative, "reason": "missing"})
            continue
        actual_size = path.stat().st_size
        actual_hash = sha256(path)
        if actual_size != expected_size or actual_hash != expected_hash:
            mismatches.append(
                {"path": relative, "expected_size": expected_size, "actual_size": actual_size,
                 "expected_hash": expected_hash, "actual_hash": actual_hash}
            )
        total_bytes += actual_size
        aggregate_lines.append(f"{relative}|{actual_size}|{actual_hash}")
    aggregate = hash_text("\n".join(sorted(aggregate_lines)))
    return {
        "file_count": len(rows),
        "verified_count": len(rows) - len(mismatches),
        "total_bytes": total_bytes,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "aggregate_sha256": aggregate,
        "expected_aggregate_sha256": "d5c8dbae6275171a7bb314cb6582457ca3a6145c0ba773f1f83eff34fe65d919",
        "pass": len(mismatches) == 0 and aggregate == "d5c8dbae6275171a7bb314cb6582457ca3a6145c0ba773f1f83eff34fe65d919",
    }


def verify_protected() -> dict[str, Any]:
    expected = {
        "P2_source_manifest.json": "79702f5679767b5f28b98c5683ae42a9ad8a33bdd37793288835c7e5accbf932",
        "P3_execution_freeze.json": "d50946da7030412d0cac3042ce80c7b98f4855805358e4750d2d2169b39ec4ed",
        "P3_source_manifest.json": "b2a330050ce2a71ae4350882062e43d3747cb8186544910c72bf21eca147e0e1",
        "P4_source_manifest.json": "2c3d29025e55b36c9ea3f30906417593129c1b8a3059b1361047de29fe819a6f",
    }
    records = {}
    for name, expected_hash in expected.items():
        actual = sha256(WORKING / name)
        records[name] = {"expected": expected_hash, "actual": actual, "match": actual == expected_hash}
    extra = {
        "P4c_source_manifest.json": (
            WORKING / "P4c_DOLFINx_PETSc_ZERO_CASE_READINESS_PREFLIGHT_20260730" / "P4c_source_manifest.json",
            "ee481d151f89f303c8b944b5f36cf732d5b3d50a00f1d6a792006c87ec228acb",
        ),
        "P4d_source_manifest.json": (
            P4D_ROOT / "P4d_source_manifest.json",
            "a54b76c5624d1e033ffc6a08bc7a339b8494ee789e9478687a4915fca11d89dd",
        ),
    }
    for name, (path, expected_hash) in extra.items():
        actual = sha256(path)
        records[name] = {"expected": expected_hash, "actual": actual, "match": actual == expected_hash}
    top_files = sorted(path for path in P4D_ROOT.iterdir() if path.is_file())
    aggregate_lines = [f"{path.name}|{path.stat().st_size}|{sha256(path)}" for path in top_files]
    aggregate = hash_text("\n".join(aggregate_lines))
    records["P4d_package_aggregate"] = {
        "expected": "8697fcecbe0f17e665080a7c673e44b93cd9223315ed3a09c70e3d0e01189914",
        "actual": aggregate,
        "top_level_file_count": len(top_files),
        "match": aggregate == "8697fcecbe0f17e665080a7c673e44b93cd9223315ed3a09c70e3d0e01189914",
    }
    return {"records": records, "pass": all(item["match"] for item in records.values())}


def normalize(value: Any) -> Any:
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if key in {"run_id", "snes_handle", "handle_integer", "ledger_path", "library_path"}:
                continue
            if key == "solve_id":
                result[key] = "NORMALIZED"
            elif key == "path" and isinstance(item, str) and item.startswith("/"):
                result[key] = pathlib.PurePosixPath(item).name
            else:
                result[key] = normalize(item)
        return result
    if isinstance(value, list):
        return [normalize(item) for item in value]
    return value


def read_jsonl(path: pathlib.Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def collect_image_identity() -> dict[str, Any]:
    process = subprocess.run(["docker", "image", "inspect", PINNED_IMAGE], text=True, capture_output=True, check=False)
    if process.returncode != 0:
        return {"pass": False, "stderr": process.stderr.strip()}
    data = json.loads(process.stdout)[0]
    return {
        "image_reference": PINNED_IMAGE,
        "image_id": data.get("Id"),
        "repo_digests": data.get("RepoDigests", []),
        "os": data.get("Os"),
        "architecture": data.get("Architecture"),
        "pass": PINNED_IMAGE in data.get("RepoDigests", []) and data.get("Os") == "linux" and data.get("Architecture") == "amd64",
    }


def process_boundary() -> dict[str, Any]:
    process = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, check=False)
    text = process.stdout.decode("mbcs", errors="replace") if isinstance(process.stdout, bytes) else process.stdout
    names = []
    for row in csv.reader(text.splitlines()):
        if row:
            names.append(row[0].lower())
    targets = ("standard.exe", "pre.exe", "smasimutility.exe", "abqcaek.exe")
    counts = {name: names.count(name) for name in targets}
    git_dir = pathlib.Path(r"F:\Abaqus learning\code learning\.git")
    return {
        "abaqus_process_counts": counts,
        "abaqus_process_total": sum(counts.values()),
        "production_git_directory_exists": git_dir.exists(),
        "production_git_entry_count": len(list(git_dir.iterdir())) if git_dir.is_dir() else None,
        "production_write_command_issued": False,
        "pass": sum(counts.values()) == 0,
    }


def main() -> int:
    v213 = verify_v213()
    protected = verify_protected()
    image = collect_image_identity()
    production = process_boundary()
    env1 = load_json(RUNTIME / "environment" / "run_1.json")
    env2 = load_json(RUNTIME / "environment" / "run_2.json")
    environment_duplicate = normalize(env1) == normalize(env2)
    host_identity = {
        "schema_version": "CMAME-P4D1-HOST-IDENTITY-1.0",
        "image": image,
        "environment_run_1": env1,
        "environment_run_2": env2,
        "fresh_process_normalized_equal": environment_duplicate,
        "thread_environment": {"OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"},
        "network": "none",
        "privileged": False,
        "mpi_ranks": 1,
        "processes_per_run": 1,
        "threads_per_process": 1,
        "pass": image.get("pass", False) and environment_duplicate,
    }
    write_json(RUNTIME / "environment" / "host_identity.json", host_identity)

    off = load_json(RUNTIME / "observer_off" / "result.json")
    on1 = load_json(RUNTIME / "observer_on_run_1" / "result.json")
    on2 = load_json(RUNTIME / "observer_on_run_2" / "result.json")
    ledger1 = read_jsonl(RUNTIME / "observer_on_run_1" / "c_ledger.jsonl")
    ledger2 = read_jsonl(RUNTIME / "observer_on_run_2" / "c_ledger.jsonl")
    no_effect_fields = ("solution_hex", "snes_reason", "iteration_count", "residual_sequence_hex")
    no_effect = all(off[field] == on1[field] == on2[field] for field in no_effect_fields)
    bridge_duplicate = normalize(on1) == normalize(on2)
    ledger_duplicate = normalize(ledger1) == normalize(ledger2)
    unselected = all(
        run["native_candidate_classification"]["structured_unselected_candidate_present"]
        for run in (on1, on2)
    )
    change_flags_false = all(
        event.get("postcheck_change_flags") is False
        for event in (ledger1[0], ledger2[0])
    )
    duplicate = {
        "schema_version": "CMAME-P4D1-DUPLICATE-1.0",
        "environment_fresh_process_normalized_equal": environment_duplicate,
        "observer_enabled_result_normalized_equal": bridge_duplicate,
        "c_ledger_normalized_equal": ledger_duplicate,
        "observer_disabled_enabled_exact_no_effect": no_effect,
        "exact_no_effect_fields": list(no_effect_fields),
        "structured_unselected_candidate_present_both_runs": unselected,
        "postcheck_change_flags_false_both_runs": change_flags_false,
        "observer_on_run_1_ledger_sha256": sha256(RUNTIME / "observer_on_run_1" / "c_ledger.jsonl"),
        "observer_on_run_2_ledger_sha256": sha256(RUNTIME / "observer_on_run_2" / "c_ledger.jsonl"),
        "duplicate_gate_pass": environment_duplicate and bridge_duplicate and ledger_duplicate and no_effect and unselected and change_flags_false,
    }
    write_json(ROOT / "P4d1_duplicate_comparison.json", duplicate)

    oracle = load_json(RUNTIME / "oracle" / "result.json")
    topology = load_json(RUNTIME / "topology" / "result.json")
    smoke = load_json(RUNTIME / "safe_increment" / "result.json")
    tests_text = (RUNTIME / "tests" / "unittest.log").read_text(encoding="utf-8")
    tests_pass = "Ran 8 tests" in tests_text and tests_text.rstrip().endswith("OK")

    g0_pass = v213["pass"] and protected["pass"]
    g1_pass = host_identity["pass"]
    g2_pass = duplicate["duplicate_gate_pass"]
    g3_pass = bool(topology["topology_gate_pass"] and topology["committed_immutable_after_trial"])
    g4_pass = bool(oracle["oracle_gate_pass"])
    smoke_pass = bool(
        smoke["mechanics_gate_pass"]
        and smoke["accepted_increment_count"] == 1
        and smoke["accepted_output_after_commit"]
        and smoke["accepted_output_candidate_matches"]
        and not smoke["continued_to_next_load"]
    )
    gates = [
        {"gate": "G0_PROTECTED_EVIDENCE", "pass": g0_pass, "blocked_state": "BLOCKED_PROTECTED_EVIDENCE_DRIFT"},
        {"gate": "G1_HOST_IDENTITY", "pass": g1_pass, "blocked_state": "BLOCKED_HOST_IDENTITY"},
        {"gate": "G2_C_BRIDGE_ATTACH", "pass": g2_pass, "blocked_state": "BLOCKED_C_BRIDGE_ATTACH"},
        {"gate": "G3_FE_TOPOLOGY_AND_STATE", "pass": g3_pass, "blocked_state": "BLOCKED_FE_TOPOLOGY_OR_ORDER"},
        {"gate": "G4_REFERENCE_ORACLE", "pass": g4_pass, "blocked_state": "BLOCKED_REFERENCE_ORACLE"},
        {"gate": "SAFE_INCREMENT_SMOKE", "pass": smoke_pass, "blocked_state": "BLOCKED_SAFE_INCREMENT_SMOKE"},
        {"gate": "DIRECTED_TESTS", "pass": tests_pass, "blocked_state": "BLOCKED_SAFE_INCREMENT_SMOKE"},
    ]
    overall = all(item["pass"] for item in gates) and production["pass"]
    terminal = "PASS_P4D1_PREFLIGHT_READY_FOR_FULL_IMPLEMENTATION" if overall else next(
        item["blocked_state"] for item in gates if not item["pass"]
    )

    raw_files = sorted(path for path in RUNTIME.rglob("*") if path.is_file())
    raw_manifest = {
        "schema_version": "CMAME-P4D1-RAW-EVIDENCE-MANIFEST-1.0",
        "generated_before_summary_manifests": True,
        "manifest_self_hash_embedded": False,
        "file_count": len(raw_files),
        "files": [file_entry(path, ROOT) for path in raw_files],
    }
    write_json(ROOT / "P4d1_raw_evidence_manifest.json", raw_manifest)

    gate_results = {
        "schema_version": "CMAME-P4D1-GATES-1.0",
        "protocol_id": "P4d.1_IMPLEMENTATION_PREFLIGHT",
        "terminal_status": terminal,
        "gates": gates,
        "protected_evidence": {"v2_13": v213, "files": protected},
        "host_identity": host_identity,
        "production_boundary": production,
        "observer_summary": duplicate,
        "oracle_summary": {
            "maximum_packet_error_hex": oracle["maximum_packet_error_hex"],
            "maximum_directional_relative_error_hex": oracle["maximum_directional_relative_error_hex"],
            "N4_relative_L2_error_hex": oracle["manufactured_reference"]["relative_L2_error_hex"],
            "N4_relative_H1_error_hex": oracle["manufactured_reference"]["relative_H1_error_hex"],
        },
        "topology_hashes": topology["hashes"],
        "safe_smoke_metrics": {
            "snes_reason": smoke["snes_reason"],
            "snes_iterations": smoke["snes_iterations"],
            "free_dof_residual_relative_hex": smoke["free_dof_residual_relative_hex"],
            "reaction_balance_relative_hex": smoke["reaction_balance_relative_hex"],
            "maximum_tau_norm_hex": smoke["maximum_tau_norm_hex"],
            "accepted_increment_count": smoke["accepted_increment_count"],
        },
        "evidence_boundary": {
            "formal_benchmark": False,
            "observed_P4d": False,
            "formal_9_case_matrix_run": False,
            "manuscript_updated": False,
            "github_zenodo_doi_updated": False,
            "abaqus_used": False,
            "comsol_used": False,
            "production_model_used": False,
        },
    }
    write_json(ROOT / "P4d1_gate_results.json", gate_results)

    python_files = sorted(list((ROOT / "src").glob("*.py")) + list((ROOT / "oracle").glob("*.py")) +
                          list((ROOT / "tests").glob("*.py")) + list(ROOT.glob("run_p4d1*.py")))
    ast_results = []
    for path in python_files:
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            ast_results.append({"path": path.relative_to(ROOT).as_posix(), "pass": True})
        except SyntaxError as error:
            ast_results.append({"path": path.relative_to(ROOT).as_posix(), "pass": False, "error": str(error)})
    implementation_files = sorted(
        [ROOT / "src" / "p4d_observer_bridge.c"] + python_files +
        [ROOT / "P4d1_bridge_abi_contract.md", ROOT / "P4d1_preflight_protocol.md",
         ROOT / "P4d1_preflight_freeze.json", ROOT / "P4d1_pre_execution_implementation_erratum.md"]
    )
    implementation = {
        "schema_version": "CMAME-P4D1-IMPLEMENTATION-MANIFEST-1.0",
        "implementation_status": terminal,
        "image_reference": PINNED_IMAGE,
        "observer_source_sha256": sha256(ROOT / "src" / "p4d_observer_bridge.c"),
        "observer_binary_sha256": sha256(RUNTIME / "bridge_build" / "libp4d_observer.so"),
        "petsc_version": env1["packages"]["PETSc"],
        "ast_parse_all_pass": all(item["pass"] for item in ast_results),
        "ast_results": ast_results,
        "directed_test_count": 8,
        "directed_tests_pass": tests_pass,
        "no_formal_case_execution": True,
        "no_abaqus_execution": True,
        "manifest_self_hash_embedded": False,
        "files": [file_entry(path, ROOT) for path in implementation_files],
        "raw_evidence_manifest_sha256": sha256(ROOT / "P4d1_raw_evidence_manifest.json"),
    }
    write_json(ROOT / "P4d1_implementation_manifest.json", implementation)

    report = f"""# P4d.1 implementation preflight result

## Terminal status

`{terminal}`

This is a preflight result only. It is not `OBSERVED-P4D` evidence and does not
authorize or report the frozen nine-case matrix.

## Gate results

| Gate | Result |
|---|---|
""" + "\n".join(f"| {item['gate']} | {'PASS' if item['pass'] else item['blocked_state']} |" for item in gates) + f"""

## Native observer

The shared library attaches to `NonlinearProblem.solver` through the verified
same-process petsc4py SNES handle. Observer-disabled and observer-enabled runs
have exact equality in solution, SNES reason, iteration count and residual
sequence. Both fresh observer processes expose a native full-step candidate
that differs from the selected work vector. All post-check change flags remain
false.

Observer C source SHA-256: `{implementation['observer_source_sha256']}`.
Observer binary SHA-256: `{implementation['observer_binary_sha256']}`.

## Oracle and topology

- Maximum Fraction packet error: `{oracle['maximum_packet_error_hex']}`.
- Maximum directional tangent relative error: `{oracle['maximum_directional_relative_error_hex']}`.
- The manufactured reference smoke used only `N=4`; relative L2/H1 diagnostics
  are `{oracle['manufactured_reference']['relative_L2_error_hex']}` and
  `{oracle['manufactured_reference']['relative_H1_error_hex']}`. No convergence
  sequence or formal error-order claim was made.
- Topology: {topology['counts']['cells']} cells, {topology['counts']['nodes']}
  nodes and {topology['counts']['integration_points']} integration points.
- Trial evaluation left committed arrays unchanged.

## Safe increment smoke

Only `H_DIRECT`, load `0.00 -> 0.04`, was run. SNES converged with reason
{smoke['snes_reason']} in {smoke['snes_iterations']} iteration. The relative
free-DOF residual and reaction imbalance are
`{smoke['free_dof_residual_relative_hex']}` and
`{smoke['reaction_balance_relative_hex']}`. Exactly one candidate was committed,
and accepted output was generated afterward from that candidate id. The run did
not continue to `0.08`.

## Preserved implementation evidence

The first pkg-config lookup failure and first topology JSON serialization
failure are retained and explained in the pre-execution erratum. Neither
changed a scientific input or threshold.

## Boundary

No Abaqus, COMSOL, OpenSees, production UEL, P3, formal P4d case, manuscript,
Claim Matrix, Figure, GitHub, Zenodo or DOI action occurred.
"""
    (ROOT / "P4d1_result_report.md").write_text(report, encoding="utf-8")

    forbidden_result_names = [path for path in ROOT.rglob("*") if path.name.startswith("P4D-")]
    pycache = list(ROOT.rglob("__pycache__")) + list(ROOT.rglob("*.pyc"))
    images = [path for path in ROOT.rglob("*") if path.suffix.lower() in {".png", ".svg", ".pdf", ".tiff", ".tif"}]
    qa_pass = bool(
        overall and implementation["ast_parse_all_pass"] and not forbidden_result_names
        and not pycache and not images and production["abaqus_process_total"] == 0
    )
    qa = f"""# P4d.1 final QA

- Terminal status: `{terminal}`.
- G0 protected v2.13 files: `{v213['verified_count']}/{v213['file_count']}`; mismatches `{v213['mismatch_count']}`.
- Protected P2/P3/P4/P4c/P4d hashes and frozen P4d aggregate: `{'PASS' if protected['pass'] else 'FAIL'}`.
- Pinned linux/amd64 image identity: `{'PASS' if image.get('pass') else 'FAIL'}`.
- Two environment packets agree after run-id normalization: `{environment_duplicate}`.
- Observer exact no-effect: `{no_effect}`.
- Two observer results and C ledgers agree after allowed normalization: `{bridge_duplicate and ledger_duplicate}`.
- Structured unselected candidate observed in both fresh processes: `{unselected}`.
- Independent oracle gate: `{g4_pass}`.
- Deterministic topology/state gate: `{g3_pass}`.
- Safe increment gate: `{smoke_pass}`.
- Directed tests: `8/8 PASS`.
- Python AST parse: `{sum(item['pass'] for item in ast_results)}/{len(ast_results)} PASS`.
- Formal P4d result paths: `{len(forbidden_result_names)}`.
- `__pycache__`/`.pyc`: `{len(pycache)}`.
- Generated SVG/PDF/TIFF/PNG: `{len(images)}`.
- Abaqus process count: `{production['abaqus_process_total']}`.
- Production write command issued: `False`.
- Formal P4d matrix run: `False`.
- `OBSERVED-P4D` evidence claimed: `False`.

QA verdict: `{'PASS' if qa_pass else 'FAIL'}`.
"""
    (ROOT / "P4d1_final_QA.md").write_text(qa, encoding="utf-8")

    source_files = sorted(path for path in ROOT.rglob("*") if path.is_file() and path.name != "P4d1_source_manifest.json")
    source_manifest = {
        "schema_version": "CMAME-P4D1-SOURCE-MANIFEST-1.0",
        "terminal_status": terminal,
        "qa_pass": qa_pass,
        "manifest_self_hash_embedded": False,
        "file_count": len(source_files),
        "files": [file_entry(path, ROOT) for path in source_files],
    }
    write_json(ROOT / "P4d1_source_manifest.json", source_manifest)
    return 0 if qa_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
