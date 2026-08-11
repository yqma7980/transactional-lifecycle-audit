# P5B acceptance gates

## Gate B0: protected design

- Every P5A input and design hash matches the source manifest.
- The matrix contains 20 unique cases: five expected cases for each four-way
  verdict.
- Exactly four held-out cases exist, one per verdict.
- execution_authorized remains false until implementation preflight passes.

## Gate B1: implementation preflight

- Adjudication follows the frozen precedence.
- INVALID cases stop before drift evaluation.
- NOT_SUPPORTED cases record a missing access plane or event.
- F08 unit tests distinguish pre-comparison and within-history mismatch.
- All adapters emit the common case-result schema.
- Safe-null, import-side-effect, unauthorized-case, no-write, and duplicate
  normalization tests pass.

## Gate B2: development formal execution

- The 16 development cases run twice in independent fresh processes.
- Semantic duplicate comparison passes for every pair.
- Expected and observed verdicts are reported without recoding.
- Every adverse, invalid, unsupported, or execution-error outcome is retained.
- Development evidence is hash-frozen before held-out access.

## Gate B3: held-out confirmation

- Only the four frozen held-out IDs are unlocked.
- Each runs twice in fresh processes.
- No replacement, tuning, or additional case is permitted.

## Gate B4: RQ1 analysis

- Report the complete expected-by-observed four-way confusion table.
- Report execution errors separately.
- INVALID and NOT_SUPPORTED do not enter sensitivity or specificity.
- Benign PASS controls enter only the finite control denominator.
- No population accuracy, universal specificity, or solver-certification claim
  is permitted.

