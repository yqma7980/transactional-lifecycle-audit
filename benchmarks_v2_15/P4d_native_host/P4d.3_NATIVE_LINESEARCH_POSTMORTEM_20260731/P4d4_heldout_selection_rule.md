# P4d.4 held-out selection rule

## Diagnostic execution requirement

After separate authorization, execute DIAG-LS-01, DIAG-LS-02, and DIAG-LS-03 exactly once each. All are exploratory and must be completed even if an earlier target triggers an unselected candidate. Do not tune parameters or add a fourth diagnostic target.

## Trigger definition

A diagnostic triggers only when all conditions hold:

1. SNES reason is positive.
2. At least one structured unselected line-search candidate is present.
3. Every C candidate has an exact Python TrialEvaluate primary-vector correlation.
4. Mechanics and finite gates pass.
5. The observer remains read-only.

## Deterministic held-out mapping

- If 0.20 is the first triggering target, select held-out target 0.22.
- If 0.24 is the first triggering target, select held-out target 0.26.
- If 0.28 is the first triggering target, select held-out target 0.30.
- If none triggers, adjudicate NOT_SUPPORTED_BY_DIAGNOSTIC_ENVELOPE.

## Future formal requirement

The selected held-out target must include an exact-current direct control and a declared-accepted-state-lag native line-search case, each repeated in two fresh single-process, single-thread runs. This document does not authorize those runs.
