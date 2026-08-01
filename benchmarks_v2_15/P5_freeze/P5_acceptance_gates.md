# P5 acceptance gates and stop rules

Status: `FROZEN_STATIC_NOT_IMPLEMENTED`

## G0 - protected evidence

All P2, P3, P4d.0 and P4d.6 input hashes listed in `P5_source_manifest.json` must match before implementation and before any later execution. P4d native line-search non-support and all preserved failures remain unchanged.

Failure: `BLOCKED_PROTECTED_EVIDENCE_DRIFT`.

## G1 - immutable host and field scales

The exact P4d image, mesh, material, load path, SNES/KSP/PC options, one-rank/one-thread environment, event ownership and scale registry must match this freeze. A missing field binding cannot be replaced after execution begins.

Failure: `BLOCKED_HOST_OR_SCALE_IDENTITY`.

## G2 - exact null control

Six fresh processes must reproduce exact semantic identities and exact-zero numerical drift for `P5-NULL-EXACT-CAL-01`. Run-specific diagnostic fields are excluded before comparison; no scientific field is excluded.

Failure: `BLOCKED_EXACT_NULL_CONTROL_NONZERO`.

## G3 - numerical null envelope

For each numeric metric, compute the complete pairwise envelope and `T_m=max(1024*eps,10*E_m)`. Require `E_m<=1e-11`, `T_m<=1e-10`, finite values, exact structural identities and repeatable environment hashes.

The two-process `ARITH_C_CONFIRMATION` case must remain within every frozen `T_m` and may not refit the envelope.

Failure: `NOT_SUPPORTED_NULL_ENVELOPE_UNSTABLE` or `NOT_SUPPORTED_NULL_ENVELOPE_TOO_WIDE`.

## G4 - scaled development selection

For each of `F01`, `F02`, `F05` and `F07`, execute all 15 binary strengths. Select only by the frozen adjacent-level rule. Two new fresh-process repetitions at both selected levels must reproduce the result. A lifecycle finding and secondary operator separation are reported separately.

Failure: `NOT_SUPPORTED_AT_FROZEN_SCALE`, `NOT_SUPPORTED_DISTINCTIVE_REGION_EMPTY`, or `BLOCKED_FRESH_PROCESS_NONREPEATABILITY`.

## G5 - held-out P6 binding

P6 receives the selected `eta_j`, metric thresholds and exact field/event definitions as immutable inputs. `P3-CONF-01` and `P3-CONF-03` may not be read during P5 selection. `P3-DEV-08` uses the frozen `ARITH_D_P6_BENIGN` path and must remain quiet.

Any need to change a P5 result after inspecting P6 is a protocol failure, not a retuning opportunity.

## Structural versus numerical verdicts

- Structural owner, restoration, source, reachability, version and event-order checks are exact.
- Numeric drift uses the metric-specific acceptance relation only.
- Operator drift is secondary and cannot by itself establish the complete lifecycle verdict.
- `NOT_SUPPORTED`, invalid setup and null controls do not enter a detected-fault numerator.

## Absolute stop rules

Stop and preserve all evidence if a protected hash changes, the exact control drifts, a scale is undefined, a null confirmation alarms, a required field/event is unavailable, a duplicate differs, a P6 result is consulted during selection, or a new strength/tolerance/site would be needed.

No Abaqus, COMSOL, production UEL, native-line-search substitute, manuscript update, DOI change or public-repository update is authorized by this freeze.
