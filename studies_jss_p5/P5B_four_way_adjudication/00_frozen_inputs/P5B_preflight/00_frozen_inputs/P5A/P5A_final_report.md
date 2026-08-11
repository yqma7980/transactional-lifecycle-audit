# P5A verdict semantics and preregistration final report

## Final status

`PASS_P5A_STATIC_FREEZE`

P5A is a static scientific-design freeze. It introduces no new runtime result
and does not alter the immutable P4 17-case evidence.

## Scientific decisions frozen

1. Verdict adjudication is ordered as applicability, eligibility, then
   lifecycle effect. An unsupported evidence plane yields `NOT_SUPPORTED`; an
   incompatible pre-comparison packet yields `INVALID`; an eligible comparison
   with an internal lifecycle violation yields `DETECT_LIFECYCLE_DRIFT`; an
   eligible invariant comparison yields `PASS_INVARIANT`.
2. Existing F08 evidence remains `DETECT_LIFECYCLE_DRIFT` because the paired
   histories begin from the same eligible packet and the mismatch is emitted
   inside one history. A mismatch already present between the declared replay
   packets is a newly frozen `INVALID` control.
3. P5B contains 20 cases: five cases for each four-way verdict, including five
   benign lifecycle variations and one held-out case per verdict.
4. P5C freezes 24 versioned candidates, eight per subject, and 12 prospective
   localization cases. B3 and B6 must return complete ordered permutations of
   the same identifiers; no post-hoc remapping is permitted.
5. P5D contains 18 performance cells: three subjects, two workload sizes, and
   three instrumentation modes. Every cell requires two unreported warm-ups
   and ten timed fresh processes. Output and production-trajectory equivalence
   are prerequisites to timing interpretation.
6. The 450 AEDS timing runs are historical background only and cannot enter
   JSS RQ5.

## Claim boundary

The proposed Claim Matrix keeps P4 observations separate from P5A designs.
P5B, P5C, and P5D remain `FROZEN_NOT_IMPLEMENTED`; none may be reported as a
Result until its implementation preflight and formal branch have completed.
The existing B3/B6 result remains bounded complementarity with exact McNemar
`p=0.125`, not superiority.

## Static QA

The machine-readable QA completed 39 checks with status
`PASS_P5A_STATIC_FREEZE`. It verified protected input hashes, JSON/CSV schema,
balanced verdict counts, held-out partitions, localization ontology membership,
the 18-cell performance matrix, authorization locks, and the absence of result
or run directories.

## Execution and workspace boundary

- No P5B, P5C, P5D, Abaqus, production UEL, or other benchmark case was run.
- Exact Abaqus process count at final boundary audit: zero.
- No manuscript, Figure, GitHub, Zenodo, DOI, or historical result was changed.
- An initial patch invocation used the production working directory and created
  three P5D duplicates under an otherwise new `04_performance` directory. The
  three files were byte-for-byte SHA-256 matched to the staging copies, then
  individually removed together with the empty directory. The final production
  residual P5A-directory count is zero.
- The production path contains an empty `.git` directory and is not recognized
  by Git as a repository; a clean Git-status claim therefore cannot be made.

## Authorized next step

The next step is a separate `P5B_IMPLEMENTATION_PREFLIGHT`: implement only the
four-way adjudication API and frozen adapters, then run unit/schema/import-side-
effect/authorization/safe-null tests. Formal P5B execution remains unauthorized
until that preflight passes without changing this freeze.
