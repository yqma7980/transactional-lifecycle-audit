# P5B.1 development execution protocol

Status: `FROZEN_BEFORE_DEVELOPMENT_EXECUTION`.

This additive freeze binds the already authorized 16-case DEVELOPMENT partition to concrete subject adapters. It does not alter the P5A case matrix, the P5B four-way adjudicator, expected verdicts, held-out partition, or protected hashes.

## Execution unit

Each invocation executes one case and one run ID (`run_1` or `run_2`) in one fresh process. S01 invocations re-enter the locally available digest-pinned DOLFINx container with one process, one MPI rank, one thread, and no network. S02 and S03 use fresh local Python processes. A result directory is created only after the case ID, run ID, CLI lock, environment lock, activation manifest, protected hashes, and DEVELOPMENT partition have passed.

## Runtime mapping

The exact case mapping is in `P5B1_CASE_RUNTIME_MAPPING.csv`. Numeric fault controls use the pre-existing lowest P2.2 strength, `ETA-LOW=1e-10`. The S01 premature-commit control uses the previously qualified active field `gamma_p[27,0,1]`. The S03 callback histories insert exactly two nonaccepting calls at `x=0.03` and `x=-0.03` in that order. These choices are frozen before any P5B DEVELOPMENT result exists.

PASS controls exercise legal lifecycle variation. DETECT cases require a compatible declared replay context plus an observed lifecycle signal. INVALID cases stop after applicability and precomparison eligibility; they do not execute lifecycle inference. NOT_SUPPORTED cases audit a native evidence plane and name the exact missing field or event.

## Formal outputs

Every run writes `case_result.json`, `runtime_observation.json`, `event_ledger.json`, and `case_manifest.json`. No run may overwrite another run. Duplicate QA removes only `run_id`, run-specific path labels, and event identifiers before semantic comparison.

## Held-out seal

`P5B-PASS-05`, `P5B-DETECT-05`, `P5B-INVALID-05`, and `P5B-NS-05` are absent from the runtime mapping. The existing `development_guard` rejects them before output-path creation. Completion of the 16 DEVELOPMENT cases does not authorize, generate, inspect, or unlock held-out execution.
