# PERF-D1 pre-execution test-locator erratum (2026-07-22)

## Status

PRE-EXECUTION TEST-ONLY CORRECTION. No formal performance case, warm-up, or timing repetition had been executed when this correction was made.

## Observed issue

The first unit-test invocation passed eight tests and raised one `FileNotFoundError` in `test_frozen_scientific_inputs_unchanged`. The test resolved protected benchmark inputs from `ROOT.parents[1]`, which omitted the authoritative `benchmarks` directory.

## Correction

Exactly three protected-input locators in `tests/test_perf_d1.py` were changed from `ROOT.parents[1] / ...` to `ROOT.parent / ...`. `ROOT` is the `benchmarks/PERF_cost_overhead` directory, so `ROOT.parent` is the authoritative `benchmarks` directory.

## Scientific boundary

This correction changes only a test-file path locator. It does not change the benchmark specification, case matrix, execution freeze, equations, workloads, accepted outputs, tolerances, statistics, performance configuration, oracle, or any protected L3/L4/L6 source file. No result is inferred from the interrupted test invocation.

## Required follow-up

The full PERF-D1 unit-test module must be rerun under the frozen single-thread, no-bytecode environment. Formal preflight remains unauthorized until all tests and static QA pass.