# P5B.3 held-out formal execution report

Status: HELD_OUT_COMPLETE_FROZEN_MATRIX_COMPLETE.

Four predeclared held-out cases were each executed in two fresh,
single-process, single-thread repetitions. All eight runs matched the
frozen four-way verdict, and every duplicate semantic gate passed.

| Case | Subject | Expected and observed verdict | Runs | Duplicate |
|---|---|---|---:|---|
| P5B-DETECT-05 | JSS-S01 | DETECT_LIFECYCLE_DRIFT | 2/2 | PASS |
| P5B-INVALID-05 | JSS-S01 | INVALID | 2/2 | PASS |
| P5B-NS-05 | JSS-S02 | NOT_SUPPORTED | 2/2 | PASS |
| P5B-PASS-05 | JSS-S01 | PASS_INVARIANT | 2/2 | PASS |

## Evidence boundary

This package establishes the outcomes of four frozen held-out cases
under the existing P5B adjudication contract. INVALID and
NOT_SUPPORTED are bounded decisions rather than failed solves.
The results do not estimate population detection or false-positive
rates, performance, thread safety, Abaqus behavior, production-model
readiness, or general solver safety.
