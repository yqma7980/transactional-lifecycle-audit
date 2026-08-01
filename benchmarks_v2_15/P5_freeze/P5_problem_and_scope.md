# P5 scaled threshold and fresh-process null-envelope freeze

Date: 2026-07-31
Design version: `CMAME-P5.0`
Status: `FROZEN_STATIC_NOT_IMPLEMENTED`
Execution authorized: `false`

## 1. Purpose

P5 converts the numerical placeholders frozen in P3 into prospective, auditable rules. It defines (i) a metric-specific fresh-process null envelope for benign floating-point nonidentity and (ii) a deterministic low-strength selection rule for the four P3 families `F01`, `F02`, `F05` and `F07`. Neither rule may inspect a P6 result.

P5 is not a detector execution and does not create `OBSERVED-P5` evidence. It freezes how a later calibration would be run and how its output would be bound into P6.

## 2. Host and branch boundary

The prospective host is the frozen serial DOLFINx/PETSc P4d model: 32 P1 triangles, 96 integration points, `G=10`, `tau_y0=1`, `H=2`, one MPI rank and one thread in the immutable DOLFINx image. P5 may use only the observed direct and author-managed retry/restart branches and the author-owned state, output and version contracts.

P4d native rejected line-search coverage remains `NOT_SUPPORTED_BY_DIAGNOSTIC_ENVELOPE`. P5 does not manufacture a native rejected candidate, reinterpret P4d.2, or use line-search non-support to estimate numerical noise.

## 3. Separation of evidence roles

1. **Null calibration** estimates only benign numerical variation from fresh processes and fixed arithmetic reductions.
2. **Null confirmation** tests the frozen envelope on a different predeclared reduction and is excluded from calibration.
3. **Scaled development** scans a new binary amplitude grid on the development site of each fault family.
4. **P6 confirmation** remains held out. It receives the development-selected dimensionless amplitude without adjustment.

Existing FEH/MUT strengths and the old absolute `1e-10` operator threshold are not copied into the new amplitude grid. Existing P4d classifications and thresholds remain immutable historical evidence.

## 4. Scientific interpretation

Structural ownership, version, event-order, source and reachability relations remain exact gates. A structural violation is not absorbed into a numerical envelope. The envelope applies only to predeclared floating-point fields and is an acceptance relation, not a transitive mathematical equivalence relation.

For scaled P3 cases, operator drift is a secondary observable. The primary lifecycle verdict still follows the P2/P3 owner-event-restoration or source-reachability contract. A negative-control contract can pass only by producing the expected failure verdict; the mutated implementation is never described as safe.

## 5. Non-support rule

If the null envelope is unstable, exceeds the frozen engineering ceiling, or a fault family has no two-level separated amplitude on the complete grid while conventional gates remain quiet, the result is `NOT_SUPPORTED_AT_FROZEN_SCALE`. No extra strength, alternate site, relaxed tolerance or result-driven threshold may be introduced.

## 6. Execution boundary

This package contains no implementation, runner, test, case result, FE solve, figure, manuscript edit, public-repository update or DOI change. The next possible step is a separately authorized P5 implementation preflight.
