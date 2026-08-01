from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
from datetime import date
from pathlib import Path


WORKING = Path(
    r"F:\NCS_paper_workspace\Nature_Computational_Science"
    r"\submission_cmame_v2_14_working_20260730"
)
P5 = WORKING / "P5_FULL_FE_BACKEND_IMPLEMENTATION_20260731"
FORMAL = P5 / "results" / "P5_formal_20260731_fullFE_v1d"
ADJ = FORMAL / "adjudication_20260731"
FREEZE = WORKING / "P5_SCALED_THRESHOLD_AND_FRESH_PROCESS_NULL_ENVELOPE_FREEZE_20260731"
P4D_MATERIAL = (
    WORKING
    / "P4d_DOLFINx_PETSc_MINIMAL_FE_HOST_20260731"
    / "P4d.2_FULL_IMPLEMENTATION_20260731"
    / "src"
    / "p4d_material.py"
)
STAGE = Path(__file__).resolve().parent
OUT = STAGE / "P5_EVIDENCE_SYNC_AND_F01_F02_POSTMORTEM_FREEZE_20260731"

EXPECTED = {
    FORMAL / "final" / "execution_manifest.json": "ebe55f10b1b3b92e8f86e33956cb5531b97493e41ce55ef9cbe9318ede5d843f",
    FORMAL / "final" / "strength_sweep.csv": "b9c1f33df506979e71b4aea7763c3eee9eeffcdc0a089d48972aa1c7d87ca006",
    FORMAL / "final" / "selected_strengths.json": "195d4c0216923c59435124d1c14379feee162de6e867acbb6ada35eb7dea8726",
    FORMAL / "final" / "null_envelope.json": "b318e735a2514dcbc357349919d6bde5ece127d2ea05752dc29bafba411cebb6",
    ADJ / "postexecution_manifest.json": "7653cd0c12b111d2f6bac68286e6172a9099a05d7bbbbec4fb8bd5eeb8725999",
    WORKING / "P2_source_manifest.json": "79702f5679767b5f28b98c5683ae42a9ad8a33bdd37793288835c7e5accbf932",
}
RAW_AGGREGATE_EXPECTED = "322f4425a390acc43bbc735076c2d10496f02861daa197361e99b6d7fa8385fd"
CONVENTIONAL_GATE = 1.0e-10
OPERATOR_Z_GATE = 10.0


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def dump_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def verify_sources() -> dict:
    mismatches = []
    for path, expected in EXPECTED.items():
        actual = sha256(path)
        if actual != expected:
            mismatches.append({"path": str(path), "expected": expected, "actual": actual})
    manifest_path = FORMAL / "final" / "execution_manifest.json"
    manifest = read_json(manifest_path)
    raw_rows = []
    for item in manifest["files"]:
        path = FORMAL / item["path"]
        actual = sha256(path)
        if actual != item["sha256"]:
            mismatches.append(
                {"path": str(path), "expected": item["sha256"], "actual": actual}
            )
        raw_rows.append(f"{item['path']}|{actual}")
    aggregate = hashlib.sha256("\n".join(raw_rows).encode("utf-8")).hexdigest()
    if aggregate != RAW_AGGREGATE_EXPECTED:
        mismatches.append(
            {"path": "formal_raw_aggregate", "expected": RAW_AGGREGATE_EXPECTED, "actual": aggregate}
        )
    if mismatches:
        raise RuntimeError(json.dumps(mismatches, indent=2))
    return {
        "protected_hash_gate": "PASS",
        "formal_raw_file_count": len(manifest["files"]),
        "formal_raw_aggregate_sha256": aggregate,
    }


def load_family_rows() -> tuple[list[dict], list[dict]]:
    sweep = []
    metric_rows = []
    for family in ("F01", "F02", "F05", "F07"):
        case_id = f"P5-SCALE-{family}-DEV"
        for index in range(15):
            run_id = f"run_{index + 1}"
            result_path = FORMAL / case_id / run_id / "case_result.json"
            result = read_json(result_path)
            if result["strength_index"] != index or result["family_id"] != family:
                raise RuntimeError(f"case identity mismatch: {result_path}")
            sweep.append(result)
            distances = result["metric_distances"]
            metric_rows.append(
                {
                    "family_id": family,
                    "case_id": case_id,
                    "run_id": run_id,
                    "strength_index": index,
                    "eta": result["eta"],
                    "conventional_quiet": bool(result["conventional_quiet"]),
                    "lifecycle_violation_present": bool(result["lifecycle_violation_present"]),
                    "all_values_finite": bool(result["all_values_finite"]),
                    "M_R": distances["M_R"],
                    "M_J": distances["M_J"],
                    "M_X": distances["M_X"],
                    "M_GP": distances["M_GP"],
                    "M_ALPHA": distances["M_ALPHA"],
                    "M_REACTION": distances["M_REACTION"],
                    "M_OUTPUT_W": distances["M_OUTPUT_W"],
                    "M_OUTPUT_R": distances["M_OUTPUT_R"],
                    "z_residual": result["z_residual"],
                    "z_tangent": result["z_tangent"],
                    "z_family": result["z_family"],
                    "observed_lifecycle_verdict": result["observed_lifecycle_verdict"],
                    "result_sha256": sha256(result_path),
                }
            )
    return sweep, metric_rows


def first_index(rows: list[dict], predicate) -> int | None:
    for row in rows:
        if predicate(row):
            return int(row["strength_index"])
    return None


def slope_through_origin(rows: list[dict], metric: str, max_index: int = 4) -> float:
    subset = [r for r in rows if int(r["strength_index"]) <= max_index and float(r["eta"]) > 0]
    numerator = sum(float(r["eta"]) * float(r[metric]) for r in subset)
    denominator = sum(float(r["eta"]) ** 2 for r in subset)
    return numerator / denominator


def source_locator(path: Path, needle: str) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    for number, line in enumerate(lines, start=1):
        if needle in line:
            return f"{path.relative_to(WORKING).as_posix()}:{number}"
    raise RuntimeError(f"missing source locator: {needle} in {path}")


def build_family_summary(sweep: list[dict]) -> list[dict[str, object]]:
    corrected = read_json(ADJ / "matrix_summary_corrected.json")
    selected = read_json(FORMAL / "final" / "selected_strengths.json")["families"]
    rows = []
    for family in ("F01", "F02", "F05", "F07"):
        group = [r for r in sweep if r["family_id"] == family]
        rows.append(
            {
                "family_id": family,
                "sweep_processes": len(group),
                "all_values_finite": all(bool(r["all_values_finite"]) for r in group),
                "all_lifecycle_violations_present": all(
                    bool(r["lifecycle_violation_present"]) for r in group
                ),
                "first_nonquiet_index": first_index(group, lambda r: not bool(r["conventional_quiet"])),
                "first_operator_z_ge_10_index": first_index(
                    group, lambda r: float(r["z_family"]) >= OPERATOR_Z_GATE
                ),
                "selected_index": selected[family]["selected_index"],
                "next_index": selected[family]["next_index"],
                "fresh_pair_verified": family in ("F05", "F07"),
                "formal_family_status": corrected["family_status"][family],
                "evidence_status": (
                    "OBSERVED-P5-FAMILY-PASS"
                    if family in ("F05", "F07")
                    else "OBSERVED-P5-NOT-SUPPORTED"
                ),
            }
        )
    return rows


def build_f01(metric_rows: list[dict], thresholds: dict[str, float]) -> tuple[dict, list[dict]]:
    rows = [r for r in metric_rows if r["family_id"] == "F01"]
    first_nonquiet = first_index(rows, lambda r: not bool(r["conventional_quiet"]))
    first_operator = first_index(rows, lambda r: float(r["z_family"]) >= OPERATOR_Z_GATE)
    slope_gp = slope_through_origin(rows, "M_GP")
    slope_r = slope_through_origin(rows, "M_R")
    inferred_conventional_eta = CONVENTIONAL_GATE / slope_gp
    inferred_operator_eta = (OPERATOR_Z_GATE * thresholds["M_R"]) / slope_r
    selected_rows = [r for r in rows if r["strength_index"] in (4, 5)]
    crossing_rows = []
    for row in selected_rows:
        crossing_rows.append(
            {
                "strength_index": row["strength_index"],
                "eta": row["eta"],
                "conventional_quiet": row["conventional_quiet"],
                "M_GP": row["M_GP"],
                "conventional_gate": CONVENTIONAL_GATE,
                "M_R": row["M_R"],
                "operator_threshold_10x_T_R": OPERATOR_Z_GATE * thresholds["M_R"],
                "z_residual": row["z_residual"],
                "z_tangent": row["z_tangent"],
                "z_family": row["z_family"],
            }
        )
    summary = {
        "family_id": "F01",
        "formal_status": "NOT_SUPPORTED_DISTINCTIVE_REGION_EMPTY",
        "observed_first_nonquiet_index": first_nonquiet,
        "observed_first_operator_separation_index": first_operator,
        "same_discrete_crossing": first_nonquiet == first_operator,
        "eligible_adjacent_pair_exists": False,
        "frozen_grid_changed": False,
        "threshold_changed": False,
        "low_strength_fit": {
            "status": "POSTMORTEM_DIAGNOSTIC_ONLY_NOT_SELECTION",
            "fit_indices": [0, 1, 2, 3, 4],
            "M_GP_per_eta_slope": slope_gp,
            "M_R_per_eta_slope": slope_r,
            "inferred_eta_at_conventional_gate": inferred_conventional_eta,
            "inferred_eta_at_operator_10x_threshold": inferred_operator_eta,
            "ordering": (
                "CONVENTIONAL_GATE_PRECEDES_OPERATOR_SEPARATION"
                if inferred_conventional_eta < inferred_operator_eta
                else "OPERATOR_SEPARATION_PRECEDES_CONVENTIONAL_GATE"
            ),
            "scientific_use": "mechanism interpretation only; prohibited for case selection",
        },
        "supported_conclusion": (
            "On the frozen binary grid, the first operator-separated level is already nonquiet; "
            "the predeclared distinctive region is empty."
        ),
        "does_not_support": [
            "interpolated selection",
            "an added mutation strength",
            "a relaxed conventional gate",
            "a full P5 pass",
        ],
    }
    return summary, crossing_rows


def build_f02(metric_rows: list[dict]) -> tuple[dict, list[dict]]:
    rows = [r for r in metric_rows if r["family_id"] == "F02"]
    adapter = P5 / "src" / "p5_fe_adapter.py"
    trace = [
        {
            "ordinal": 1,
            "symbol": "declared_alpha_cache",
            "role": "declared persistent field and projection member",
            "source_locator": source_locator(adapter, "declared_alpha_cache: np.ndarray"),
            "reachability_status": "STATICALLY_REACHABLE",
            "evidence_status": "ESTABLISHED-CODE-TRACE",
        },
        {
            "ordinal": 2,
            "symbol": "F02 mutation",
            "role": "adds eta*0.1 at cell 0, quadrature point 1",
            "source_locator": source_locator(adapter, "declared_alpha_cache[0, 1] += eta * 0.1"),
            "reachability_status": "MUTATION_WRITTEN",
            "evidence_status": "ESTABLISHED-CODE-TRACE",
        },
        {
            "ordinal": 3,
            "symbol": "effective_alpha",
            "role": "committed alpha plus declared persistent cache",
            "source_locator": source_locator(adapter, "effective_alpha = committed.alpha"),
            "reachability_status": "CONSUMED_BY_ADAPTER",
            "evidence_status": "ESTABLISHED-CODE-TRACE",
        },
        {
            "ordinal": 4,
            "symbol": "evaluate_material(current)",
            "role": "receives effective_alpha at each integration point",
            "source_locator": source_locator(adapter, "current = evaluate_material"),
            "reachability_status": "MATERIAL_INPUT_REACHED",
            "evidence_status": "ESTABLISHED-CODE-TRACE",
        },
        {
            "ordinal": 5,
            "symbol": "yield_function",
            "role": "alpha enters the material branch criterion",
            "source_locator": source_locator(P4D_MATERIAL, "yield_function = trial_norm"),
            "reachability_status": "BRANCH_CRITERION_REACHED",
            "evidence_status": "ESTABLISHED-CODE-TRACE",
        },
        {
            "ordinal": 6,
            "symbol": "elastic return",
            "role": "tau and tangent are alpha-independent if the branch remains elastic",
            "source_locator": source_locator(P4D_MATERIAL, "if yield_function <= 0.0"),
            "reachability_status": "PLAUSIBLE_MASKING_BRANCH",
            "evidence_status": "INFERRED-NOT-RUNTIME-BRANCH-PROVEN",
        },
    ]
    max_operator = max(max(float(r["M_R"]), float(r["M_J"])) for r in rows)
    first_nonquiet = first_index(rows, lambda r: not bool(r["conventional_quiet"]))
    summary = {
        "family_id": "F02",
        "formal_status": "NOT_SUPPORTED_DISTINCTIVE_REGION_EMPTY",
        "all_15_structural_violations_present": all(
            bool(r["lifecycle_violation_present"]) for r in rows
        ),
        "all_15_operator_residual_zero": all(float(r["M_R"]) == 0.0 for r in rows),
        "all_15_operator_tangent_zero": all(float(r["M_J"]) == 0.0 for r in rows),
        "maximum_operator_metric": max_operator,
        "first_nonquiet_index": first_nonquiet,
        "first_nonquiet_field": "M_ALPHA",
        "static_dependency_trace": "REACHABLE_TO_MATERIAL_BRANCH_CRITERION",
        "mechanism_interpretation": (
            "The declared alpha field reaches material evaluation. The frozen replay nevertheless "
            "shows zero residual/tangent drift at every strength. An unchanged elastic branch is a "
            "plausible masking mechanism, but no per-integration-point branch ledger was frozen, so "
            "that explanation remains inferred."
        ),
        "supported_conclusion": (
            "F02 detects an exact restoration violation but supplies no secondary operator separation "
            "under the frozen history."
        ),
        "does_not_support": [
            "dead-code classification",
            "universal alpha insensitivity",
            "a changed replay history",
            "a full P5 pass",
        ],
    }
    return summary, trace


def build_claim_matrix() -> str:
    base = (WORKING / "P2_claim_evidence_matrix_v2_14_draft.md").read_text(encoding="utf-8")
    base = base.replace("Status: `DRAFT_STATIC_ONLY`", "Status: `POST_P5_EVIDENCE_SYNC_DRAFT`")
    base = base.replace(
        "| V14-C08 | The protocol detects and localizes a systematic family of lifecycle faults without alarming on benign controls. | `OPEN` | Current mutations are heterogeneous and not a frozen coverage study | Nothing beyond case-specific outcomes. | Population coverage or general false-positive/negative rates. | P4 frozen fault taxonomy and confirmation cases. |",
        "| V14-C08 | The protocol detects and localizes a systematic family of lifecycle faults without alarming on benign controls. | `OBSERVED-P5-BOUNDED/MIXED` | Exact and arithmetic null controls; F05/F07 fresh-process verification; F01/F02 non-support | Bounded evidence for two frozen families and explicit non-support for two others. | Population coverage, sensitivity/specificity, or general false-positive/negative rates. | Preserve the mixed result; do not aggregate as a full pass. |",
    )
    base = base.replace(
        "| V14-C10 | TLA transfers to a host whose rejection/retry/restart events are generated natively by that host. | `OPEN` | SciPy exposes nonaccepted residual evaluations but not the complete FE lifecycle set | No complete native-lifecycle claim. | Native finite-element transfer. | P5 host selection and formal gate. |",
        "| V14-C10 | TLA transfers to a native DOLFINx/PETSc finite-element backend with auditable state and operator packets. | `OBSERVED-P4D/P5-BOUNDED` | P4d branch evidence and P5 full-backend runs | Native FE backend transfer for the executed direct, driver-retry, restart, output, version and scaled-mutation paths. | Native rejected line-search candidate coverage, Abaqus behavior, parallel safety or production readiness. | Keep native line-search non-support explicit. |",
    )
    insert = """
| V14-C17 | The P5 numerical null envelope is stable under fresh-process calibration and confirmation. | `OBSERVED-P5` | Six exact-null, six arithmetic-null and two confirmation processes | Frozen metric thresholds and a bounded numerical-null reference. | A universal machine-independent threshold. | Preserve environment identity and thresholds. |
| V14-C18 | F05 and F07 satisfy the frozen adjacent-strength and fresh-process verification rules. | `OBSERVED-P5-FAMILY-PASS` | Fifteen strengths per family plus two fresh repetitions at each of two adjacent selected levels | Bounded family-level detection and repeatability in the P5 FE backend. | A full P5 matrix pass or coverage of all persistence faults. | Eligible only as family-level evidence. |
| V14-C19 | F01 and F02 do not provide a distinctive conventional-quiet/operator-separated region under the frozen protocol. | `OBSERVED-P5-NOT-SUPPORTED` | Fifteen strengths per family; F01 threshold crossing; F02 dependency trace | A transparent non-support result and mechanism-bounded postmortem. | That the faults are absent, harmless, or undetectable under all histories. | Freeze the result; no interpolation or retuning. |
| V14-C20 | The complete P5 matrix passed. | `NOT_SUPPORTED` | Corrected P5 summary: F01/F02 non-support, F05/F07 pass | No authorized positive full-matrix claim. | Complete mutation-family coverage or general detection superiority. | P6 full entry remains closed. |
"""
    marker = "\n## Abstract eligibility at P2"
    return base.replace(marker, "\n" + insert.strip() + "\n" + marker).replace(
        "Currently eligible for a bounded abstract:",
        "After P5, the bounded abstract may additionally mention the calibrated null envelope and the mixed family outcome. Currently eligible for a bounded abstract:",
    )


def build_manuscript_patch() -> str:
    return """# P5 manuscript evidence-sync patch for v2.14

Date: 2026-07-31  
Status: `DRAFT_INSERTION_ONLY_NOT_A_MANUSCRIPT`  
Source manuscript: v2.13 remains read-only.

## Results insertion

### Scaled mutation families expose both detectable and unsupported regimes

We calibrated a fresh-process numerical-null envelope before applying four predeclared scaled mutation families to the DOLFINx/PETSc finite-element backend. The exact and arithmetic null controls passed, and the independent confirmation processes remained within every frozen metric threshold. Across the four 15-level binary sweeps, all 60 development runs were finite and contained the expected exact lifecycle violation. The secondary numerical evidence was nevertheless mixed. Output-feedback and callback-bias families F05 and F07 each satisfied the predeclared adjacent-level separation rule and reproduced it in four new fresh-process comparisons. Trial-cache family F01 and declared-alpha family F02 did not. For F01, the first grid level with residual separation of at least ten null thresholds was already outside the conventional quiet region. For F02, the declared field-restoration violation was present at every level, but residual and tangent replay distances remained exactly zero. The complete P5 matrix is therefore classified as not supported rather than passed.

## Methods insertion

The P5 amplitude grid, field bindings, metric scales, null-envelope rule and family-selection algorithm were frozen before execution. Six exact-null and six arithmetic-null processes defined metric thresholds as the larger of 1,024 machine epsilons and ten times the complete pairwise arithmetic envelope; two additional processes confirmed, but did not refit, those thresholds. Each mutation family was then evaluated at all 15 predeclared binary strengths in separate single-process, single-thread runs. A family could advance only if two adjacent levels retained finite mechanics and conventional endpoint gates, contained the exact lifecycle violation, and exceeded ten null thresholds in residual or tangent replay. Two new fresh-process repetitions were required at each selected level. No interpolation, added amplitude, changed field binding or relaxed threshold was allowed.

## Discussion insertion

The mixed P5 result is informative about method scope. F05/F07 show that exact ownership or event-order violations can coexist with a numerically quiet endpoint and a repeatable secondary operator signal. F01 shows the opposite ordering: the ordinary field gate activates no later than the secondary operator gate on the frozen grid, so lifecycle replay adds no distinctive numerical detection region for that family. F02 separates structural adjudication from numerical consequence even more sharply. Static tracing confirms that the perturbed alpha cache reaches the material branch criterion, yet no residual or tangent drift appears under the frozen replay. An unchanged elastic branch is a plausible explanation, but it is not promoted to an observed mechanism because the formal run did not freeze a per-integration-point branch ledger.

## Limitations insertion

P5 is not a full-matrix pass and does not establish population-level fault coverage, sensitivity, specificity or superiority over conventional verification. F01/F02 may behave differently under another admissible history, active constitutive branch or field binding, but those alternatives were not part of the frozen protocol and were not explored retrospectively. The results remain single-rank, single-thread DOLFINx/PETSc evidence and do not establish native rejected-line-search coverage, Abaqus behavior or production-model reliability.

## Abstract-safe sentence

In a native finite-element backend, calibrated null controls and scaled mutations produced repeatable family-level evidence for two fault classes, while two other predeclared classes returned explicit non-support rather than a forced positive result.

## Prohibited wording

- "P5 passed" or "all mutation families were detected".
- "F02 is dead code" or "alpha cannot affect the operators".
- "F01 proves TLA is more sensitive than conventional checks".
- Any Abaqus, production, parallel, contact, damage or multiphysics claim.
"""


def main() -> None:
    if OUT.exists() and any(OUT.iterdir()):
        raise RuntimeError(f"refusing to overwrite nonempty output directory: {OUT}")
    OUT.mkdir(parents=True, exist_ok=True)
    source_gate = verify_sources()
    corrected = read_json(ADJ / "matrix_summary_corrected.json")
    if corrected["evidence_status"] != "NOT_SUPPORTED_FULL_P5_MATRIX":
        raise RuntimeError("unexpected corrected P5 status")
    if corrected["actual_process_count"] != 82:
        raise RuntimeError("unexpected actual process count")

    sweep, metric_rows = load_family_rows()
    if len(sweep) != 60 or not all(bool(row["all_values_finite"]) for row in sweep):
        raise RuntimeError("strength sweep completeness/finite gate failed")
    null_envelope = read_json(FORMAL / "final" / "null_envelope.json")
    thresholds = null_envelope["thresholds"]

    shutil.copy2(Path(__file__), OUT / "build_p5_evidence_sync.py")

    family_rows = build_family_summary(sweep)
    write_csv(
        OUT / "P5_family_outcome_source.csv",
        list(family_rows[0].keys()),
        family_rows,
    )
    write_csv(
        OUT / "P5_F01_F02_metric_sweep_source.csv",
        list(metric_rows[0].keys()),
        [r for r in metric_rows if r["family_id"] in ("F01", "F02")],
    )

    f01_summary, crossing_rows = build_f01(metric_rows, thresholds)
    dump_json(OUT / "P5_F01_postmortem_summary.json", f01_summary)
    write_csv(
        OUT / "P5_F01_threshold_crossing.csv",
        list(crossing_rows[0].keys()),
        crossing_rows,
    )
    (OUT / "P5_F01_threshold_crossing_analysis.md").write_text(
        f"""# P5 F01 threshold-crossing postmortem

Status: `OBSERVED_NOT_SUPPORTED_DISTINCTIVE_REGION_EMPTY`

The frozen binary sweep first became nonquiet at index {f01_summary['observed_first_nonquiet_index']} and first reached `Z_family >= 10` at the same index {f01_summary['observed_first_operator_separation_index']}. Index 4 remained conventionally quiet with `M_GP={crossing_rows[0]['M_GP']:.6g}`, `M_R={crossing_rows[0]['M_R']:.6g}` and `Z_R={crossing_rows[0]['z_residual']:.6g}`. Index 5 produced `M_GP={crossing_rows[1]['M_GP']:.6g}`, `M_R={crossing_rows[1]['M_R']:.6g}` and `Z_R={crossing_rows[1]['z_residual']:.6g}`, but its conventional gate had already failed.

A through-origin fit over indices 0--4 is retained only as a postmortem diagnostic. It places the `M_GP=1e-10` crossing at eta approximately {f01_summary['low_strength_fit']['inferred_eta_at_conventional_gate']:.6g} and the `M_R=10*T_R` crossing at eta approximately {f01_summary['low_strength_fit']['inferred_eta_at_operator_10x_threshold']:.6g}. This ordering is consistent with the observed empty distinctive region. The inferred values are not case selections and cannot authorize interpolation, an added strength or a changed gate.

Supported conclusion: under the frozen grid and history, F01 supplies an exact restoration violation but no region in which the secondary operator signal is separated while conventional outputs remain quiet.
""",
        encoding="utf-8",
    )

    f02_summary, f02_trace = build_f02(metric_rows)
    dump_json(OUT / "P5_F02_postmortem_summary.json", f02_summary)
    write_csv(
        OUT / "P5_F02_dependency_trace.csv",
        list(f02_trace[0].keys()),
        f02_trace,
    )
    (OUT / "P5_F02_dependency_analysis.md").write_text(
        """# P5 F02 dependency postmortem

Status: `OBSERVED_NOT_SUPPORTED_WITH_STATIC_REACHABILITY_TRACE`

All 15 F02 runs contain the exact declared-persistent-field restoration violation and remain finite. `M_R` and `M_J` are exactly zero at every strength, whereas `M_ALPHA` eventually leaves the conventional quiet region. The frozen history therefore contains no secondary operator-separation region.

The static dependency trace rules out a simple disconnected-field explanation: `declared_alpha_cache` is part of persistent state, contributes to `effective_alpha`, and is passed to the material update, where alpha enters the yield criterion. The elastic return is independent of alpha once the branch remains unchanged. That is a plausible masking mechanism, not an observed branch history, because no formal per-integration-point branch ledger was frozen. The evidence does not justify changing the history, mutation site or constitutive state after seeing the result.
""",
        encoding="utf-8",
    )

    postmortem_freeze = {
        "freeze_id": "P5-EVIDENCE-SYNC-POSTMORTEM-1.0",
        "date": str(date.today()),
        "status": "FROZEN_POSTEXECUTION_NO_NEW_CASES",
        "formal_execution_tag": "P5_formal_20260731_fullFE_v1d",
        "formal_matrix_status": corrected["formal_matrix_status"],
        "actual_process_count": 82,
        "family_status": corrected["family_status"],
        "locked_rules": {
            "new_strengths_allowed": False,
            "interpolation_for_selection_allowed": False,
            "threshold_changes_allowed": False,
            "field_rebinding_allowed": False,
            "history_changes_allowed": False,
            "rerun_authorized": False,
        },
        "F01_postmortem_scope": "observed discrete crossing plus diagnostic low-strength fit",
        "F02_postmortem_scope": "static dependency trace plus observed zero operator drift",
        "evidence_labels": {
            "F01": "OBSERVED-P5-NOT-SUPPORTED",
            "F02": "OBSERVED-P5-NOT-SUPPORTED",
            "F05": "OBSERVED-P5-FAMILY-PASS",
            "F07": "OBSERVED-P5-FAMILY-PASS",
            "full_matrix": "NOT_SUPPORTED",
        },
        "protected_evidence": source_gate,
    }
    dump_json(OUT / "P5_postmortem_freeze.json", postmortem_freeze)

    (OUT / "P5_claim_evidence_matrix_v2_14_postP5.md").write_text(
        build_claim_matrix(), encoding="utf-8"
    )
    (OUT / "P5_manuscript_evidence_sync_patch.md").write_text(
        build_manuscript_patch(), encoding="utf-8"
    )
    (OUT / "P5_figure_evidence_contract.md").write_text(
        """# P5 figure evidence contract

Status: `SOURCE_DATA_READY_NO_FINAL_FIGURE`

## Panel A - calibrated null envelope

- Source: `null_envelope.json` and corrected summary.
- Allowed claim: fresh-process null calibration and confirmation passed.
- Forbidden implication: universal or machine-independent threshold.

## Panel B - four family outcomes

- Source: `P5_family_outcome_source.csv`.
- Allowed claim: F05/F07 family pass; F01/F02 non-support.
- Forbidden implication: complete P5 pass or population coverage.

## Panel C - F01 competing threshold crossings

- Source: `P5_F01_threshold_crossing.csv` and the full F01 metric sweep.
- Show the conventional `1e-10` field gate separately from `10*T_R` operator separation.
- Allowed claim: first observed crossings occur at the same frozen grid index.
- Forbidden implication: diagnostic fitted crossings are formal selected strengths.

## Panel D - F02 structural-to-numerical trace

- Source: `P5_F02_dependency_trace.csv` and F02 metric sweep.
- Allowed claim: the field is statically reachable, while residual/tangent drift is zero under the frozen history.
- Forbidden implication: the elastic branch was observed at every affected integration point.

No SVG, PDF, TIFF or PNG is generated by this task.
""",
        encoding="utf-8",
    )
    (OUT / "P6_entry_decision_gate.md").write_text(
        """# P6 entry decision gate after P5

Status: `P6_FULL_ENTRY_NOT_AUTHORIZED`

The frozen P5 protocol requires family selection before held-out P6 binding. F01 and F02 produced no eligible selected strength, so the complete P5-to-P6 chain is not satisfied. F05/F07 family-level evidence remains valid but cannot be promoted to a complete P6 matrix by dropping unsupported families after execution.

A future F05/F07-only study would require a new prospective scientific question, new static freeze and a claim explicitly limited to those families. It cannot be called continuation of the frozen full P5 matrix, cannot reuse P6 as an untouched confirmation, and is not authorized here.

No new case, threshold, history, field binding or manuscript result is authorized by this decision file.
""",
        encoding="utf-8",
    )

    qa = {
        "status": "PASS_STATIC_EVIDENCE_SYNC_QA",
        **source_gate,
        "corrected_summary_status": corrected["evidence_status"],
        "actual_process_count": corrected["actual_process_count"],
        "strength_sweep_row_count": len(sweep),
        "F01_F02_metric_source_row_count": len(
            [r for r in metric_rows if r["family_id"] in ("F01", "F02")]
        ),
        "all_strength_runs_finite": all(bool(r["all_values_finite"]) for r in sweep),
        "F01_status": f01_summary["formal_status"],
        "F02_status": f02_summary["formal_status"],
        "formal_case_execution_performed": False,
        "abaqus_execution_performed": False,
        "manuscript_overwritten": False,
        "public_repository_modified": False,
        "doi_modified": False,
    }
    dump_json(OUT / "P5_final_QA.json", qa)
    (OUT / "P5_final_report.md").write_text(
        f"""# P5 evidence sync and F01/F02 postmortem

Final status: `PASS_P5_EVIDENCE_SYNC_AND_POSTMORTEM_FREEZE`

The 662-file formal raw manifest was re-read and reproduced aggregate SHA-256 `{RAW_AGGREGATE_EXPECTED}`. The corrected execution count is 82, not the planned maximum of 90. All recorded case values are finite.

The full P5 matrix remains `NOT_SUPPORTED_FULL_P5_MATRIX`. F05 and F07 passed their frozen fresh-process verification. F01 and F02 remain `NOT_SUPPORTED_DISTINCTIVE_REGION_EMPTY`. F01 reaches secondary operator separation only when the conventional field gate is already nonquiet. F02 contains the exact structural restoration violation but zero residual/tangent drift throughout the frozen sweep; static tracing confirms reachability to the material branch criterion without proving the runtime branch mechanism.

This task created source tables, bounded Claim Matrix/manuscript insertions and a P6 decision gate. It did not run a case, modify thresholds, overwrite the v2.13 manuscript, or update GitHub, Zenodo or DOI records.
""",
        encoding="utf-8",
    )

    output_items = []
    for path in sorted(OUT.iterdir(), key=lambda p: p.name.lower()):
        if path.name == "P5_source_manifest.json" or not path.is_file():
            continue
        output_items.append(
            {"path": path.name, "bytes": path.stat().st_size, "sha256": sha256(path)}
        )
    source_items = [
        {"path": str(path), "sha256": expected} for path, expected in EXPECTED.items()
    ]
    source_items.append(
        {
            "path": "formal_raw_manifest_aggregate",
            "file_count": source_gate["formal_raw_file_count"],
            "sha256": source_gate["formal_raw_aggregate_sha256"],
        }
    )
    dump_json(
        OUT / "P5_source_manifest.json",
        {
            "manifest_id": "P5-EVIDENCE-SYNC-SOURCE-1.0",
            "status": "FINAL_STATIC_DERIVATION",
            "sources": source_items,
            "outputs": output_items,
            "manifest_self_hash_embedded": False,
        },
    )
    print(json.dumps({"status": qa["status"], "output_count": len(output_items) + 1}, indent=2))


if __name__ == "__main__":
    main()
