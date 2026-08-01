# P4d.1 pre-execution implementation erratum

This record preserves two implementation-only corrections made before a gate
result was assigned.  No scientific model, callback schedule, mesh, load,
material parameter, solver tolerance, oracle value or acceptance threshold was
changed.

1. The first shared-library build attempted to resolve a `PETSc` pkg-config
   entry using the image's default `PKG_CONFIG_PATH`.  The entry is stored under
   `/usr/local/petsc/$PETSC_ARCH/lib/pkgconfig`; the failed build log is
   preserved as `runtime_evidence/bridge_build/build.log`.  Build attempt 2
   prepended that same-version official directory and compiled the unchanged C
   source.
2. The first topology execution constructed the frozen 32-cell topology and
   state but the generic stage runner could not serialize NumPy arrays.  Its
   traceback is preserved as `runtime_evidence/topology/stderr.log`.  A new
   topology-only runner converts arrays to JSON lists; it does not alter the
   topology, canonical hashes or state evaluation.  Attempt-2 logs are stored
   separately.

Neither failed attempt is formal P4d evidence.  The interpreted preflight uses
only the successful bridge build and the successful topology result while
retaining the failed artifacts for auditability.
