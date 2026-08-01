# PERF-D0 controlled cost and performance specification

Design: PERF-D1.0  
Status: FROZEN_NOT_IMPLEMENTED  
Date: 2026-07-22

## Question

What incremental cost is associated with optional transaction-audit layers when the equations, numerical path, tolerances and accepted numerical outputs are held fixed?

## Problem families

- `L3`: the frozen one-dimensional poroelastic consolidation finite-volume problem. The immutable L3 solver remains authoritative.
- `L4`: the frozen one-dimensional zero-capillarity two-phase displacement finite-volume problem with one-way displacement observable. The immutable L4 solver remains authoritative.
- `L6`: the frozen scalar nonlinear equation executed by SciPy 1.17.1 `least_squares(method="trf")` with the L6 host options.

This performance study does not alter or revalidate the scientific accuracy gates of L3, L4 or L6.

## Five cumulative configurations

1. `C0_VALID_BASELINE`: authoritative valid numerical path with no optional outer audit layer. L3/L4 retain unavoidable hashes already embedded in their frozen solvers; therefore C0 is not a raw mutable-state implementation.
2. `C1_TRANSACTION`: C0 plus explicit outer begin-attempt/candidate/commit ownership accounting without state hashing or retained event rows.
3. `C2_FINGERPRINT`: C1 plus canonical declared/accepted-state serialization and SHA-256 fingerprints.
4. `C3_EVENT_LOG`: C1 plus retained in-memory event rows and deterministic event serialization, without state fingerprints.
5. `C4_FULL_PROVENANCE`: C1 plus fingerprints, event rows, accepted-output provenance envelope, deterministic serialization and payload hash.

All modes return the same accepted numerical fields. Audit payload construction is timed; final result-file writing is outside the timed interval and is identical across modes.

## Frozen sizes

| Family | Small | Medium | Large |
|---|---|---|---|
| L3 | 256 cells, 160 steps to 0.2 | 512 cells, 240 steps to 0.2 | 1024 cells, 320 steps to 0.2 |
| L4 | 160 cells, CFL 0.4 to 0.2 | 320 cells, CFL 0.4 to 0.2 | 640 cells, CFL 0.4 to 0.2 |
| L6 | 50 independent TRF solves | 200 independent TRF solves | 800 independent TRF solves |

## Timing boundary

Timing begins after imports, environment checks, CPU affinity and immutable input construction. It ends after the accepted numerical output and the selected audit payload have been constructed and hashed where applicable. Result-directory creation and result-file writes are excluded.

## Environment

- Python 3.12.10.
- Windows 11.
- CPU affinity mask 1, CPU 0.
- `OMP_NUM_THREADS=1`, `MKL_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`, `NUMEXPR_NUM_THREADS=1`.
- `PYTHONHASHSEED=0` and `PYTHONDONTWRITEBYTECODE=1`.
- One worker process and one worker thread.
- No network, Abaqus or COMSOL.

## Metrics

Each formal process reports wall time, process CPU time, OS peak working set, Python allocation peak, accepted steps/solves, kernel-step evaluations, residual evaluations, tangent evaluations, accepted callbacks, nonlinear iteration proxy, audit-event count, serialized audit bytes, serialization time and SHA-256 time.

## Statistical protocol

For each of 45 family-size-configuration cells: two unmeasured independent warm-up processes followed by ten independent measured processes. No run is discarded. Report median, Q1, Q3, IQR and a deterministic 95% percentile bootstrap confidence interval for the median using 10,000 resamples and seed 20260722. Configuration order rotates by formal repetition to reduce fixed order bias.

## Claim boundary

The study estimates Python-level overhead on this machine for these frozen workloads. It does not establish production UEL speed, parallel scaling, Abaqus cost, cross-machine performance, asymptotic complexity or a universal benefit. Negative overhead results must be retained.