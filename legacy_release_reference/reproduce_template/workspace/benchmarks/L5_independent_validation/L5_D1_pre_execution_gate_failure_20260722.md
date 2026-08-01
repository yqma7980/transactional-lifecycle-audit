# L5-D1 independent-validation pre-execution gate failure

Date: 2026-07-22  
Evidence status: `PRECHECK_FAIL_NOT_FORMAL_EVIDENCE`  
Implementation status: `IMPLEMENTED_PRECHECK_FAILED_SCIENTIFIC_GATE`

## Decision

Formal L5 execution was not started. The directed preflight ran 11 tests: 10 passed and one frozen prerequisite failed. `L5-IV-CV-01` produced a minimum observed order of `0.6294266281954826`, below the predeclared threshold `0.7`.

No threshold, grid, reference, equation, numerical method or order definition was changed after observing the result. In particular, the result was not converted into a pass by using a whole-range fitted slope, by replacing `N=80/160/320`, or by relaxing the gate.

## Frozen convergence evidence

| Metric | 80->160 order | 160->320 order |
|---|---:|---:|
| Saturation L1 | 0.9420513562253338 | 0.6630502608420619 |
| Pressure relative L2 | 0.8395195461847365 | 0.8476231677990818 |
| Front location | 0.9312293445027730 | 0.6294266281954826 |
| One-way displacement | 0.8495931643882688 | 0.8518394336892714 |

The minimum is the finest-pair front-location order. The finest-pair saturation order also lies below `0.7`, so changing only the front locator would not satisfy the frozen gate.

## Diagnostic boundary

An in-memory diagnostic at `N=640` and `N=1280` showed continued error reduction and shock-alignment oscillation in adjacent-grid order. Those levels were not frozen cases, were not written as formal results and were not used to redefine the acceptance gate. They only support the conclusion that the failure is not a NaN/Inf or obvious implementation crash.

## Passed preflight components

- independent binary serializer and deterministic fingerprint;
- independent entropy/Gauss-8 oracle identity and mass check;
- finite, bounded and conservative independent solver health check;
- accepted-output provenance;
- exact safe retry/rollback parity;
- finite unsafe negative-control drift;
- no L4 implementation import;
- protected L4 raw aggregate hash;
- unauthorized-case rejection.

These passes do not override the failed convergence prerequisite.

## Evidence boundary

This record is not `OBSERVED-L5`. It does not establish cross-implementation agreement, independent validation, Abaqus validity, production readiness, performance, two-way coupling or CO2 application validity. Claim Matrix v1.1 and manuscript v1.1 remain unchanged.

## Stop action

No L5 formal case, duplicate run, final summary, Figure 11 source data, Claim Matrix v1.2 or manuscript v1.2 was created. The next scientific decision requires user review because any attempt to force a pass would require changing a frozen protocol interpretation or benchmark design.
