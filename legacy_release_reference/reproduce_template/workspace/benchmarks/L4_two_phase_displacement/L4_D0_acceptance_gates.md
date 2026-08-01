# L4-D0 acceptance gates

Status: frozen before implementation or formal output. All values must be
finite and below `1E100` in absolute value. No threshold may be relaxed after
formal output is observed.

| Case | Frozen pass gate |
|---|---|
| `L4-REF-01` | At `t=0.1,0.2,0.4`, cell-average saturation L1 error <= `4E-3`, front-location absolute error <= `3E-3`, pressure relative L2 error <= `7.5E-3`, pressure Linf error <= `1E-2`, one-way displacement absolute error <= `8E-4`, root residual <= `1E-13`, and quadrature estimate <= `1E-12`. |
| `L4-CV-S-01` | For `N=80,160,320`, all saturation-L1, front, pressure-L2 and displacement errors decrease twice; finest-pair orders are >= `0.5` for every metric. This is a fixed-CFL mesh-refinement gate for a discontinuous entropy solution, not a smooth-solution second-order claim. |
| `L4-CV-T-01` | For `N=800`, `CFL=0.4,0.2,0.1` against the frozen same-mesh `CFL=0.0125` time reference, saturation-L1, pressure-L2 and displacement errors decrease twice and finest-pair orders are >= `0.8`. |
| `L4-MB-W-01` | At every accepted step through `t=0.6`, the maximum normalized wetting-phase step defect and final normalized cumulative defect are <= `5E-12`. |
| `L4-MB-N-01` | At every accepted step through `t=0.6`, the maximum normalized nonwetting-phase step defect and final normalized cumulative defect are <= `5E-12`. |
| `L4-FR-01` | At `t=0.1,0.2,0.4,0.6`, threshold-interpolated front error is <= `3E-3`; the accepted front is strictly increasing and remains before the outlet. The threshold is frozen at `S_star/2`. |
| `L4-MECH-01` | At `t=0.1,0.2,0.4`, pressure relative L2 error <= `7.5E-3`, pressure Linf error <= `1E-2`, one-way displacement absolute error <= `8E-4`, and accepted response is generated only from accepted pressure. |
| `L4-ST-01` | Through `t=0.6`, saturation remains in `[0,1]` within `1E-13`, saturation and pressure are nonincreasing with `x`, pressure is nonnegative, nonwetting mass/front are nondecreasing, wetting mass is nonincreasing, and no clipping or mass repair occurs. |
| `L4-RT-01` | Direct and safe-retry accepted saturation, pressure, displacement, phase masses and committed/physical fingerprints are exact; rejection leaves committed state unchanged, rejected candidates unreachable, and accepted output sourced only from the accepted state. |
| `L4-RT-02` | Declared replay context and committed fingerprint before replay are equal; rejected candidate is unreachable; observed fingerprint differs; saturation L2 drift >= `1E-4`, pressure L2 drift >= `1E-6`, displacement drift >= `1E-6`, absolute declared phase-mass defect >= `1E-4`, and all values remain finite. |

Each case runs twice in independent single-process, single-thread executions.
After normalizing only `run_id`, `case_result`, metric/profile records and event
records must be exact. A failed prerequisite stops downstream cases.

Hard stops include an oracle/parameter mismatch, post hoc threshold change,
non-finite value, saturation clipping, safe committed-state mutation before
acceptance, zero unsafe discriminating drift, changed physics between comparator
paths, accepted output sourced from a rejected candidate, or invocation of
Abaqus, COMSOL or production code.

