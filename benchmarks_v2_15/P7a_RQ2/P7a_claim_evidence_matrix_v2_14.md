# Claim-evidence matrix v2.14 draft

Date: 2026-08-01  
Status: `P7A_BOUNDED_EVIDENCE_SYNC_COMPLETE`  
Supersedes: none; v2.13 and the root v2.2 claim matrix remain historical baselines  

## Evidence states used here

- `ESTABLISHED`: definition, conditional derivation or directly checked artifact fact.
- `OBSERVED-*`: result observed under a named frozen protocol.
- `PROPOSED`: v2.14 method or verdict not yet formally frozen/executed.
- `OPEN`: required evidence absent.
- `NOT_SUPPORTED`: current host or design cannot support the claim.

## Matrix

| ID | Candidate claim | Current status | Direct evidence | Supports | Does not prove | Next gate |
|---|---|---|---|---|---|---|
| V14-C01 | A rejected trial can change rollback-external user state and later finite operators while the visible committed state remains unchanged. | `OBSERVED-L0/L1/L2/FEH-SENSITIVITY` | Existing scalar, material, host and FEH controls; v2.13 FEH source tables | Existence of the seeded failure mode in tested implementations. | Frequency in real software; all hidden-state faults; Abaqus behavior. | Preserve as bounded motivation. |
| V14-C02 | A lifecycle declaration can separate state ownership, restoration responsibility, admissible history, operator version and semantic output provenance. | `ESTABLISHED/PROPOSED` | P2 state-transition definition; v2.13 projection declarations | A testable protocol structure. | Completeness of any model-specific field inventory. | Freeze schema and model declarations. |
| V14-C03 | Under explicit ownership, closed projection, restoration, version, provenance and determinism assumptions, eligible histories should satisfy the declared replay relation. | `ESTABLISHED_CONDITIONAL` | P2 design contract and counterexamples | Conditional reasoning and necessary audit fields. | Universal theorem; proof of dependency closure from finite tests. | Formal review and notation audit. |
| V14-C04 | Safe direct, rejected-line-search, cutback and restart histories preserve the frozen relations in the existing FEH host. | `OBSERVED-FEH-D0` | FEH-LC-01--04, two fresh-process repetitions each | Bounded safe-history parity for a 48-element, 192-integration-point anti-plane host. | Native external-host lifecycle, parallelism, complex contact/damage or production FE. | Retain with narrower host description. |
| V14-C05 | FEH-NC-01/02 show finite operator drift after persistent trial-cache/output-mirror divergence. | `OBSERVED_OPERATOR_SENSITIVITY`; formal v2.14 lifecycle verdict `PROPOSED` | v2.13 FEH case source and raw JSON | Finite sensitivity and reproducibility of the seeded controls. | A formal v2.14 restoration-failure verdict without a prospective v2.14 freeze. | Freeze lifecycle ownership and rerun only if authorized. |
| V14-C06 | MUT-D0 contains a nonempty tested strength interval in which conventional gates pass while operator drift exceeds its frozen threshold. | `OBSERVED-MUT-D0-OPERATOR-SENSITIVITY` | 46 MUT records; strengths `1e-10` through `1e-2`; confirmation at `1e-6` | One mutation-family sensitivity interval under the existing threshold. | Full TLA detection boundary; fault coverage; sensitivity/specificity or miss probability. | New threshold and lifecycle-mutation protocol. |
| V14-C07 | In the bounded retrospective F05/F07 comparison, lifecycle-ledger audit adds owner/event/source localization beyond final-state regression, matched operator-version checks and generic equal-input replay. | `OBSERVED-P6R-BOUNDED-PARTIAL` | P6R 60 method cells across five cases and ten read-only projection processes | Bounded diagnostic-localization increment for two frozen fault families; the null control remained quiet. | Checkpoint/restart or component-fingerprint comparison; held-out validation; incremental detection beyond generic replay; general superiority. | Eligible for P8 only with retrospective and applicability boundaries. |
| V14-C08 | The protocol detects and localizes selected lifecycle faults without alarming on the bound null control. | `OBSERVED-P5/P6R-BOUNDED-MIXED` | P5 F05/F07 family passes, P6R null/F05/F07 method projection, and preserved F01/F02 non-support | Bounded evidence for two fault families and explicit non-support for two others. | Complete fault coverage, sensitivity/specificity, miss probability or population performance. | Report tested operators and evidence gaps without aggregation as a full pass. |
| V14-C09 | The open FE host demonstrates multi-element, multi-integration-point lifecycle behavior. | `OBSERVED-FEH-D0` | 48 Q1 elements, 192 integration points, heterogeneous plastic field | Nontrivial open FE proof of concept. | Independent lifecycle orchestration; large-scale, contact, damage or multiphysics generality. | Native-host feasibility gate. |
| V14-C10 | TLA transfers to a native DOLFINx/PETSc finite-element backend with auditable state and operator packets. | `OBSERVED-P4D/P5-BOUNDED` | P4d branch evidence and P5 full-backend runs | Native FE backend transfer for the executed direct, driver-retry, restart, output, version and scaled-mutation paths. | Native rejected line-search candidate coverage, Abaqus behavior, parallel safety or production readiness. | Keep native line-search non-support explicit. |
| V14-C11 | A version mismatch can be rejected before correction, commit and accepted output. | `OBSERVED-L2-D3/FEH-NC-03/L6` | Preserved version-contract cases | Feasibility of pre-correction version enforcement in tested adapters. | Enforcement by arbitrary hosts or Abaqus. | Include in same-fault comparison. |
| V14-C12 | Accepted output can be tied to authoritative committed state and kept unreachable from rejected candidates. | `OBSERVED-L2-D4/FEH-SAFE/L6` | Output-provenance controls | Bounded provenance enforcement. | Safety of arbitrary output pipelines and restart files. | Native-host output gate. |
| V14-C13 | Full-provenance instrumentation cost is workload dependent. | `OBSERVED-PERFORMANCE-D1` | 450 output-equivalent timing runs; cross-workload median `6.28%` | Machine/workload-specific cost distribution. | Universal low overhead, scaling or speed-up. | Retain; add native-host cost only if outputs match. |
| V14-C14 | Current public and supplementary packages preserve source data, failures and manifests for the reported standalone evidence. | `OBSERVED-LOCAL_PACKAGE`; public synchronization pending | v2.13 package, manifests and prior public records | Local artifact traceability. | That public v1.0.0 already contains prospective v2.14 methods/results. | Defer DOI/release update until science freeze. |
| V14-C15 | TLA is a universal computational-mechanics reliability theory. | `NOT_SUPPORTED` | Explicit scope limitations | No authorized positive claim. | Universal safety, completeness or correctness. | Keep rejected. |
| V14-C16 | The work validates Abaqus, production UELs, threaded execution, two-way coupling, fault mechanics or CO2 predictions. | `OPEN/NOT_SUPPORTED` | No corresponding formal evidence | No authorized positive claim. | All listed applications. | Separate future research only. |

| V14-C17 | The P5 numerical null envelope is stable under fresh-process calibration and confirmation. | `OBSERVED-P5` | Six exact-null, six arithmetic-null and two confirmation processes | Frozen metric thresholds and a bounded numerical-null reference. | A universal machine-independent threshold. | Preserve environment identity and thresholds. |
| V14-C18 | F05 and F07 satisfy the frozen adjacent-strength and fresh-process verification rules. | `OBSERVED-P5-FAMILY-PASS` | Fifteen strengths per family plus two fresh repetitions at each of two adjacent selected levels | Bounded family-level detection and repeatability in the P5 FE backend. | A full P5 matrix pass or coverage of all persistence faults. | Eligible only as family-level evidence. |
| V14-C19 | F01 and F02 do not provide a distinctive conventional-quiet/operator-separated region under the frozen protocol. | `OBSERVED-P5-NOT-SUPPORTED` | Fifteen strengths per family; F01 threshold crossing; F02 dependency trace | A transparent non-support result and mechanism-bounded postmortem. | That the faults are absent, harmless, or undetectable under all histories. | Freeze the result; no interpolation or retuning. |
| V14-C20 | The complete P5 matrix passed. | `NOT_SUPPORTED` | Corrected P5 summary: F01/F02 non-support, F05/F07 pass | No authorized positive full-matrix claim. | Complete mutation-family coverage or general detection superiority. | P6 full entry remains closed. |
| V14-C21 | The P6R read-only projections reproduce their case-method packets exactly across each pair of fresh processes. | `OBSERVED-P6R-REPEATABILITY` | Five exact duplicate pairs for `method_results.csv` and `projection_packets.json` | Deterministic secondary projection under the frozen serial environment. | Independent-team replication, parallel determinism or FE rerun reproducibility. | Retain exact hashes in the Supplement. |
| V14-C22 | The complete P6 confirmation chain passed. | `NOT_SUPPORTED` | P5 full-entry decision and P6R scope declaration | No authorized positive full-P6 claim. | Held-out validation or complete comparator coverage. | Keep rejected. |
| V14-C23 | All six baseline methods were evaluated for F05/F07. | `NOT_SUPPORTED` | P6R applicability audit: M2 and M3 are not applicable | No authorized complete six-method claim. | Checkpoint/restart and component-fingerprint behavior. | Preserve the explicit evidence gaps. |

## Abstract eligibility after P7a

V14-C07 is eligible only as a bounded retrospective localization result: two selected fault families, four applicable methods, no held-out confirmation, and no detection-rate claim. V14-C08 remains a mixed bounded result. Existing eligible claims retain their earlier evidence boundaries.

## RQ2 adjudication

RQ2 status: `PARTIALLY_SUPPORTED_WITHIN_F05_F07_BOUNDED_RETROSPECTIVE_SCOPE`. The observed increment is causal localization, not a higher detection count than generic equal-input replay. M2 and M3 remain evidence gaps, so the comparison is not a complete baseline matrix.

## CMAME decision dependency

The same-fault evidence now supports a bounded methodological increment for F05/F07, while full comparator coverage, native rejected line-search coverage, held-out confirmation and complete P5/P6 remain unsupported. P8 may rewrite the paper around this narrower result but must not restore broader wording.
