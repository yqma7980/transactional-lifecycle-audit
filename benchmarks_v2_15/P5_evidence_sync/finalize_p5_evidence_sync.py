from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "P5_EVIDENCE_SYNC_AND_F01_F02_POSTMORTEM_FREEZE_20260731"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


claim = OUT / "P5_claim_evidence_matrix_v2_14_postP5.md"
text = claim.read_text(encoding="utf-8")
text = text.replace("## Abstract eligibility at P2", "## Abstract eligibility after P5")
text = text.replace(
    "The strongest CMAME-facing claims are V14-C07 and V14-C10. If the fair comparison or native-host gate fails, the paper must retain a narrower software-verification framing and re-evaluate CMAME versus JCP rather than compensating with broader wording.",
    "The strongest CMAME-facing claims remain V14-C07 and V14-C10. Native finite-element transfer now has bounded P4d/P5 support, but the fair same-fault comparison is not completed and native rejected-line-search coverage remains unsupported. The paper must retain that narrower boundary rather than compensating with broader wording.",
)
claim.write_text(text, encoding="utf-8")

readme = ROOT / "README_v2_14_working_postP5.md"
readme.write_text(
    """# CMAME v2.14 working package

Date: 2026-07-31  
Status: `P1-P5_COMPLETE_THROUGH_MIXED_P5_EVIDENCE_SYNC`  
Execution status: `P5_FORMAL_EVIDENCE_PRESERVED_NO_NEW_CASE_IN_SYNC_TASK`

## Purpose

This directory develops the v2.14 methodological upgrade without overwriting the v2.13 submission candidate. P1--P4 define the research questions, transaction model, verdict taxonomy, same-fault comparison design and native-host feasibility path. P4d establishes bounded DOLFINx/PETSc finite-element lifecycle evidence. P5 calibrates a fresh-process null envelope and evaluates four frozen scaled-mutation families.

## Current P5 decision

- Full P5 status: `NOT_SUPPORTED_FULL_P5_MATRIX`.
- F05 and F07: `PASS_FRESH_PROCESS_VERIFICATION`.
- F01 and F02: `NOT_SUPPORTED_DISTINCTIVE_REGION_EMPTY`.
- Actual formal process count: 82; all recorded case values are finite.
- Formal raw evidence: 662 files; aggregate SHA-256 `322f4425a390acc43bbc735076c2d10496f02861daa197361e99b6d7fa8385fd`.
- P6 full entry: not authorized because F01/F02 have no eligible selected strength.

## New evidence-sync package

`P5_EVIDENCE_SYNC_AND_F01_F02_POSTMORTEM_FREEZE_20260731` contains:

- source tables for the four family outcomes and all F01/F02 metric sweeps;
- F01 discrete and diagnostic threshold-crossing analysis;
- F02 static dependency trace with observed/inferred mechanism labels;
- a post-P5 Claim Matrix draft and manuscript insertion patch;
- a figure evidence contract, P6 decision gate, QA and SHA-256 manifest.

## Hard boundaries

- v2.13 source, PDFs, raw JSON/CSV, failure records and public-archive metadata remain read-only.
- This evidence-sync task did not run FE cases, unit tests, Abaqus, COMSOL or production models.
- No threshold, strength, field binding, history or oracle was changed after observing P5.
- GitHub, Zenodo and DOI records were not changed.
- F05/F07 family-level passes cannot be reported as a complete P5 pass.
- F02 elastic-branch masking is an inference, not an observed per-integration-point runtime history.

## Next gate

Do not enter the frozen full P6 chain. A future F05/F07-only study would require a new prospective question and static freeze. Before manuscript promotion, complete the remaining fair same-fault comparison or explicitly retain it as an open limitation.
""",
    encoding="utf-8",
)

shutil.copy2(Path(__file__), OUT / Path(__file__).name)
manifest_path = OUT / "P5_source_manifest.json"
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
manifest["outputs"] = [
    {"path": path.name, "bytes": path.stat().st_size, "sha256": digest(path)}
    for path in sorted(OUT.iterdir(), key=lambda p: p.name.lower())
    if path.is_file() and path.name != manifest_path.name
]
manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps({"status": "FINALIZED", "manifest_outputs": len(manifest["outputs"])}, indent=2))
