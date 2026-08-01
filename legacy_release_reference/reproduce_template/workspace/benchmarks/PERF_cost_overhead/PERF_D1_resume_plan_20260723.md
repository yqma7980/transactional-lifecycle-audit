# PERF-D1 formal resume plan

Status: **FROZEN_NOT_EXECUTED**

1. Reverify the 405-run aggregate and 90 warm-up receipt hash.
2. Require all `run_01`-`run_09` directories and reject any existing `run_10` or formal receipt file.
3. Execute only `run_10`, preserving the original family-size group order and rotation offset four.
4. After each five-configuration group, require exact accepted-output fingerprints.
5. Never repeat warm-ups, overwrite a run, delete a slow run, or alter the case matrix.
6. After all 450 runs exist, reconstruct `formal_execution_receipts.json` in the exact original loop order and verify every run manifest.
7. Continue to the frozen postprocessor only after the resumed formal ledger passes.
