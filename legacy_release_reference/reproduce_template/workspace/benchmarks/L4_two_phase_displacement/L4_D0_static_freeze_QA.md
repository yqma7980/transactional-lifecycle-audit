# L4-D0 static-freeze QA

Status: `STATIC_FREEZE_PASS`, design `L4-D1.0` remains
`FROZEN_NOT_IMPLEMENTED`. This document reports pre-implementation design
checks, not `OBSERVED-L4` evidence.

## Structural checks

- The freeze JSON parses and names ten unique formal cases.
- The CSV parses to the same ten case IDs and contains no duplicate ID.
- All design-output and protected-input hashes in the source manifest match
  the files present at freeze time.
- No `src`, `tests`, runner, results or execution directory exists for L4.
- The only planned canonical serializer is the existing L2 serializer.
- No Abaqus, COMSOL or production-model process was invoked.

## Analytical checks

Independent design calculations reproduced

```text
S_star = 0.7071067811865475
v_shock = 1.2071067811865475
t_breakthrough = 0.8284271247461901
```

The Rankine-Hugoniot and characteristic condition
`f'(S_star)=f(S_star)/S_star` closes to floating-point roundoff. All frozen
reference times are earlier than breakthrough. The maximum characteristic
speed is `2`; `CFL=0.4` therefore remains inside the monotone explicit update
limit without clipping.

## Non-formal gate-discrimination calculation

A disposable, in-memory standard-library calculation was used only before
implementation to confirm that the predeclared schedules discriminate the
intended quantities. It created no benchmark file and is not formal evidence.

At `N=800`, `CFL=0.4`, the largest values over `t=0.1,0.2,0.4` were
approximately:

```text
cell-average saturation L1 error = 2.8234E-3
front absolute error             = 2.1529E-3
pressure relative L2 error       = 5.1918E-3
pressure Linf error              = 6.0809E-3
one-way displacement error       = 5.9452E-4
```

These remain inside the frozen reference gates without changing a physical
equation or postprocessing definition.

For `N=80,160,320`, pre-implementation mesh-refinement orders were:

| Metric | coarse pair | finest pair | frozen minimum |
|---|---:|---:|---:|
| saturation L1 | 0.77499 | 0.68251 | 0.5 |
| front | 0.55156 | 0.73089 | 0.5 |
| pressure L2 | 0.73919 | 0.77438 | 0.5 |
| one-way displacement | 0.75020 | 0.77898 | 0.5 |

For `N=800`, temporal comparisons at `CFL=0.4,0.2,0.1` against the frozen
`CFL=0.0125` same-mesh reference gave finest-pair design orders of `1.11196`,
`1.10357` and `1.10329` for saturation, pressure and displacement,
respectively; the frozen minimum is `0.8`.

The seeded unsafe retry design produced finite nonzero values before freeze:

```text
saturation L2 drift      = 5.16955E-2
pressure L2 drift        = 2.03065E-3
displacement drift       = 9.67339E-5
declared phase-mass drift= 1.00000E-2
```

Each exceeds its frozen detection floor. These calculations do not establish
that the future implementation or formal repetitions pass.

## Claim boundary

The freeze can support a future bounded standalone two-phase displacement
claim only after implementation, unit QA and two formal independent runs per
case. It cannot support two-way poromechanics, capillary flow, fault mechanics,
Abaqus, performance, production readiness or CO2 application conclusions.

