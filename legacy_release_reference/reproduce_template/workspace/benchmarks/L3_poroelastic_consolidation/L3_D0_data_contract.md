# L3-D0 data contract

Each formal `case_id/run_id` directory contains exactly:

- `case_result.json`
- `field_comparison.csv`
- `poro_event_log.csv`
- `case_manifest.json`

Results record model/configuration identity, analytical and discrete metrics,
lifecycle fingerprints, expected/observed classifications and finite flags.
The event ledger records attempt and acceptance state, time, step, mesh,
committed/candidate/persistent fingerprints, pressure range and mean,
settlement, outflow, boundary flux, storage change, mass defect and candidate
reachability.

The only canonical serializer is the existing L2
`canonical_json/canonical_hash`; floats use `float.hex`. No result file is
created during the freeze stage.
