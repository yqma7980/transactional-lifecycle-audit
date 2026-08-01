# P4d static freeze summary

## Decision

`P4d_DOLFINx_PETSc_MINIMAL_FE_HOST` is frozen as `FROZEN_NOT_IMPLEMENTED`.

The future host case is a 2D anti-plane elastoplastic unit-square problem with:

- 32 P1 triangular elements;
- 96 ordered integration points;
- two plastic-strain components plus one accumulated plastic variable per integration point;
- loading, unloading and reloading;
- DOLFINx assembly, PETSc SNES/backtracking line search, author-owned outer transactions and the retained PETSc C observation pattern.

## Frozen matrix

Nine future cases are defined:

1. analytical manufactured elastic reference;
2. independent elastic/plastic constitutive oracle;
3. safe direct accepted path;
4. PETSc-native nonaccepting line-search history;
5. safe driver-owned failed-attempt/retry history;
6. fresh-process checkpoint/restart history;
7. seeded hidden trial-cache negative control;
8. rejected-candidate output-provenance negative control;
9. pre-correction operator-version guard.

Each future formal case requires two fresh single-process, single-thread repetitions. No case has been implemented or run.

## Retained P4c layer

The P4c official PETSc C observation approach is a mandatory dependency because pure petsc4py did not expose the complete structured line-search ledger. The scalar P4c binary is not reused as FE evidence. A new observer-only attachment must first prove read-only access to the exact DOLFINx-owned SNES; otherwise P4d stops at `BLOCKED_C_BRIDGE_ATTACH`.

## Evidence boundary

This package supports only a static implementation decision. It does not support an `OBSERVED-P4D` claim, a manuscript claim expansion, MPI/thread safety, performance, contact, damage, two-way flow-mechanics, Abaqus, production UEL or carbon-storage conclusions.

## Next separately authorized task

`P4d.1_IMPLEMENTATION_PREFLIGHT` may implement only:

- C observer attachment zero case;
- independent material/manufactured oracles;
- deterministic mesh/state allocation;
- safe single-increment smoke test.

It must stop before the 9-case formal matrix unless separately authorized after all preflight gates pass.
