# PERF-D0 non-formal scale pilot

Date: 2026-07-22  
Status: CAPABILITY_AND_SIZE_SELECTION_ONLY  
Evidence use: prohibited

All probes used one Python process, one thread, CPU 0, no result files and no benchmark evidence label. Their only purpose was to choose workloads that are long enough to reduce process-startup dominance without creating an unnecessarily expensive formal matrix.

| Family | Pilot size | Work | Wall time (s) |
|---|---:|---:|---:|
| L3 | 64 cells | 80 accepted steps | 0.0113319 |
| L3 | 256 cells | 160 accepted steps | 0.0876008 |
| L3 | 1024 cells | 320 accepted steps | 0.6120404 |
| L4 | 40 cells | CFL 0.4 to time 0.2 | 0.0045025 |
| L4 | 80 cells | CFL 0.4 to time 0.2 | 0.0166493 |
| L4 | 160 cells | CFL 0.4 to time 0.2 | 0.0580045 |
| L6 | 10 solves | SciPy TRF safe analytic | 0.0487772 |
| L6 | 50 solves | SciPy TRF safe analytic | 0.1952813 |
| L6 | 200 solves | SciPy TRF safe analytic | 0.8455524 |

These pilot timings are not formal repetitions, confidence intervals, overhead estimates or manuscript evidence. No threshold or positive-performance claim is derived from them.