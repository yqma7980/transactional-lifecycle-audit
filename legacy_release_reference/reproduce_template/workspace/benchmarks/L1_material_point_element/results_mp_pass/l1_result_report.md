# L1-MP final result

Status: **PASS L1-MP / L1-E1 NOT IMPLEMENTED OR EXECUTED**

## Decision

All 12 frozen L1-MP cases and all 25 scenario-variant outcomes passed their predeclared hard gates in two independent complete executions. The deterministic call ledger, case table, checkpoint table, design-validation record, candidate report and candidate summary were byte identical between runs.

This is Branch A of the frozen plan. The full L1 level is not complete because L1-E1 remains blocked and was not authorized in this task.

## Hard-gate evidence

- MP cases passed: `12/12`.
- MP scenario-variant outcomes passed: `25/25`.
- Safe replay false positives: `0`.
- Call-ledger rows: `202`.
- Accepted-checkpoint rows: `9`.
- All normal numeric outputs finite: `true`.
- Rejected evaluations left committed safe state unchanged: `true`.
- Duplicate accept advanced the accepted version only once: `true`.
- Safe terminal/output reads were non-interfering: `true`.
- Checkpoint round trips reproduced committed state and operator fingerprints: `true`.
- Elastic and plastic directional tangent checks passed the frozen tolerance: `true`.

## Seed observations

- `MP-LC-01 / unsafe_trial_cache`: delta stress `-1.69421487603305798e+00`; `DETECTED_FINITE_SEEDED_TRIAL_DRIFT`.
- `MP-LC-02 / unsafe_trial_cache`: delta stress `2.54320060105184087e+00`; `DETECTED_FINITE_SEEDED_TRIAL_DRIFT`.
- `MP-LC-06 / unsafe_output_feedback`: delta stress `-1.69421487603305798e+00`; `DETECTED_FINITE_OUTPUT_FEEDBACK_DRIFT`.

The primary rejected-plastic-trial seed reproduced the frozen analytical drift `Delta stress = -205/121` within `1e-12`. Safe-local and safe-transactional controls returned exact-zero replay drift for their applicable lifecycle comparisons.

`MP-LC-02` used a documented pre-execution seed erratum. The original monotonic call-order permutation reached the same hidden plastic state and could not exercise its finite-nonzero drift gate; before formal execution it was replaced by the same `+0.03/-0.03` discarded packets in opposite order. Equations, tolerances and expected classification were unchanged.

## Reproducibility

- Compared deterministic files: `6`.
- Mismatched deterministic files: `0`.
- Run 1 wall time: `0.050620200 s`.
- Run 2 wall time: `0.048497000 s`.
- Maximum Python peak allocation: `406057` bytes.
- Abaqus processes observed during finalization: `0`.

Performance values are descriptive only and are not an L1 pass criterion.

## Evidence classification

- `OBSERVED_L1`: the 25 MP outcomes, ledger, checkpoint, seed-detection and duplicate-run results.
- `ESTABLISHED_ANALYTICAL_REFERENCE`: the frozen Fraction oracle values and central-difference tolerances.
- `OPEN`: L1-E1, L2-L6, host integration, global solves, conservation, performance and application consequences.

## Claim boundary

The result shows that this standalone L1-MP harness detects its seeded path-dependent lifecycle defects without flagging its safe controls. It does not establish Abaqus/UEL safety, restart parity, global Newton robustness, mass conservation, two-phase poromechanics accuracy, cross-framework generality, CO2 plume validity, fault response or surface displacement.
