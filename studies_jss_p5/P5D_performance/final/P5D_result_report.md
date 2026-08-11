# P5D formal performance evidence report

**Status:** `PASS_P5D_FORMAL_PERFORMANCE_STUDY`  
**Evidence:** `OBSERVED-JSS-P5D`

The frozen study executed 18 cells spanning three subjects, two workloads per subject, and three instrumentation modes. It retained 36 unreported warm-ups and 180 formal fresh-process measurements. Output fingerprints, accepted trajectories, production evaluation counts, and within-workload environment identities agree across M0, M3, and M6 before timing is interpreted.

Across the six workload groups, generic replay has a cross-cell median external-wall overhead of -0.821% (range -2.926% to 6.920%). Full TLA has a cross-cell median of -0.061% (range -0.904% to 5.119%). Negative estimates are retained and treated as timing variability, not acceleration.

The result is bounded to one machine and single-process, single-thread execution. It does not establish parallel overhead, industrial-scale cost, or a population performance distribution. Historical AES timing records were not used.
