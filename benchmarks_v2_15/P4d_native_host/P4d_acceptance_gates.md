# P4d acceptance gates and stop rules

Status: `FROZEN_NOT_IMPLEMENTED`

No gate in this document has been executed. Thresholds may not be changed after a future run is observed.

## 1. Pre-implementation gates

### G0 - protected evidence

- v2.13 aggregate remains `d5c8dbae6275171a7bb314cb6582457ca3a6145c0ba773f1f83eff34fe65d919`.
- P2, P3, P4 and P4c protected manifests match the hashes in `P4d_execution_freeze.json`.
- P4c raw runtime evidence is read-only.

Failure: `BLOCKED_PROTECTED_EVIDENCE_DRIFT`.

### G1 - immutable host

- exact DOLFINx image digest and linux/amd64 platform match the freeze;
- future runs are network-disabled, unprivileged, one rank and one thread;
- DOLFINx, PETSc, petsc4py, Basix, UFL and mpi4py versions and module hashes are recorded twice.

Failure: `BLOCKED_HOST_IDENTITY`.

### G2 - C observer attachment

Before a mesh is created, an observer-only shared library must attach to the exact SNES object owned by `dolfinx.fem.petsc.NonlinearProblem`. A one-DOF zero case must reproduce structured PETSc line-search vectors, lambda and reason without changing the solution or options.

Text monitor parsing, callback counts or a separate C-owned SNES do not satisfy this gate.

Failure: `BLOCKED_C_BRIDGE_ATTACH`.

### G3 - deterministic FE topology

The 32-cell/25-node mesh, boundary DOFs and 96 quadrature records must match the frozen recipe. Coordinates, connectivity, cell order, quadrature points and weights receive exact canonical hashes.

Failure: `BLOCKED_FE_TOPOLOGY_OR_ORDER`.

### G4 - independent oracles

- manufactured elastic forcing is generated from the analytical solution, not from the FE output;
- elastic and plastic material packets match `P4d_reference_oracle_contract.json`;
- the consistent tangent passes a directional finite-difference check at frozen points with relative error at most `1e-7`;
- oracle code and host implementation may share constants but not the same update routine.

Failure: `BLOCKED_REFERENCE_ORACLE`.

## 2. Conventional mechanics gates

These gates are reported separately from lifecycle verdicts.

### M1 - finite and bounded state

- no NaN, Inf or absolute value above `1e100`;
- `alpha >= -1e-14`;
- committed `alpha` is nondecreasing at each integration point;
- trial state may not overwrite the accepted arrays.

### M2 - nonlinear convergence

For a normal accepted attempt:

- PETSc SNES converged reason is positive;
- final residual meets the frozen SNES tolerances;
- no accepted output or commit occurs when the reason is zero or negative.

The designated forced-retry attempt is expected to have a negative reason and is not judged by M2 as an accepted increment.

### M3 - equilibrium

At every accepted load:

- normalized free-DOF residual at most `1e-10`;
- normalized top/bottom reaction imbalance at most `1e-10`;
- plastic yield consistency `|q-(tau_y0+H alpha)| / max(1,tau_y0+H alpha) <= 1e-9` at committed plastic points.

### M4 - manufactured reference

`P4D-REF-01` must satisfy all four error/order thresholds in the problem specification and monotone error decrease. Failure stops all path-dependent formal cases.

## 3. Lifecycle gates

### L1 - committed immutability

Every residual, Jacobian, line-search and failed-attempt event must leave the committed state hash and accepted version unchanged. Only `AcceptCommit` may change them.

### L2 - candidate reconstruction and operator packet

Each trial candidate must be reconstructed from the same committed source state. Residual and tangent must reference the same material candidate in `EXACT_CURRENT` mode or satisfy the explicit `DECLARED_ACCEPTED_STATE_LAG` relation.

### L3 - native line-search evidence

`P4D-SAFE-LS-01` requires at least one PETSc C-observed work vector that is not selected as the line-search result, plus the selected lambda and reason. The same event must correlate with the Python material-candidate ledger by vector content and solve/iteration identity.

If the frozen history yields no such event, classify `NOT_SUPPORTED_BY_FROZEN_HISTORY` and stop; do not alter the load, tangent mode or line-search options.

### L4 - safe retry restoration

The predeclared `max_it=1` attempt from accepted `0.08` to target `0.20` must end with a negative PETSc reason. Before the retry to `0.10`, the primary, committed, persistent and semantic accepted-state projections must equal the pre-attempt state. The first retry residual/Jacobian packet must match the direct history within `1e-10`.

If the attempt converges, classify `NOT_SUPPORTED_FORCED_RETRY_TRIGGER` and stop dependent cases without changing `max_it`.

### L5 - safe restart parity

The continuous and fresh-process restart histories must have:

- exact mesh/material/schema/version hashes;
- exact accepted load and index;
- exact committed discrete hashes;
- primary, reaction, stress and history arrays equal within `1e-10`;
- no diagnostic-only field entering physical state.

### L6 - accepted-output provenance

Every accepted row must reference a candidate selected by a positive SNES solve and then committed by the driver. No rejected or failed-attempt candidate may appear in accepted output. Trial diagnostics are stored separately.

### L7 - version guard

An undeclared residual/tangent state-version pair must be rejected before:

- linear correction formation;
- primary-vector update;
- material commit;
- checkpoint write;
- accepted output.

The mismatch packet remains finite and has the same numeric residual and tangent as its matched control.

## 4. Case-specific scientific verdicts

| Case | Required primary verdict | Required secondary result |
|---|---|---|
| `P4D-REF-01` | `REFERENCE_GATE_PASS` | analytical convergence gates pass |
| `P4D-CONST-01` | `CONSTITUTIVE_ORACLE_PASS` | exact elastic/plastic packets |
| `P4D-SAFE-DIR-01` | `PASS_REPLAY_INVARIANCE_WITHIN_TESTED_CLASS` | baseline mechanics gates pass |
| `P4D-SAFE-LS-01` | `PASS_REPLAY_INVARIANCE_WITHIN_TESTED_CLASS` | native nonaccepting line-search event and accepted-field parity |
| `P4D-SAFE-RT-01` | `PASS_REPLAY_INVARIANCE_WITHIN_TESTED_CLASS` | exact restoration and retry parity |
| `P4D-SAFE-RS-01` | `PASS_REPLAY_INVARIANCE_WITHIN_TESTED_CLASS` | fresh-process checkpoint parity |
| `P4D-NC-CACHE-01` | `FAIL_PERSISTENT_STATE_RESTORATION` | finite operator drift above `1e-10` is secondary |
| `P4D-NC-OUTPUT-01` | `FAIL_REJECTED_CANDIDATE_REACHABILITY` | accepted-output provenance false while physics may remain equal |
| `P4D-VER-01` | `EXPECTED_REJECT_OPERATOR_VERSION_MISMATCH_BEFORE_CORRECTION` | numeric `Delta R=0`, `Delta J=0` |

The case contract passes only when the observed primary and secondary outcomes match this table. The manuscript must never state that an unsafe implementation passed.

## 5. Duplicate-run gate

Each future formal case is executed in two fresh, single-process, single-thread containers. After removing only `run_id`, wall-clock timestamp and absolute path:

- semantic result JSON must match;
- event sequence and scientific fields must match;
- case classifications must match;
- exact discrete hashes must match;
- numerical arrays must satisfy the frozen scaled comparison.

A duplicate mismatch stops evidence synchronization.

## 6. Stop rules

Stop and preserve the evidence if:

- a protected hash changes;
- the C observer needs a DOLFINx or PETSc core patch;
- a native event can only be inferred retrospectively;
- the mesh/order/oracle differs from the freeze;
- a prerequisite case fails;
- an accepted output is written before commit;
- a negative control is tuned after observation;
- a threshold, load, seed or material parameter must change to obtain the expected verdict;
- two fresh-process repetitions differ;
- implementation would require production UEL, Abaqus, COMSOL or a public-repository change.

No alternative case may be substituted automatically.
