# L2-D3.0 static implementation QA

Date: 2026-07-22

Status: **IMPLEMENTED_NOT_EXECUTED**

## Scope

This document records static implementation acceptance for the frozen
L2-D3.0 tangent-path benchmark. It is not a benchmark execution report.
No L2-TG case, test suite, runner, Abaqus job or production calculation was
executed. Consequently, no OBSERVED-L2-D3 evidence exists.

The implementation reuses the L2-HOST-D1.0 material model, element model,
transactional state semantics and canonical serializer without modifying any
D1 or D2 source, result, freeze or manifest.

## Frozen design verification

| Frozen file | SHA-256 | Result |
|---|---|---|
| `L2_D3_execution_freeze.json` | `03ebd4eb92fca4cb9300be4192cdd73b5575f9798b9c46f90bd618f7dc85cbcc` | PASS |
| `L2_D3_tangent_path_case_matrix.csv` | `665576bd3e9f66c0ed8152a4fde4cc69d1b82ab810202e666340f234ec2f5c64` | PASS |
| `L2_D3_implementation_plan.md` | `2a90570675297ac8270dbc41c4aa0b8665a12776c96c65efadc72c7264782a78` | PASS |
| `L2_D3_source_manifest.json` | `f53254ec00340489f4cbc78c84b9e7c4f79325c471c27b7b8fe36189b8384925` | PASS |

The frozen identity is `design_version=L2-D3.0`,
`design_status=FROZEN_NOT_IMPLEMENTED`, `execution_authorized=false` and
`results_exist=false`. The case matrix contains only `L2-TG-01`,
`L2-TG-02` and `L2-TG-03`.

## Created implementation files

| File | Purpose | SHA-256 |
|---|---|---|
| `src/l2_d3_tangent_path.py` | Tangent-path contracts and case entry point | `e2025fd45a1779f8ff76c0c867def4a6777007b10556e7a9fd5f59a3e1e938cd` |
| `oracle/l2_d3_fraction_oracle.py` | Independent exact Fraction oracle | `c8228de5050de5d42d7aad802c9adf8d2ef5481a986c4418ec59cc25eab85f80` |
| `tests/test_l2_d3_tangent_path.py` | Twelve unexecuted test definitions | `3d17003e90b0c9d2f797a9c888d5964e0fcf0408c57dd210ac00b753f0ccf236` |
| `run_l2_d3.py` | Doubly locked one-case runner | `24321670c277da69862e8ed123ae00debde9039349a5372e1099cc7d9204f837` |
| `L2_D3_implementation_manifest.json` | Static implementation provenance | `629a9eef34c0e9a7b60a68ce11ee640f70e131f7ab849e35fa3fc5058ccb5e81` |

The QA report hash is intentionally reported externally after this file is
created. It is not embedded in the implementation manifest.

## Core API and state contracts

The core module defines immutable `TangentEvaluationPacket`,
`TangentPath`, `VersionedOperatorPacket`, `TangentPathComparison` and
`TangentPathCaseResult` records. It provides:

`load_frozen_design`, `validate_frozen_design`, `build_exact_path`,
`build_declared_lagged_path`, `build_tg03_packets`,
`compare_tangent_paths`, `validate_operator_versions`,
`classify_tangent_case` and `execute_tangent_path_case`.

Module import has no case execution, file creation, environment mutation or
shared mutable physical-state initialization.

## Frozen tangent-path mapping

### L2-TG-01

Two fresh safe transactional hosts follow the same exact-current path. Each
path has three evaluations. The implementation requires exact equality of
each residual, tangent, correction, candidate fingerprint and accepted
fingerprint. The frozen expected classification is
`PASS_SAME_TRACK_REPEATABILITY`.

### L2-TG-02

The exact-current path uses three evaluations. The declared one-iteration
lagged tangent path uses four evaluations. Both retain the same residual
definition, load and initial committed state. They are required to reach:

- accepted `u=21/1000`;
- accepted `sigma=11/10`;
- accepted `epsilon_p=1/100`;
- accepted `kappa=1/100`.

Different iteration counts are permitted and are not themselves failures.
The frozen expected classification is
`PASS_DECLARED_LAGGED_TANGENT_PARITY`.

### L2-TG-03

At `u=3/100` and `F=1/2`, both packets retain the same finite numerical
operator:

- `sigma=13/11`;
- `epsilon_p=kappa=1/55`;
- `R=15/22`;
- `K=100/11`.

The mismatch packet changes only tangent state-version metadata. Operator
version validation must reject it before correction, commit, accepted output
or physical interpretation. The committed state must remain unchanged and
accepted output must be unreachable. The frozen expected classification is
`REJECT_VERSION_MISMATCH_BEFORE_LIFECYCLE_VERDICT`.

## Independent Fraction oracle

The oracle imports only Python standard-library `fractions.Fraction` and
does not import the implementation module. A separate static recomputation
confirmed:

| Quantity | Exact result |
|---|---|
| Exact `u` sequence | `0/1, 11/1000, 21/1000` |
| Exact residual sequence | `-11/10, -1/11, 0/1` |
| Exact used-tangent sequence | `100/1, 100/11, 100/11` |
| Lagged `u` sequence | `0/1, 11/1000, 131/11000, 21/1000` |
| Lagged residual sequence | `-11/10, -1/11, -10/121, 0/1` |
| Lagged used-tangent sequence | `100/1, 100/1, 100/11, 100/11` |
| TG-03 residual | `15/22` |
| TG-03 tangent | `100/11` |

Result: **PASS_STATIC_INDEPENDENT_FRACTION_RECHECK**.

## Runner authorization boundary

`run_l2_d3.py` has a main guard and accepts one case ID plus one run ID per
process. Execution requires both:

- command-line flag `--execute-authorized`;
- environment variable `L2_D3_EXECUTION_AUTHORIZED=YES`.

Static AST inspection confirmed that both locks are checked before case
execution and before output-directory creation. The runner was not invoked.

## Static QA results

| Check | Result |
|---|---|
| Freeze JSON and case-matrix CSV parse | PASS |
| Implementation manifest JSON parse | PASS |
| Four Python files AST parse | PASS |
| Four Python files source-only `compile(..., exec)` | PASS |
| Core required class and API declarations | PASS |
| Independent Fraction recomputation | PASS |
| Runner main guard and double-lock ordering | PASS |
| New implementation module import side effects | Checked statically; no import was executed |
| Test execution | NOT RUN |
| Case execution | NOT RUN |
| Runner execution | NOT RUN |
| Abaqus execution | NOT RUN |
| Result directories created | NO |
| `__pycache__` created | NO |
| SVG/PDF/TIFF/PNG generated for L2-D3 | NO |

## Protected-file verification

- The 81 pre-existing L2 files retained aggregate SHA-256
  `15b5a1992a4b8c5e86676f82b8b3958f96677f9fc555c72f51fd30482affa671`.
  The aggregate uses lower-case SHA-256 values in case-insensitive
  relative-path order as `relative/path|sha256`, joined by LF with no final
  newline.
- The 17 protected Figure 1-5 files retained aggregate SHA-256
  `bdb4fa878ab18fc97e1deb8b95b40dd48024ee4cbe1a7ffac2be8c760acdb425`.
- Claim Matrix v0.5 retained
  `07323ebf5b1d15a2e64eb68199a592d3a323938339f7d51c52e0dc380867522c`.
- Manuscript v0.5 retained
  `d7184d814c39d0fd62f798d468a4d6da57474dd1714176b9403207c523eb89e3`.
- D1/D2 source, result, freeze and manifest files were not modified.

The three authorized governance documents were updated only after static QA:

| Governance file | Final SHA-256 |
|---|---|
| `STATUS.md` | `ba79439a8754791c90b6abe82fcdf7d18a2e7f98cbfe6a3a0a9794bb88f888b3` |
| `07_global_roadmap.md` | `a7709926aabf536dd78bfb52e9d541a7790e5cc92f1e81f7cffccdc2bfbb3f7b` |
| `08_execution_backlog.md` | `3a1fd43a43f2e2a4a2cd98311fdafa4d4193011569d8a26df54e926767af7725` |

## Production and solver boundary

The active production Git repository under
`${PRODUCTION_WORKSPACE_EXCLUDED}/Shenhua_UEL_full_model_20260423`
retained zero tracked changes, zero staged changes and 53 existing
`git status --short` entries. Its LF/no-final-newline status fingerprint
remained
`4def4e7d6c4b5369caa9c0582324f6d2470861f5b07ce57b51e9fd08e18c6e7f`.

Abaqus `standard`, `pre`, `SMASimUtility` and `ABQcaeK` process count
was zero. No Git add, commit, clean, move or delete operation was performed.

## Evidence boundary and next authorization

The final status is **IMPLEMENTED_NOT_EXECUTED**. This static implementation
does not support an OBSERVED-L2-D3, Abaqus, production, performance,
conservation, coupled-physics or application claim. The observed L2 boundary
remains 7/14 cases through L2-D2, and W3.4 remains NOT STARTED.

The only eligible next action is a separate user authorization for
`L2-TG-01`, `L2-TG-02` and `L2-TG-03`, each executed in two independent
single-process, single-thread repetitions. No such execution is authorized
by this static QA.
