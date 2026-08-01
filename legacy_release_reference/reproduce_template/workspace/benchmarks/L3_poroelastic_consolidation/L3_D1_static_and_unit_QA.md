# L3-D1 static, unit and preflight QA

Status: `IMPLEMENTED_UNIT_TESTED_PREFLIGHT_PASS_NOT_FORMALLY_EXECUTED`.

This is implementation QA, not formal `OBSERVED-L3` evidence. No Abaqus or production model was used.

## Static contract

- The frozen design remains `L3-D1.0a`; equations, schedules and tolerances were not changed.
- The authoritative L2 `canonical_json/canonical_hash` implementation is loaded read-only by verified source SHA-256 without importing the legacy package facade. No second serializer was created.
- Trial and accepted event fingerprints are captured at the event time. Rejected candidates become unreachable while unsafe persistent state remains outside rollback by design.
- The runner requires the CLI flag, authorization environment variable and one-thread declaration before any result directory can be created. The unauthorized probe exited 1 and created no output.

## Directed tests

`11/11` directed tests passed in one process and one thread with bytecode generation disabled. The tests cover the freeze identity, model reduction, Fourier oracle, reference, spatial and temporal convergence, mass balance, monotonic stability, safe retry, unsafe negative control and unauthorized case rejection.

## Non-formal preflight

All seven frozen cases passed in memory. The finest-pair spatial orders were `2.00040087888327` for pressure and `2.000392029638694` for settlement. The temporal orders were `1.0120157853757363` and `1.0017378588196653`. The maximum normalized step mass defect was `1.6891235530033578E-13`; the cumulative value was `9.880984919163893E-15`. Safe retry produced exact zero pressure and settlement drift. The unsafe control produced pressure L2 drift `5.9890262453956816E-2`, settlement drift `1.0441150039577962E-2` and declared mass defect `3.514145077299766E-2`, all finite.

These values only establish preflight margin. They must not be cited as formal manuscript evidence until two independent formal processes per case pass and their outputs are synchronized.

## Open boundary

Formal execution, duplicate-run equality, L3 evidence sync, Abaqus, two-phase flow, fault-zone application, thread safety, performance and production readiness remain open.
