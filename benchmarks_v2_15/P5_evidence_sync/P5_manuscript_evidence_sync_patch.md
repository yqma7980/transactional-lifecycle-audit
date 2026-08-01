# P5 manuscript evidence-sync patch for v2.14

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
