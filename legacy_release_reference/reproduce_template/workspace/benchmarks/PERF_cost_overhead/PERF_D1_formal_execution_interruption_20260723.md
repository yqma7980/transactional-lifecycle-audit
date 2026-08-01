# PERF-D1 formal execution interruption (2026-07-23)

## Event

The orchestration tool reached its 30-minute outer wait limit during the frozen formal run. The original runner continued long enough to complete exactly nine formal repetitions and then exited before starting `run_10` or writing `formal_execution_receipts.json`.

## Frozen??

- 405 complete formal run directories.
- 1,215 run files; every directory contains the exact three-file output contract.
- Runs `run_01` through `run_09` exist for all 45 cells.
- No `run_10` directory exists.
- The 90 warm-up receipt file is complete and valid.
- All existing manifests match, all run results pass, and all nine family-size groups retain exact output fingerprints.
- No Python worker remained active when the?? was frozen.

## Interpretation

This is an infrastructure interruption, not a scientific hard-gate failure. No existing run may be overwritten, deleted, repeated, or excluded. A resume is valid only if it executes exactly the 45 missing `run_10` processes in the original rotation and then reconstructs the complete 450-entry receipt ledger from immutable per-run evidence.
