# PERF-D1 static implementation and unit QA

Status: **IMPLEMENTED_UNIT_TESTED_NOT_PREFLIGHTED**

## Scope

This is implementation and unit-test evidence only. It is not a preflight result, a formal timing result, or a performance claim.

## Static checks

- Eight Python implementation/test/runner files parse successfully with `ast.parse`.
- The frozen 45-cell matrix and all protected L3/L4/L6 scientific inputs match the source manifest.
- The parent runner requires both `--execute-authorized` and `PERF_D1_EXECUTION_AUTHORIZED=YES`.
- The worker requires both `--worker-authorized` and `PERF_D1_WORKER_AUTHORIZED=YES`.
- No preflight or formal results directory existed at this gate.
- `__pycache__` count was zero.

## Unit tests

The authoritative rerun completed 9 tests with zero failures and zero errors. Covered contracts include the 45-cell product, cumulative audit modes, exact output equivalence for tiny L3/L4/L6 workloads, observation-only audit behavior, Windows CPU-affinity and peak-memory capability, and rejection before result creation when dual authorization is absent.

## Erratum trace

The first invocation passed eight tests and raised one test-only path error. Three locators were corrected from `ROOT.parents[1]` to `ROOT.parent`; the dated erratum records why this does not alter any equation, workload, threshold, output, freeze, or protected source. No formal or preflight case had run.

## Claim boundary

No timing overhead, performance benefit, production readiness, Abaqus result, COMSOL result, or physical-model conclusion is established here. The next authorized gate is the 45-cell non-formal preflight with exact output fingerprints across C0-C4.
