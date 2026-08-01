# Future P5 output contract

No file in this list is created by the preflight.

Each future run must write a non-overwriting directory containing environment identity, case result, event ledger, numeric metric packets and a per-run manifest. Calibration finalization must add `null_pairwise_metrics.csv`, `null_envelope.json`, `strength_sweep.csv`, `selected_strengths.json`, `duplicate_comparison.json` and an execution manifest.

Run-specific fields (`run_id`, wall-clock timestamp and absolute path) may be removed only for duplicate comparison. Scientific fields, structural verdicts and metric values may not be excluded. Structural identities remain exact; numeric metrics use only the frozen P5 acceptance relation.
