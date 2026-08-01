# L3-D0 acceptance gates

All values must be finite and below `1E100` in absolute value.

| Case | Frozen pass gate |
|---|---|
| L3-REF-01 | At `t=0.05,0.2,0.5`, relative pressure L2 error <= `5E-3`, pressure Linf error <= `1E-2`, settlement absolute error <= `2E-4`, oracle envelope <= `1E-15`. |
| L3-CV-S-01 | `N=20,40,80`, `dt=0.2*dx^2`, `t=0.2`; pressure and settlement errors decrease twice and finest-pair orders are >= `1.7`. |
| L3-CV-T-01 | `N=400`, `dt=0.04,0.02,0.01`, `t=0.2`; pressure and settlement errors decrease twice and finest-pair orders are >= `0.8`. |
| L3-MB-01 | `N=64`, `dt=0.005`, `t=0.5`; maximum normalized step and cumulative mass defects <= `5E-12`. |
| L3-ST-01 | `N=80`, `dt=0.0025`, `t=0.5`; pressure remains in `[0,p0]` within `1E-13`, is nondecreasing with depth, mean pressure never rises, and settlement/outflow never fall. |
| L3-RT-01 | Direct and safe-retry accepted fields and fingerprints are exact; rejection leaves committed state unchanged and candidates unreachable. |
| L3-RT-02 | Declared replay and committed fingerprints are equal, observed fingerprint differs, pressure L2 drift >= `1E-8`, settlement drift >= `1E-10`, declared mass defect >= `1E-8`, and all values are finite. |

Each case runs twice in independent single-process, single-thread executions.
After replacing only `run_id`, result, comparison and event records must be
exact. No threshold may be relaxed after formal output is seen.

Hard stops include oracle/parameter mismatch, non-finite values, safe committed
state mutation before acceptance, zero unsafe discriminating drift, changed
physics between comparator paths, or invocation of Abaqus/production code.
