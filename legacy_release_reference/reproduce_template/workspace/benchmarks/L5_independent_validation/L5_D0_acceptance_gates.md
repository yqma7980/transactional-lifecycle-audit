# L5-D0 acceptance gates

All thresholds are frozen before implementation.

| Gate | Threshold |
|---|---|
| Finite absolute limit | 1E100 |
| Saturation bounds | -1E-12 <= Sn <= 1+1E-12 |
| Reference saturation L1 | <= 8E-3 |
| Reference front absolute error | <= 4.5E-3 |
| Reference pressure relative L2 | <= 1E-2 |
| Reference pressure Linf | <= 1.5E-2 |
| One-way displacement absolute | <= 1.5E-3 |
| Minimum observed convergence order | >= 0.7 |
| Normalized step and cumulative phase-mass defect | <= 1E-11 |
| Cross-implementation saturation L1 | <= 8E-3 |
| Cross-implementation pressure relative L2 | <= 1.2E-2 |
| Cross-implementation front absolute | <= 5E-3 |
| Cross-implementation displacement absolute | <= 1.5E-3 |
| Safe retry | exact fields, committed state and accepted-output fingerprint |
| Accepted output with live trial | exact committed payload; trial unreachable |
| Unsafe saturation L2 drift floor | >= 1E-4 |
| Unsafe pressure L2 drift floor | >= 1E-7 |
| Unsafe displacement drift floor | >= 1E-8 |
| Unsafe declared phase-mass defect floor | >= 1E-5 |
| Duplicate repetitions | exact after replacing run_id and excluding run-labelled derived hashes |

Prerequisites are evaluated in case-matrix order. A failed prerequisite stops subsequent formal cases without threshold changes or result deletion. The unsafe case passes only when the predeclared invalid mechanism is detected; it is not a usable physical solution.
