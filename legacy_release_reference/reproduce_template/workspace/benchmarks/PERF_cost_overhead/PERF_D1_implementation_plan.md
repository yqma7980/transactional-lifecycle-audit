# PERF-D1 implementation and execution plan

Status: FROZEN_NOT_IMPLEMENTED

1. Implement a shared worker with five cumulative audit modes and family adapters for L3, L4 and L6.
2. Import immutable L3/L4/L6 dependencies by hash-protected paths; do not modify or copy their scientific solvers.
3. For L3/L4, measure optional outer lifecycle-audit overhead on top of the authoritative solver. Document that their frozen kernels already contain unavoidable internal fingerprint operations.
4. For L6, use identical SciPy equations and options in all modes; C0 may use a minimal direct host adapter while C1-C4 add cumulative audit layers.
5. Implement Windows CPU-affinity and PeakWorkingSetSize queries with `ctypes`; use `tracemalloc` for Python allocation peak.
6. Preflight all 45 cells once without timing claims. Require exact cross-mode output fingerprints before any formal timing.
7. Run 90 independent warm-up processes, then 450 independent formal processes in the frozen rotation order.
8. Generate immutable raw results, per-run manifests, output-equivalence comparison, statistics, final summary and source data.
9. Stop on the first scientific hard gate failure. Do not alter size, mode, threshold, output schema or repetition count after execution starts.