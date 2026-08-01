# Figure 3 evidence contract: bounded same-fault comparison

Status: `SOURCE_DATA_COMPLETE_NOT_FINAL_FIGURE`

## Panel A - method applicability

- Source: `P7a_figure3_same_fault_source.csv`.
- Fields: `case_id`, `fault_id`, `method_id`, `applicable`, `denominator_status`.
- Allowed conclusion: four methods are reconstructable from all ten bound runs; checkpoint/restart and component-fingerprint methods are not applicable.
- Forbidden implication: all six methods were compared or the missing methods failed.

## Panel B - anomaly information

- Fields: `observed_anomaly_detected`, `information_yield`, `oracle_flag_match`.
- Allowed conclusion: M1/M4 remain quiet, M5/M6 detect the F05/F07 anomalies, and all applicable methods remain quiet for the null control.
- Forbidden implication: M6 has a higher detection rate than M5 or the result generalizes beyond F05/F07.

## Panel C - localization increment

- Fields: `observed_localization_plane`, `localization_rank`, `expected_localized_cause`.
- Allowed conclusion: M5 identifies replay-relation drift, whereas M6 localizes F05 to rejected-candidate reachability and F07 to persistent-state restoration.
- Forbidden implication: complete root-cause proof for untested faults or production software.

## Panel D - evidence boundary

- Fields: `evidence_status`, `repetition_exact`, `case_role`.
- Allowed conclusion: five case pairs reproduce exactly as read-only secondary projections.
- Forbidden implication: held-out validation, full P6, population detection rates, Abaqus validity or parallel safety.

No SVG, PDF, TIFF or final manuscript figure is generated in P7a.
