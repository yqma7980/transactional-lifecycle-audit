# P7a P6R evidence sync and RQ2 adjudication

## Final status

`PASS_P7A_BOUNDED_EVIDENCE_SYNC_READY_FOR_P8`

## Evidence synchronized

P7a reads P2 definitions, the partial P4d native-host evidence, the mixed P5 family result and the P6R bounded formal projections without modifying any upstream artifact. The evidence registry contains 23 immutable inputs. P6R contributes 60 run-method rows and 30 repetition-collapsed case-method rows.

## RQ2 result

RQ2 is `PARTIALLY_SUPPORTED_WITHIN_F05_F07_BOUNDED_RETROSPECTIVE_SCOPE`. Across the null control and the selected/adjacent F05 and F07 cases, M1 final-state regression and M4 matched operator-version checks remain quiet. M5 equal-input replay detects operator drift for F05/F07. M6 detects the same anomalies and adds distinct owner/event/source localization: rejected-candidate reachability for F05 and persistent-state restoration for F07. All four applicable methods remain quiet for the null control, and every repetition pair agrees exactly.

The result does not show incremental detection over M5. It shows incremental localization. M2 checkpoint/restart and M3 component fingerprinting are not applicable, so P7a is not a complete six-method comparison.

## Manuscript boundary

The new Claim Matrix permits a bounded retrospective RQ2 statement in P8. It does not authorize full P5/P6, held-out validation, detection-rate, Abaqus, production, parallel or multiphysics claims. No FE solve, benchmark, unit test or Abaqus process was run by P7a, and public archives were not changed.
