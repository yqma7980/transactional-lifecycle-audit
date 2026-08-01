# PERF-D1 postprocessor import erratum (2026-07-23)

The first authorized postprocessor invocation stopped before `build_evidence` and before creation of the `final` directory because direct script execution did not place the NCS workspace root on `sys.path`. The 450-run raw aggregate remained unchanged.

The runner now inserts its authoritative workspace root before importing the already frozen `perf_postprocess` module. No statistic, seed, metric, threshold, raw result, accepted output, or postprocessing implementation changed. A targeted unauthorized invocation must import successfully, refuse execution, and leave `final` absent before the authorized retry.