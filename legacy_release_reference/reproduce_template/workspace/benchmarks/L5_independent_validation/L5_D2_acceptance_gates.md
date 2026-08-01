# L5-D2 acceptance gates

Status: `FROZEN_NOT_IMPLEMENTED`

All thresholds are frozen before D2 implementation and formal execution.

## Revised convergence gate

The levels are exactly `N=80,160,320,640,1280`, with `h=1/N` and target time `t=0.2`.

For each metric, compute the OLS slope `p` of `log(error)` against `log(h)` using all five points. The case passes only if:

- every error is finite and strictly positive;
- every metric is strictly monotone decreasing across all four refinements;
- every five-level regression order is `>=0.7`.

Metrics: saturation L1, pressure relative L2, front absolute error and one-way displacement absolute error.

All four adjacent-pair orders, OLS intercept, `R^2`, slope standard error and log-fit residuals are recorded. They have no additional numerical pass threshold. The front statistic is not a Richardson extrapolation and is not used to claim an uncertainty interval.

## Preserved gates

| Gate | Threshold |
|---|---|
| Finite absolute limit | `1E100` |
| Saturation bounds | `-1E-12 <= Sn <= 1+1E-12` |
| Reference saturation L1 | `<= 8E-3` |
| Reference front absolute error | `<= 4.5E-3` |
| Reference pressure relative L2 | `<= 1E-2` |
| Reference pressure Linf | `<= 1.5E-2` |
| One-way displacement absolute | `<= 1.5E-3` |
| Five-level observed convergence order | `>= 0.7` |
| Normalized step and cumulative phase-mass defect | `<= 1E-11` |
| Cross-implementation saturation L1 | `<= 8E-3` |
| Cross-implementation pressure relative L2 | `<= 1.2E-2` |
| Cross-implementation front absolute | `<= 5E-3` |
| Cross-implementation displacement absolute | `<= 1.5E-3` |
| Safe retry | exact fields, committed state and accepted-output fingerprint |
| Accepted output with live trial | exact committed payload; trial unreachable |
| Unsafe saturation L2 drift floor | `>= 1E-4` |
| Unsafe pressure L2 drift floor | `>= 1E-7` |
| Unsafe displacement drift floor | `>= 1E-8` |
| Unsafe declared phase-mass defect floor | `>= 1E-5` |
| Duplicate repetitions | exact after replacing `run_id` and excluding run-labelled derived hashes |

Prerequisites are evaluated in case-matrix order. A failed prerequisite stops all subsequent formal cases. Thresholds, levels, solver, reference and oracle cannot be changed after preflight or formal results are observed.
