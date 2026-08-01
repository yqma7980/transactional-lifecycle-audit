# P4d.1 implementation preflight protocol

Status: `FROZEN_BEFORE_IMPLEMENTATION`

## Purpose

This protocol tests whether the frozen P4d design can be implemented in the
pinned DOLFINx/PETSc host.  It is not a formal benchmark and cannot create
`OBSERVED-P4D` evidence.

## Gate order

1. **G0 protected evidence.** Recompute all user-specified hashes using ordinal
   path ordering.  Any mismatch terminates as
   `BLOCKED_PROTECTED_EVIDENCE_DRIFT`.
2. **G1 immutable host.** Use only the locally present pinned image with
   `network=none`, one process, one rank and one thread.  Two fresh environment
   packets must agree after removing run identity and paths.
3. **G2 observer attachment.** Compile a new observer-only shared library in
   the pinned image, attach it to a DOLFINx-owned SNES, prove observer no-effect
   and duplicate equality, and expose a structured unselected line-search
   candidate.
4. **G4 independent oracle.** Derive elastic and plastic packets with
   `fractions.Fraction`, evaluate an independent manufactured solution on
   `N=4`, and perform the frozen directional tangent check.
5. **G3 deterministic topology and state.** Construct the frozen 4 by 4 mesh,
   deterministic cell and boundary ordering, degree-2 triangle quadrature and
   committed arrays.  Hash all canonical packets and prove trial evaluation
   leaves committed arrays unchanged.
6. **Safe increment smoke.** Run only `H_DIRECT`, load `0.00 -> 0.04`, with
   exact-current tangent.  Commit exactly once after positive SNES reason and
   mechanics gates; generate accepted output only after that commit.

The unusual G4-before-G3 execution order is intentional: an independent
reference failure stops before the physical preflight mesh is interpreted.

## Frozen thresholds

- Fraction absolute and relative tolerance: `1e-14`.
- Directional tangent relative error: `<=1e-7`.
- SNES: `newtonls/bt`, `atol=1e-11`, `rtol=1e-10`, `stol=1e-12`, `max_it=25`.
- Linear solve: `preonly/lu`.
- Finite absolute limit: `1e100`.
- Mechanics checks: finite values, nonnegative alpha, immutable pre-commit
  state, positive convergence reason, bounded free-DOF residual and reaction
  balance, exact residual/tangent version relation.

## Execution identities

Only these preflight ids are accepted:

```text
P4D1-ENV-01
P4D1-BRIDGE-01
P4D1-ORACLE-01
P4D1-TOPOLOGY-01
P4D1-SMOKE-01
P4D1-GUARD-01
```

All `P4D-*` formal ids are rejected before output-directory creation.

## Evidence handling

Raw outputs are written under `runtime_evidence`, hashed, and never overwritten.
Summaries are generated only after raw hashes are frozen.  Normalization may
remove run id, absolute path and wall-clock timestamp, but may not remove a
solver value, callback event, iteration, version, hash or classification.

The sole passing terminal state is
`PASS_P4D1_PREFLIGHT_READY_FOR_FULL_IMPLEMENTATION`.  It authorizes only a
later, separately reviewed full P4d implementation.
