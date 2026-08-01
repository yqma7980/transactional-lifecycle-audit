# PERF-D1 postprocessing contract

Status: **FROZEN_BEFORE_FORMAL_EXECUTION**

## Raw evidence gate

The postprocessor must find exactly 45 cells, ten formal process directories per cell, and exactly three files per run: `accepted_output.json`, `performance_result.json`, and `case_manifest.json`. It must verify every manifest hash, the 90 warm-up receipts, the 450 formal receipts, finite metrics, CPU affinity mask 1, the frozen thread environment, and exact accepted-output equality across C0-C4 and all repetitions within each family-size group. No run may be excluded.

## Frozen statistics

For every numeric metric and each of 45 cells, report median, Q1, Q3, IQR, and a deterministic 95% percentile bootstrap confidence interval for the median. Quartiles use linear interpolation. Bootstrap uses NumPy `default_rng(20260722)`, 10,000 resamples, lexicographically sorted case IDs, and a fixed metric-field order. Configuration overhead is the ratio of a cell median to the matching C0 family-size median; negative overhead is retained.

Metrics include wall and process CPU time, OS and Python peak memory, accepted-output bytes, numerical evaluation counts, event/fingerprint counts, serialized payload bytes, serialization time, and hashing time.

## Claim boundary

A valid result is classified `PASS_OUTPUT_EQUIVALENT_TIMING_RECORDED`. It estimates Python-level, single-thread, machine-specific cost for the frozen L3/L4/L6 workloads. It does not establish acceleration, production UEL cost, Abaqus scaling, cross-machine portability, asymptotic complexity, or universal overhead.
