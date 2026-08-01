# L4-D1 pre-execution implementation erratum

Status: PRE_EXECUTION_IMPLEMENTATION_CORRECTION

Evidence status: ESTABLISHED for the code-contract correction; no formal L4 result exists yet.

## Scope

The frozen scientific model, case matrix, analytical oracle, tolerances, mesh and time-step schedules are unchanged. This erratum records three implementation-only corrections found before any formal case execution.

1. The first import route entered the legacy L2_host_lifecycle.src package initializer and its benchmark imports. L4 now loads the authoritative l2_state.py serializer source directly and reuses its canonical_hash; no second serializer was introduced.
2. normalized_defect(defect) incorrectly called max with a single scalar when no optional scales were supplied. The call now evaluates a tuple whose first entry is 1.0.
3. The safe-retry classifier incorrectly required the floating-point phase-balance defect to equal exactly zero. The frozen contract requires exact replay drift and fingerprint parity, while phase balance uses the separately frozen 5E-12 gate. The classifier now applies that existing gate. The observed preflight value was 4.336808689942018E-18.
4. The first absolute-path runner launch stopped before import because the NCS package root was not on sys.path. No result directory or case output was created. The runner now inserts the resolved NCS root before importing the benchmark package.

## Verification

After these corrections, all 10 directed unit/preflight tests passed in one single-process, single-thread run. No result directory existed before or after the tests. No formal case, Abaqus process, production model or Git operation was executed.

This document does not establish OBSERVED-L4; formal independent-process repetitions remain required.
