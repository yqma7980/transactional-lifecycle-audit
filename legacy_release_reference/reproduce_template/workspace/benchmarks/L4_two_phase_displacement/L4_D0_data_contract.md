# L4-D0 data contract

Each future formal `case_id/run_id` directory must contain exactly:

- `case_result.json`
- `metric_comparison.csv`
- `accepted_profile.csv`
- `phase_event_log.csv`
- `case_manifest.json`

`case_result.json` records design/host identity, expected and observed
classification, pass flag, process/thread identity, finite flags, oracle and
gate summaries, lifecycle equality flags and evidence boundaries.

`metric_comparison.csv` records checkpoint, mesh, time step/CFL, saturation,
front, pressure, displacement, phase-mass and convergence metrics.

`accepted_profile.csv` records only accepted profiles. Required identity fields
are `case_id`, `run_id`, `accepted_version`, `time`, `cell_index`, `x`,
`S_n`, `S_w`, `p`, `lambda_n`, `lambda_w`, `f_n`, committed fingerprint and
accepted-output provenance fingerprint. A rejected candidate may appear only
in the event ledger and must never appear here.

`phase_event_log.csv` records attempt, trial, reject and accept events, declared
and observed state versions, committed/candidate/persistent fingerprints,
candidate reachability, time step, saturation/pressure extrema, phase masses,
boundary fluxes, phase defects, front, displacement and finite flags.

`case_manifest.json` records SHA-256 and byte size for the other four outputs,
the frozen design/case-matrix hashes and the execution environment. It does not
embed its own hash.

The only canonical serializer is the existing L2
`canonical_json/canonical_hash`, with `float.hex` representation. The entropy
oracle is independent of the finite-volume update. No result file or results
directory is created during the freeze stage.

