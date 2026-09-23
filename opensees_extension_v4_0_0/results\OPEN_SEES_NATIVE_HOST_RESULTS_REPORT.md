# OpenSees native-host registered study results

## Status

`EXECUTION_CLASSIFICATION: PASS`

`NATIVE_HOST: OpenSees 3.8.0`

`LIFECYCLE_TIER: TIER_A_NATIVE_MATERIAL_API`

The study was executed once from the preregistered source and executable under
preregistration SHA-256
`DF47113565DB18DB58DAD662B17B5A8F65BB4E3ADD21A96D719C58092161C21D`.
No threshold, case, candidate, or analysis rule was changed after observation.

## Registered outcomes

- 8/8 case-level outcomes matched the preregistered branch.
- 24/24 fresh processes completed.
- 8/8 cases were semantically reproducible across three processes after
  removing only `run_id`.
- Both benign controls remained `PASS_INVARIANT`.
- Four controlled lifecycle-fault cases were adjudicated as
  `DETECT_LIFECYCLE_DRIFT`.
- The injected semantic candidate ranked first in 4/4 fault cases.
- The invalid-comparison and unsupported-observation controls remained distinct
  from invariant behavior.
- No miss or adverse result occurred in this registered population.

## Mechanistic observation

`OS-F03` is the most informative external-subject case: omission of the native
revert call activated a lifecycle signal while the later stress and tangent
replay remained numerically identical.  This constructed result illustrates,
for this API and history only, why lifecycle evidence can add information beyond
generic response replay.  It is not evidence of an upstream OpenSees defect.

## Statistical and reliability boundary

The eight cases are an independent external-subject validation and are not
pooled with the frozen 17-case comparison, 20-case adjudication, 12-case
localization, or 180-run timing studies.  The original McNemar value `p=0.125`
and localization value `p=0.03125` are unchanged.  The new counts are descriptive
for the registered cases and do not estimate population sensitivity, failure
probability, MTTF, MTBF, field-defect prevalence, or industrial reliability.

## Release boundary

The parent v3.0.0 data and software releases remain immutable.  The new files
are eligible for a separate local v4.0.0 archive.  Remote publication is not
authorized by this task and therefore remains an author action.
