# P5D pre-execution environment-binding erratum

## Scope

The frozen P5D scientific design, workloads, instrumentation modes, equivalence
gates, repetitions and statistical rules remain unchanged. This erratum binds
each heterogeneous subject to the authoritative environment available before
formal timing.

The first qualification attempt completed the twelve S01/S02 cells and stopped
before executing S03 because the DOLFINx image contains SciPy 1.16.2 whereas the
frozen L6 adapter requires SciPy 1.17.1. No formal timing had started and no S03
timing value was observed. The failed attempt is preserved under
`results/qualification`.

## Corrected binding

- JSS-S01 and JSS-S02: frozen DOLFINx/PETSc Linux container
  `sha256:1bb0d528457c78db65ba5445421abe37d0cdfa542cc182bf36d3b4aca02f1fab`.
- JSS-S03: host CPython 3.12.10, NumPy 2.4.3 and SciPy 1.17.1, which is the
  version required by the immutable L6 adapter.
- Every process remains single-threaded and restricted to logical CPU 0.
- Environment identity must match across M0, M3 and M6 within each workload.

The replacement qualification batch is stored as `qualification_v2`. The old
qualification evidence is not overwritten or used in the formal performance
summary.

## Claim boundary

This correction is an implementation-environment binding, not a change to the
scientific protocol. It does not permit cross-subject absolute runtime
comparisons; P5D overhead is computed only within a subject/workload relative
to its M0 control.
