
# P4d.5 branch-resumption acceptance gates

Status: `FROZEN_STATIC_NOT_IMPLEMENTED`

## 1. Protected-evidence gate

Before implementation and again before every future case, recompute every source hash in `P4d5_source_manifest.json`. P4d.0-P4d.4 files are immutable. The original line-search failure and all diagnostic outcomes remain preserved.

## 2. Host and execution identity

Future execution must use the pinned `dolfinx/dolfinx` image digest, `linux/amd64`, network disabled, one MPI rank, one process and one thread. Each case/run is a fresh container. Two repetitions are required per case. Output overwrite is forbidden.

## 3. Inherited prerequisites

The two-run formal passes of `P4D-REF-01`, `P4D-CONST-01` and `P4D-SAFE-DIR-01` are inherited only as immutable prerequisites. They are not rerun and are not counted as new P4d.5 processes.

## 4. Common mechanics and lifecycle gates

The numerical model, grid, material constants, load histories, tolerances and independent oracles remain those frozen by P4d.0. All values must be finite; accepted solves require positive SNES reason; free-DOF residual, reaction balance, yield consistency and bounded-state gates remain unchanged. Residual/Jacobian/observer callbacks must not mutate committed state. Accepted output must be written only after a selected candidate is committed.

## 5. Branch-specific gates

### B-RETRY: `P4D-SAFE-RT-01`

The predeclared `max_it=1` attempt from accepted load `0.08` to target `0.20` must return a negative PETSc reason. If it converges, return `NOT_SUPPORTED_FORCED_RETRY_TRIGGER`; do not change `max_it`. Before retry to `0.10`, primary, committed, persistent and semantic accepted-state projections must equal the pre-attempt state. The first retry operator packet must match the direct history within the existing `1e-10` tolerance.

### B-RESTART: `P4D-SAFE-RS-01`

A checkpoint may be written only after the direct path accepts load `0.12`. Continuous and fresh-process restart histories require exact mesh, material, schema, version and committed discrete hashes, followed by accepted-field and operator parity under the existing frozen tolerances. This is author-managed checkpoint/restart, not PETSc TS restart.

### B-VERSION: `P4D-VER-01`

The mismatched residual/tangent version packet must remain numerically identical to its matched control (`Delta R=0`, `Delta J=0`) and be rejected before correction, commit, checkpoint or accepted output.

### B-RETRY-CACHE: `P4D-NC-CACHE-01`

This case is eligible only after `P4D-SAFE-RT-01` formally passes. The primary verdict is `FAIL_PERSISTENT_STATE_RESTORATION`. If persistent identities differ, any finite operator drift is a secondary operator-sensitivity observation, not an admissible equal-persistent-state replay verdict. The existing `1e-10` drift threshold is not changed.

### B-RETRY-OUTPUT: `P4D-NC-OUTPUT-01`

This case is eligible only after `P4D-SAFE-RT-01` formally passes. A rejected candidate reaching accepted output or a feedback mirror must produce `FAIL_REJECTED_CANDIDATE_REACHABILITY`, even if final physical fields remain equal.

## 6. Duplicate-run gate

For each case, two fresh-process results must agree after removal of run ID, timestamps and absolute paths. Scientific fields, event ordering, verdicts and canonical hashes must match exactly unless a predeclared floating-point field uses an existing tolerance. No failed repetition may be discarded.

## 7. Branch-local stopping and final adjudication

A branch failure stops only its descendants. Independent branches continue in the separately authorized future execution. Even if all five P4d.5 cases pass, the strongest allowed aggregate status is `PARTIAL_OBSERVED_P4D_WITH_NATIVE_LINESEARCH_NOT_SUPPORTED`; `P4D_MATRIX_PASS` and native rejected-line-search coverage remain forbidden.

## 8. Current execution boundary

This freeze authorizes no implementation, unit test, runner, Docker container or FE case. It creates no `results`, `execution`, `output` or `run_*` directory and does not update the manuscript, Claim Matrix, figures or public archives.
