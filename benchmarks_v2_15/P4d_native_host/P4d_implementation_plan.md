# P4d implementation plan

Status: `FROZEN_NOT_IMPLEMENTED`  
Execution authorization: `false`

This plan records a future implementation order. It does not authorize source creation, compilation, unit tests or case execution.

## Stage I - protected baseline and package layout

1. Revalidate all hashes in `P4d_execution_freeze.json`.
2. Create a new implementation directory and a separate results root; do not edit P4c or earlier evidence.
3. Pin the immutable DOLFINx image, one rank, one thread and network-disabled runtime.
4. Define canonical JSON/array serialization once and use it for all P4d hashes.

Gate: no protected drift and no production mount.

## Stage II - observer attachment zero case

1. Extract an observer-only C module from the P4c API pattern.
2. Implement a narrow attachment ABI for an existing PETSc `SNES`.
3. Attach it to the exact SNES exposed by a DOLFINx nonlinear problem.
4. Repeat the P4c scalar globalization probe twice.
5. Compare with observer disabled and require identical solution, reason, iterations and residual sequence.

Gate: structured vectors, lambda and reason are available without a core patch or state modification. Otherwise stop at `BLOCKED_C_BRIDGE_ATTACH`.

## Stage III - independent oracles

1. Implement the Fraction material oracle in a module that imports no host constitutive code.
2. Implement the manufactured elastic forcing analytically.
3. Implement a stress-only directional finite-difference tangent check.
4. Unit-test the exact packets frozen in `P4d_reference_oracle_contract.json`.

Gate: exact packets and directional tangent threshold pass before the FE lifecycle code is executed.

## Stage IV - deterministic mesh and state store

1. Create the frozen 4x4 triangular unit-square mesh.
2. Build the scalar P1 space and frozen top/bottom boundary ordering.
3. Obtain the degree-2 triangle quadrature rule.
4. Allocate immutable committed arrays and call-local candidate arrays with the frozen shapes.
5. Record topology, quadrature and material hashes.

Gate: all counts and hashes satisfy G3. Any ordering change requires a new design revision before execution.

## Stage V - residual, Jacobian and version guard

1. Implement the constitutive evaluator as a pure function of trial strain and committed state.
2. Assemble residual and consistent tangent without mutating committed arrays.
3. Emit one material-candidate packet per primary-vector evaluation.
4. Implement `EXACT_CURRENT`, `DECLARED_ACCEPTED_STATE_LAG` and `UNDECLARED_MISMATCH` relations.
5. Reject an undeclared relation before passing a matrix to PETSc for correction.

Gate: unit tests prove committed immutability and version-guard reachability.

## Stage VI - transaction driver and I/O

1. Implement accepted load history and immutable source snapshots.
2. Commit only after positive SNES reason plus mechanics gates.
3. Implement the frozen max-iteration failed attempt and restoration.
4. Implement accepted output using the frozen schema.
5. Implement checkpoint write and fresh-process restart without pickle.

Gate: safe direct, retry and restart smoke cases agree at the first replay packet before formal runs.

## Stage VII - negative controls

1. Add the hidden trial-cache variant with exactly the frozen `1e-6` scale.
2. Add the rejected-output reachability variant.
3. Keep the safe code path unchanged.
4. Do not tune a seed after observing a result.

Gate: static inspection proves each variant changes only its declared owner/event pair.

## Stage VIII - preflight

Allowed preflight cases:

- one reference mesh level;
- one elastic and one plastic material packet;
- one safe direct increment;
- the observer attachment zero case;
- unauthorized-case and no-write runner checks.

Preflight is not formal evidence. If any prerequisite fails, preserve it and stop. Do not run the 9-case matrix.

## Stage IX - formal execution

Only after a separate authorization:

1. execute cases in the frozen order;
2. use two fresh, single-process, single-thread repetitions per case;
3. stop at the first prerequisite failure;
4. never overwrite a run;
5. freeze raw results before creating summaries;
6. compare duplicates after removing only run-specific diagnostic fields.

## Stage X - evidence synchronization

Only after all prerequisite formal gates pass:

- create the final P4d evidence package;
- update a new Claim Matrix and manuscript version;
- create source-data tables and an evidence contract;
- retain all bounded limitations;
- do not update DOI, GitHub or Zenodo without separate user direction.

## Files explicitly not created by this freeze

```text
src/
tests/
oracle/
runner/
results/
execution/
output/
checkpoints/
*.py
*.c
*.so
*.exe
```
