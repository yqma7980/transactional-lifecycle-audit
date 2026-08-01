# PERF-D0 acceptance gates

1. The case matrix contains exactly 45 unique cells: three families, three sizes and five configurations.
2. Every cell has two unmeasured warm-up processes and ten measured independent single-process, single-thread runs.
3. All worker processes confirm CPU affinity mask 1 and all frozen thread variables equal 1.
4. All accepted numerical values are finite and below 1E100.
5. Within each family-size cell, the canonical accepted numerical output fingerprint is exactly equal across all five configurations and all ten repetitions.
6. L3 outputs include final time, pressure field, cumulative outflow, accepted version and settlement.
7. L4 outputs include final time, saturation field, pressure field, phase masses, front, displacement and accepted version.
8. L6 outputs include every batch solve final x, residual, cost, nfev, njev and host status.
9. Any output mismatch invalidates the performance comparison and stops the entire downstream goal before clean rerun or manuscript v2.1.
10. No timed run may be deleted or excluded. Failure, interruption and slow observations remain in the raw table.
11. Two warm-ups are never included in formal statistics.
12. Each measured cell must contain exactly ten valid process records before statistics are computed.
13. Median, Q1, Q3, IQR and deterministic 95% bootstrap median confidence interval are mandatory.
14. Runtime, CPU, peak memory, evaluation counts, event rows, payload bytes, serialization and hashing are reporting metrics, not positive-performance pass thresholds.
15. C0 is explicitly described as the valid frozen baseline without optional outer audit, not as an implementation without all transaction or hashing cost.
16. Result-file I/O is outside the timed region; in-memory payload construction and serialization are inside it.
17. No Abaqus, COMSOL, production UEL, network service, Git operation or multi-threaded workload is permitted.
18. A PASS means `PASS_OUTPUT_EQUIVALENT_TIMING_RECORDED`, not `performance improved`.