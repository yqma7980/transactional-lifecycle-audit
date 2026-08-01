# P4d.1 PETSc observer ABI contract

Status: `FROZEN_BEFORE_BRIDGE_EXECUTION`

## Identity

The bridge is compiled inside the pinned `linux/amd64` DOLFINx image and is
loaded only by the same Python process that owns the target
`dolfinx.fem.petsc.NonlinearProblem`.  The target object is
`problem.solver`; the bridge may not create or replace an SNES.

The only public attachment entry point is:

```c
int P4dObserverAttach(
    uintptr_t snes_handle,
    const char *output_path,
    const char *schema_version,
    const char *observer_build_hash,
    const char *solve_id,
    char *error_buffer,
    size_t error_buffer_size);
```

Python passes `petsc4py.PETSc.SNES.handle` as an unsigned integer whose width
must equal `sizeof(void*)`.  Before registering callbacks, the C side verifies
that the pointer has PETSc class id `SNES_CLASSID`, obtains its type through
`SNESGetType`, and obtains its existing line search through
`SNESGetLineSearch`.  Failure of any check rejects attachment before solving.

## Read-only callback contract

The bridge registers:

- `SNESLineSearchMonitorSet` to observe attempted work vectors;
- `SNESLineSearchSetPostCheck` to observe the selected work vector and lambda;
- `SNESMonitorSet` to record accepted nonlinear-iteration states.

The post-check always sets `changed_direction=PETSC_FALSE` and
`changed_work=PETSC_FALSE`.  No callback may write a PETSc vector, replace the
line search, set lambda or reason, alter options, evaluate material state, or
commit user state.

Each JSONL row contains the schema and build identities, solve id, callback
kind, ordinal, nonlinear iteration, line-search reason, lambda in hexadecimal,
and exact hexadecimal arrays for available X/F/Y/W/G vectors with sizes.

## Attachment and no-effect gates

The bridge attaches to the exact DOLFINx-owned SNES used by the zero case.  An
observer-disabled solve and an observer-enabled solve use identical initial
state and options.  They must agree exactly in solution hexadecimal values,
SNES reason, iteration count and residual-norm hexadecimal sequence.

Two observer-enabled fresh processes must agree after removing only run id,
absolute path and environment-record timestamp.  At least one line-search
monitor work vector must differ from the corresponding selected post-check
work vector, giving a structured native nonaccepting candidate.  Otherwise G2
is `BLOCKED_C_BRIDGE_ATTACH`.

## Evidence boundary

Successful attachment demonstrates observer ABI compatibility and read-only
host-event visibility only.  It does not establish constitutive rollback,
accepted-output provenance, P4d formal evidence, production readiness, or
parallel callback ordering.
