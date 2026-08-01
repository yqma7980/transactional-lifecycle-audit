# P5 backend output contract

Status: `IMPLEMENTED_NOT_EXECUTED`

Each future single-process run writes a new, non-overwriting directory containing `environment.json`, `event_ledger.csv`, `accepted_output.csv`, `metric_packets.npz`, `operator_contributions.npz`, `case_result.json` and `case_manifest.json`.

`metric_packets.npz` contains only numeric arrays for the eight frozen metrics. `operator_contributions.npz` contains numeric values and integer offsets for every residual and tangent contribution; object arrays and pickle-dependent loading are forbidden. All NPZ files must load with `allow_pickle=False`.

The environment semantic hash is the P4d canonical hash after removing only `run_id`. Duplicate comparison may remove only `run_id`, wall-clock timestamps and absolute paths. Scientific fields, structural verdicts, event projections, metrics and hashes remain in the comparison.

Future matrix finalization writes `null_pairwise_metrics.csv`, `null_envelope.json`, `null_confirmation.json`, `strength_sweep.csv`, `selected_strengths.json`, `duplicate_comparison.json`, `matrix_summary.json` and `execution_manifest.json`. These files do not exist in the implementation package.
