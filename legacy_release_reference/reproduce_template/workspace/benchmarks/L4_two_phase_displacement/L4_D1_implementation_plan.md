# L4-D1 implementation plan

Status: `FROZEN_NOT_IMPLEMENTED`.

The planned implementation is a standalone standard-library Python host. It
will contain immutable committed/trial/output packets, an entropy/resistance
oracle independent of the numerical update, a conservative first-order
finite-volume solver, accepted-state pressure and one-way mechanics
reconstruction, safe and seeded-unsafe retry variants, a frozen case dispatcher,
directed tests and a double-locked runner.

The implementation may reuse only the existing canonical serializer. It must
not import, simplify or adapt the production UEL. It must not add capillary
pressure, gravity, compressibility, clipping, mass repair or mechanics-to-flow
feedback after this freeze.

The preflight sequence is:

1. Parse and hash all frozen files.
2. Independently reproduce `S_star`, shock speed and breakthrough time.
3. Verify the entropy root and split quadrature without importing the solver.
4. Verify telescoping phase-balance identities.
5. Verify the safe retry is exactly invariant in memory.
6. Verify the frozen unsafe seed produces finite nonzero drift above every
   predeclared floor.
7. Run directed unit tests without creating formal results.
8. Freeze the implementation manifest before formal execution.

Formal execution requires both `--execute-authorized` and
`L4_D1_EXECUTION_AUTHORIZED=YES`. One process executes one case and one run ID.
Each case will run twice independently and single-threaded. A failed
prerequisite stops downstream execution; no threshold, schedule, physics or
oracle may be changed in response to formal output.

Passing this benchmark would establish only bounded `OBSERVED-L4` evidence for
the frozen standalone problem. It would not establish two-way poromechanics,
Abaqus behavior, fault-zone physics, performance or production readiness.

