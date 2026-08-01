# L5-D2 independent two-phase validation specification

Status: `FROZEN_NOT_IMPLEMENTED`

Design version: `L5-D2.0`

## Preserved physical problem

The equations, dimensionless parameters, initial and boundary conditions, relative permeabilities, pressure reconstruction and one-way mechanical observable are identical to the frozen L5-D0/L5-D1 problem. The model remains incompressible and immiscible with no gravity and no capillary pressure. Mechanics is diagnostic one-way flow-to-mechanics only.

## Preserved independent implementation

L5-D2 retains the independently written L5 solver and oracle as immutable dependencies: piecewise-linear minmod reconstruction, Rusanov flux with global characteristic bound 2, SSPRK2 time integration, binary length-tagged IEEE-754 state fingerprints, and a separately coded entropy/bisection plus fixed Gauss-8 reference. It may not import L4 implementation code.

## Revised convergence family

The only scientific protocol revision is the convergence estimator. `L5-D2-CV-01` uses the predeclared uniform levels `N=80,160,320,640,1280` at `t=0.2`. For each of saturation L1 error, pressure relative L2 error, front absolute error and one-way displacement absolute error, the formal statistic is the ordinary least-squares slope of `log(error)` against `log(1/N)` over all five levels.

The convergence family passes only when all errors are finite, positive, strictly decreasing on every refinement, and every five-level regression order is at least `0.7`. Adjacent-pair orders and fit diagnostics are retained but are not individual vetoes. No Richardson-extrapolated front or uncertainty band is produced.

## Formal cases

- `L5-D2-REF-01`: independent entropy-reference accuracy.
- `L5-D2-CV-01`: five-level convergence and monotonic-error gate.
- `L5-D2-MB-01`: separate wetting and non-wetting phase balance.
- `L5-D2-FR-01`: front position and profile checks.
- `L5-D2-OP-01`: accepted-output provenance with a live unaccepted trial.
- `L5-D2-RT-01`: safe retry/rollback exact parity.
- `L5-D2-RT-02`: seeded unsafe finite-drift negative control.
- `L5-D2-XP-01`: cross-implementation field parity against hash-verified L4 data.

Each case is planned for two independent single-process, single-thread runs. Cases execute in matrix order and the first prerequisite failure stops all later cases.

## Historical transparency

L5-D1 remains a failed precheck. Its post-failure `N=640/1280` values are diagnostic only and are excluded from L5-D2 formal raw evidence. L5-D2 formal evidence, if authorized after implementation and preflight, must be generated in a new result root from fresh processes.
