# L5-D2 implementation plan

Status: `FROZEN_NOT_IMPLEMENTED`

1. Preserve every L5-D0/D1 file and failure record as read-only.
2. Add D2-named case, test and runner modules. Reuse the hash-protected independent L5 state, solver, oracle and lifecycle implementation without modification.
3. Implement the five-level OLS convergence statistic directly from freshly computed errors. Record all adjacent orders and fit diagnostics without adding post hoc pass thresholds.
4. Prove by AST and import audit that neither D2 nor its immutable dependencies import L4 implementation code. L4 formal data may be read only by the cross-implementation case after aggregate-hash verification.
5. Complete syntax, oracle, serializer, finite, bounds, mass, provenance, safe/unsafe, unauthorized-case and frozen-protocol preflight tests. Unit tests are not formal evidence.
6. Use a D2 double-locked runner. Each invocation executes one case and one run ID in one single-thread process and writes only to `results/L5_D2_independent_validation`.
7. After preflight passes, execute the eight cases in frozen matrix order with two independent processes each. Stop after the first failed prerequisite.
8. Freeze raw outputs, verify per-run manifests, compare normalized duplicate runs and build a bounded final evidence package.
9. If immutable D1 dependency reuse is insufficient, if L4 code import becomes necessary, or if any scientific threshold/reference/level must change, record failure and stop.

No Abaqus, COMSOL, production UEL, Git operation, result overwrite or network service is permitted during implementation or execution.
