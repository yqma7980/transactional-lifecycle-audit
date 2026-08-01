# CR-D3 dependency-complete exact clean rerun contract

Status: **FROZEN_NOT_IMPLEMENTED**

CR-D3 retains CR-D2's exact historical L1-MP source profile and all prior scientific gates. It corrects only the clean execution dependency graph: the L5 cross-implementation case verifies the complete L4 raw aggregate, so all ten L4 cases are now rerun twice before L5-XP. The added ten jobs are independent `run_2` processes with historical complete-file SHA-256 targets.

All twenty L4 run directories are written under `workspace/benchmarks/L4_two_phase_displacement/results/L4_D1_two_phase_displacement` inside the isolated clean snapshot. Before L5-XP, that directory must contain exactly 100 raw files and reproduce aggregate `ff25b0622dd8ce74a6a5d8d3f712df593e732a20918c4259c7fc0afb4539e78d`. The `final` derived directory is not copied or required.

The remaining 49-job envelope, case parameters, thresholds, oracles, accepted-output contracts, first-mismatch stop gate and six-cell performance protocol are unchanged. This is dependency completion, not a relaxation or a post hoc numerical criterion.
